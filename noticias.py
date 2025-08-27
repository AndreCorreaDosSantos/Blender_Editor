# noticias.py
# -*- coding: utf-8 -*-
import os, io, re, zipfile, argparse
from datetime import datetime, timedelta
from dateutil import tz
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================
# Config
# =========================
BASE_URL     = "http://data.gdeltproject.org/gdeltv2"
OUT_DIR      = "dados_gdelt"
TIMEZONE     = "America/Boa_Vista"
MAX_WORKERS  = 8
SAVE_PARQUET = True

# GKG 2.1 — índices -> nomes
# 1: DATE, 3: SourceCommonName, 4: DocumentIdentifier (URL),
# 8: V2Themes, 10: V2Locations, 15: V2Tone, 25: TranslationInfo
COL_MAP_BASE = {1:"date", 3:"source", 4:"url", 8:"themes", 10:"locations", 15:"tone", 25:"translation"}
COL_FALLBACKS = {"themes":[7,8], "locations":[9,10]}

# Seções conhecidas em PT em domínios globais
KNOWN_PT_SECTIONS = [
    "bbc.com/portuguese",
    "dw.com/pt-br",
    "nytimes.com/pt",
    "france24.com/pt",
    "elpais.com/brasil",
    "elpais.com/america/brasil",
    "theguardian.com/world/portugal",
    "euronews.com/next/pt",
    "euronews.com/pt",
    "cnn.com/brasil",
    "rt.com/portuguese",
    "rfi.fr/pt",
    "afp.com/pt",
]

# Hosts BR comuns sem .br no TLD (ou com múltiplos subdomínios)
KNOWN_PT_HOSTS = {
    # Globo e derivados
    "globo.com", "g1.globo.com", "valor.globo.com", "ge.globo.com",
    "oglobo.globo.com",
    # Portais e jornais
    "metropoles.com", "terra.com.br", "uol.com.br", "band.uol.com.br",
    "folha.uol.com.br", "estadao.com.br", "gazetadopovo.com.br",
    "correiobraziliense.com.br", "diariodepernambuco.com.br",
    "gauchazh.clicrbs.com.br", "veja.abril.com.br",
    # Outros que às vezes aparecem via CDN/link curto
    "gauchazh.com.br", "abril.com.br"
}

# =========================
# Utils
# =========================
def ensure_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)

def session_with_retries():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
    s.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS))
    return s

def round_to_15(dt: datetime) -> datetime:
    m = (dt.minute // 15) * 15
    return dt.replace(minute=m, second=0, microsecond=0)

def gen_timestamps_today_local(tz_name: str, janela_minutos: int | None = None):
    tz_local = tz.gettz(tz_name); tz_utc = tz.gettz("UTC")
    now_local = datetime.now(tz_local)
    if janela_minutos and janela_minutos > 0:
        start_local = round_to_15(now_local - timedelta(minutes=janela_minutos))
    else:
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = now_local
    stamps = []
    curr = start_local
    while curr <= end_local:
        stamps.append(curr.astimezone(tz_utc).strftime("%Y%m%d%H%M%S"))
        curr += timedelta(minutes=15)
    return stamps

def map_columns_with_fallback(df: pd.DataFrame) -> pd.DataFrame:
    present = set(df.columns.tolist())
    col_map = {}
    for idx, name in COL_MAP_BASE.items():
        if idx in present:
            col_map[idx] = name
    if "themes" not in col_map.values():
        for cand in COL_FALLBACKS["themes"]:
            if cand in present:
                col_map[cand] = "themes"; break
    if "locations" not in col_map.values():
        for cand in COL_FALLBACKS["locations"]:
            if cand in present:
                col_map[cand] = "locations"; break
    df = df[list(col_map.keys())].rename(columns=col_map)
    for must in ["date","source","url","themes","locations","tone","translation"]:
        if must not in df.columns:
            df[must] = ""
    return df

def read_gkg_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            df = pd.read_csv(f, sep="\t", header=None, dtype=str, on_bad_lines="skip", encoding="utf-8", engine="python")
    df = map_columns_with_fallback(df)
    df["date_utc"] = pd.to_datetime(df["date"], format="%Y%m%d%H%M%S", errors="coerce", utc=True)
    for c in ["source","url","themes","locations","tone","translation"]:
        df[c] = df[c].fillna("")
    return df

def filter_today_local(df: pd.DataFrame, tz_name: str) -> pd.DataFrame:
    tz_local = tz.gettz(tz_name)
    start_local = datetime.now(tz_local).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local   = start_local + timedelta(days=1)
    dfl = df.copy()
    dfl["date_local"] = dfl["date_utc"].dt.tz_convert(tz_local)
    return dfl[dfl["date_local"].between(start_local, end_local, inclusive="left")]

# ---- Heurísticas robustas para "conteúdo em português" ----
def is_pt_host(host: str) -> bool:
    """Português por TLD .br/.pt OU host presente em lista de veículos PT/BR."""
    if not host:
        return False
    h = host.lower()
    return h.endswith(".br") or h.endswith(".pt") or h in KNOWN_PT_HOSTS

def is_pt_query(qs: dict) -> bool:
    """Querystring indica PT? (lang/locale/hl=pt ou pt-BR)"""
    for k, vals in qs.items():
        if k.lower() in {"lang","locale","hl"}:
            joined = " ".join(str(v).lower() for v in vals)
            if re.search(r"\bpt(?:-br)?\b", joined):
                return True
    return False

def is_pt_section(host: str, path: str) -> bool:
    """Caminho bate em seções PT conhecidas (BBC, DW, NYT, etc.)?"""
    full = (host + path).lower()
    return any(hint in full for hint in KNOWN_PT_SECTIONS)

def portuguese_mask_from_url(url_series: pd.Series) -> pd.Series:
    """
    Retorna uma Series booleana marcando URLs que provavelmente são conteúdo em português.
    Critérios (OR):
      - host .br/.pt ou em KNOWN_PT_HOSTS
      - querystring com lang/locale/hl=pt/pt-BR
      - seção PT conhecida no path
    """
    hosts, paths, qs_dicts = [], [], []
    for u in url_series.fillna(""):
        try:
            parsed = urlparse(u)
            hosts.append((parsed.hostname or "").lower())
            paths.append((parsed.path or "").lower())
            qs_dicts.append(parse_qs(parsed.query or ""))
        except Exception:
            hosts.append("")
            paths.append("")
            qs_dicts.append({})
    hosts = pd.Series(hosts, index=url_series.index)
    paths = pd.Series(paths, index=url_series.index)

    m_host = hosts.apply(is_pt_host)
    m_qs   = pd.Series([is_pt_query(q) for q in qs_dicts], index=url_series.index)
    m_sec  = pd.Series([is_pt_section(h, p) for h, p in zip(hosts, paths)], index=url_series.index)
    return m_host | m_qs | m_sec

def apply_filters(df: pd.DataFrame, only_lang: set[str], filter_brazil: bool):
    dff = df.copy()
    stats = {"ingestao": len(dff)}

    # FILTRO "PORTUGUÊS" REFORÇADO:
    if only_lang and ("POR" in {x.upper() for x in only_lang}):
        # máscara por URL (host/qs/seções)
        m_url_pt = portuguese_mask_from_url(dff["url"])
        cnt_url_pt = int(m_url_pt.sum())

        # TranslationInfo — parse robusto (srclc/srclang/src_lc)
        lang_extracted = dff["translation"].str.extract(
            r'(?i)\b(?:srclc|srclang|src_lc)[:=]\s*([a-z]{3})\b', expand=False
        ).str.upper().fillna("")
        m_tr_pt = lang_extracted.eq("POR")
        cnt_tr_pt = int(m_tr_pt.sum())

        m_pt = m_url_pt | m_tr_pt
        dff = dff[m_pt]
        stats.update({"pt_url_mask": cnt_url_pt, "pt_trans_info": cnt_tr_pt})
    else:
        # quando não há filtragem por idioma, ainda assim registra contagem opcional por curiosidade
        stats.update({"pt_url_mask": "—", "pt_trans_info": "—"})

    stats["apos_idioma"] = len(dff)

    # Brasil por V2Locations (opcional)
    if filter_brazil and not dff.empty:
        loc = dff["locations"].fillna("")
        m_br = loc.str.contains("Brazil", case=False, na=False) | loc.str.contains(r"\bBRA\b", case=False, na=False)
        dff = dff[m_br]
        stats["apos_brasil"] = len(dff)
    else:
        stats["apos_brasil"] = "—"

    # Dedup + ordenação
    if not dff.empty:
        dff = dff.dropna(subset=["url"]).drop_duplicates(subset=["url"])
        dff = dff.sort_values("date_utc", ascending=False).reset_index(drop=True)
    stats["apos_dedup"] = len(dff)

    return dff, stats

def download_gkg_zip(ts: str, sess: requests.Session) -> bytes | None:
    """Baixa o pacote GKG referente ao timestamp (YYYYMMDDHHMMSS). Retorna bytes do ZIP ou None."""
    url = f"{BASE_URL}/{ts}.gkg.csv.zip"
    try:
        r = sess.get(url, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        pass
    return None

# =========================
# Main
# =========================
def main():
    ap = argparse.ArgumentParser(description="GDELT (GKG) do dia atual — com detecção robusta de conteúdo em português.")
    # permite usar --idiomas SEM valor (fica vazio => todos)
    ap.add_argument(
        "--idiomas",
        nargs="?",           # 0 ou 1 valor
        const="",            # se vier sem valor => ""
        type=str,
        default="POR",
        help="ISO-639-3 separados por vírgula (ex.: POR,ENG,SPA). Se usado sem valor, pega TODOS."
    )
    ap.add_argument("--brasil", action="store_true", help="Filtrar Brasil em V2Locations.")
    ap.add_argument("--janela-minutos", type=int, default=0, help="Se >0, pega apenas os últimos X minutos (ex.: 120).")
    ap.add_argument("--sem-paralelo", action="store_true", help="Baixar sequencial (debug).")
    args = ap.parse_args()

    # Trata '', '""', "''" e espaços como vazio (=> todos os idiomas)
    idiomas_raw = (args.idiomas or "").strip().strip('"').strip("'")
    only_lang = {x.strip().upper() for x in idiomas_raw.split(",") if x.strip()} if idiomas_raw else set()

    ensure_dirs()
    stamps = gen_timestamps_today_local(TIMEZONE, args.janela_minutos if args.janela_minutos > 0 else None)
    sess = session_with_retries()

    print(f"🌎 Fuso: {TIMEZONE}")
    print(f"🗓️  Timestamps: {len(stamps)} (15 em 15 min)")
    print(f"🈚  Idiomas alvo: {('todos' if not only_lang else ','.join(sorted(only_lang)))} | 🇧🇷 Brasil: {args.brasil}")
    print(f"⚙️  Download: {'sequencial' if args.sem_paralelo else f'paralelo ({MAX_WORKERS} threads)'}")

    # Download
    blobs, ok, miss = [], 0, 0
    if args.sem_paralelo:
        for ts in stamps:
            b = download_gkg_zip(ts, sess)
            if b: blobs.append(b); ok += 1
            else: miss += 1
    else:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(download_gkg_zip, ts, sess): ts for ts in stamps}
            for fut in as_completed(futs):
                b = fut.result()
                if b: blobs.append(b); ok += 1
                else: miss += 1

    if not blobs:
        print("❌ Nada baixado. Tente aumentar a janela ou rodar mais tarde.")
        return

    # Parse
    frames = []
    for blob in blobs:
        try:
            frames.append(read_gkg_from_zip(blob))
        except Exception:
            pass
    if not frames:
        print("❌ Nenhum pacote válido após parse.")
        return

    df_all = pd.concat(frames, ignore_index=True)

    # Recorte do dia local
    before_day = len(df_all)
    df_all = filter_today_local(df_all, TIMEZONE)
    after_day = len(df_all)

    # Filtros
    df_all, stats = apply_filters(df_all, only_lang=only_lang, filter_brazil=args.brasil)

    # Campos ISO legíveis (além do epoch ms padrão do to_json/to_parquet)
    if not df_all.empty:
        df_all["date_local_iso"] = df_all["date_local"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
        df_all["date_utc_iso"]   = df_all["date_utc"].dt.strftime("%Y-%m-%d %H:%M:%S%z")

    # Save
    jsonl_path = os.path.join(OUT_DIR, "hoje.jsonl")
    df_all.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

    saved_msg = jsonl_path
    if SAVE_PARQUET:
        try:
            import pyarrow  # noqa
            parquet_path = os.path.join(OUT_DIR, "hoje.parquet")
            df_all.to_parquet(parquet_path, index=False)
            saved_msg += f" e {parquet_path}"
        except Exception as e:
            csv_path = os.path.join(OUT_DIR, "hoje.csv")
            df_all.to_csv(csv_path, index=False, encoding="utf-8")
            print(f"⚠️ Parquet indisponível ({e}). Salvei CSV.")
            saved_msg += f" e {csv_path}"

    print(f"✅ Pacotes OK: {ok}, faltando/erros: {miss}")
    # monta os campos de log com fallback visual “—” quando não se aplica
    pt_url_mask  = stats.get("pt_url_mask", "—")
    pt_tr_info   = stats.get("pt_trans_info","—")
    apos_brasil  = stats.get("apos_brasil","—")
    print(f"📊 ingestão={sum(len(x) for x in frames)}, dia_local={after_day}/{before_day}, "
          f"pt_url_mask={pt_url_mask}, pt_trans_info={pt_tr_info}, "
          f"após_idioma={stats['apos_idioma']}, após_brasil={apos_brasil}, dedup={stats['apos_dedup']}")
    print(f"💾 Salvos: {saved_msg}")

if __name__ == "__main__":
    main()
