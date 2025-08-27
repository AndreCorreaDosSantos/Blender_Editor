# noticias.py
# -*- coding: utf-8 -*-
import os, io, re, zipfile, argparse, time
from datetime import datetime, timedelta
from dateutil import tz
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========= Config =========
BASE_URL     = "http://data.gdeltproject.org/gdeltv2"
OUT_DIR      = "dados_gdelt"
TIMEZONE     = "America/Boa_Vista"
MAX_WORKERS  = 8
SAVE_PARQUET = True

# GKG 2.1 — índices -> nomes
COL_MAP_BASE = {1:"date", 3:"source", 4:"url", 8:"themes", 10:"locations", 15:"tone", 25:"translation"}
COL_FALLBACKS = {"themes":[7,8], "locations":[9,10]}

KNOWN_PT_SECTIONS = [
    "bbc.com/portuguese","dw.com/pt-br","nytimes.com/pt","france24.com/pt",
    "elpais.com/brasil","elpais.com/america/brasil","theguardian.com/world/portugal",
    "euronews.com/pt","euronews.com/next/pt","cnn.com/brasil","rt.com/portuguese","rfi.fr/pt","afp.com/pt",
]
KNOWN_PT_HOSTS = {
    "globo.com","g1.globo.com","valor.globo.com","ge.globo.com","oglobo.globo.com",
    "metropoles.com","terra.com.br","uol.com.br","band.uol.com.br","folha.uol.com.br",
    "estadao.com.br","gazetadopovo.com.br","correiobraziliense.com.br","diariodepernambuco.com.br",
    "gauchazh.clicrbs.com.br","veja.abril.com.br","gauchazh.com.br","abril.com.br"
}

# ======== Utils =========
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

# ---- Heurísticas PT ----
def is_pt_host(host: str) -> bool:
    if not host: return False
    h = host.lower()
    return h.endswith(".br") or h.endswith(".pt") or h in KNOWN_PT_HOSTS

def is_pt_query(qs: dict) -> bool:
    for k, vals in qs.items():
        if k.lower() in {"lang","locale","hl"}:
            joined = " ".join(str(v).lower() for v in vals)
            if re.search(r"\bpt(?:-br)?\b", joined):
                return True
    return False

def is_pt_section(host: str, path: str) -> bool:
    full = (host + path).lower()
    return any(hint in full for hint in KNOWN_PT_SECTIONS)

def portuguese_mask_from_url(url_series: pd.Series) -> pd.Series:
    hosts, paths, qs_dicts = [], [], []
    for u in url_series.fillna(""):
        try:
            p = urlparse(u)
            hosts.append((p.hostname or "").lower())
            paths.append((p.path or "").lower())
            qs_dicts.append(parse_qs(p.query or ""))
        except Exception:
            hosts.append(""); paths.append(""); qs_dicts.append({})
    hosts = pd.Series(hosts, index=url_series.index); paths = pd.Series(paths, index=url_series.index)
    m_host = hosts.apply(is_pt_host)
    m_qs   = pd.Series([is_pt_query(q) for q in qs_dicts], index=url_series.index)
    m_sec  = pd.Series([is_pt_section(h, p) for h, p in zip(hosts, paths)], index=url_series.index)
    return m_host | m_qs | m_sec

def apply_filters(df: pd.DataFrame, only_lang: set[str], filter_brazil: bool):
    dff = df.copy()
    stats = {"ingestao": len(dff)}
    if only_lang and ("POR" in {x.upper() for x in only_lang}):
        m_url_pt = portuguese_mask_from_url(dff["url"])
        cnt_url_pt = int(m_url_pt.sum())
        lang_extracted = dff["translation"].str.extract(
            r'(?i)\b(?:srclc|srclang|src_lc)[:=]\s*([a-z]{3})\b', expand=False
        ).str.upper().fillna("")
        m_tr_pt = lang_extracted.eq("POR"); cnt_tr_pt = int(m_tr_pt.sum())
        dff = dff[m_url_pt | m_tr_pt]
        stats.update({"pt_url_mask": cnt_url_pt, "pt_trans_info": cnt_tr_pt})
    else:
        stats.update({"pt_url_mask": "—", "pt_trans_info": "—"})
    stats["apos_idioma"] = len(dff)

    if filter_brazil and not dff.empty:
        loc = dff["locations"].fillna("")
        m_br = loc.str.contains("Brazil", case=False, na=False) | loc.str.contains(r"\bBRA\b", case=False, na=False)
        dff = dff[m_br]; stats["apos_brasil"] = len(dff)
    else:
        stats["apos_brasil"] = "—"

    if not dff.empty:
        dff = dff.dropna(subset=["url"]).drop_duplicates(subset=["url"])
        dff = dff.sort_values("date_utc", ascending=False).reset_index(drop=True)
    stats["apos_dedup"] = len(dff)
    return dff, stats

def download_gkg_zip(ts: str, sess: requests.Session) -> bytes | None:
    url = f"{BASE_URL}/{ts}.gkg.csv.zip"
    try:
        r = sess.get(url, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        pass
    return None

# ======= EXTRAÇÃO DO TEXTO =======
def maybe_import_trafilatura():
    try:
        import trafilatura
        from trafilatura.metadata import extract_metadata
        return trafilatura, extract_metadata
    except Exception:
        return None, None

def extract_article_text(url: str, timeout: int = 15):
    """
    Baixa e extrai texto/título com trafilatura. Retorna dict com:
    { 'title', 'text', 'lang', 'status' }
    """
    trafilatura, extract_metadata = maybe_import_trafilatura()
    if trafilatura is None:
        return {"title": None, "text": None, "lang": None, "status": "trafilatura-missing"}

    try:
        downloaded = trafilatura.fetch_url(url, timeout=timeout)
        if not downloaded:
            return {"title": None, "text": None, "lang": None, "status": "fetch-failed"}

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            favor_recall=True,   # tenta puxar mais texto quando necessário
            with_metadata=False
        )
        meta = extract_metadata(downloaded)
        title = getattr(meta, "title", None) if meta else None
        lang  = getattr(meta, "language", None) if meta else None

        if text and len(text.strip()) >= 200:  # mínimo para considerar artigo
            return {"title": title, "text": text, "lang": lang, "status": "ok"}
        else:
            return {"title": title, "text": text, "lang": lang, "status": "extract-weak"}
    except Exception as e:
        return {"title": None, "text": None, "lang": None, "status": f"error:{type(e).__name__}"}

def enrich_with_article_text(df: pd.DataFrame, max_items: int, timeout: int):
    if df.empty:
        return df.assign(title=None, text=None, lang=None, fetch_status=None)

    take = min(max_items, len(df))
    subset = df.head(take).copy()
    results = [None] * take

    def worker(i, u):
        results[i] = extract_article_text(u, timeout=timeout)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(worker, i, u): i for i, u in enumerate(subset["url"].tolist())}
        for _ in as_completed(futures):
            pass

    subset = subset.reset_index(drop=True)
    subset["title"] = [r["title"] if r else None for r in results]
    subset["text"]  = [r["text"] if r else None for r in results]
    subset["lang"]  = [r["lang"] if r else None for r in results]
    subset["fetch_status"] = [r["status"] if r else "unknown" for r in results]

    # Junta de volta (mantendo ordem original)
    rest = df.iloc[take:].copy()
    out = pd.concat([subset, rest], ignore_index=True)
    return out

# ========= Main =========
def main():
    ap = argparse.ArgumentParser(description="GDELT (GKG) do dia — com detecção PT e opcional de baixar texto das matérias.")
    ap.add_argument(
        "--idiomas", nargs="?", const="", type=str, default="POR",
        help="ISO-639-3 separados por vírgula (ex.: POR,ENG,SPA). Se usado sem valor, pega TODOS."
    )
    ap.add_argument("--brasil", action="store_true", help="Filtrar Brasil em V2Locations.")
    ap.add_argument("--janela-minutos", type=int, default=0, help="Se >0, pega apenas os últimos X minutos (ex.: 120).")
    ap.add_argument("--sem-paralelo", action="store_true", help="Baixar sequencial (debug).")

    # novos
    ap.add_argument("--baixar-texto", action="store_true", help="Baixar e extrair o texto/título dos artigos.")
    ap.add_argument("--max-artigos", type=int, default=200, help="Máximo de artigos para extrair texto (para evitar bloqueios).")
    ap.add_argument("--timeout", type=int, default=15, help="Timeout de download por artigo (segundos).")

    args = ap.parse_args()

    idiomas_raw = (args.idiomas or "").strip().strip('"').strip("'")
    only_lang = {x.strip().upper() for x in idiomas_raw.split(",") if x.strip()} if idiomas_raw else set()

    ensure_dirs()
    stamps = gen_timestamps_today_local(TIMEZONE, args.janela_minutos if args.janela_minutos > 0 else None)
    sess = session_with_retries()

    print(f"🌎 Fuso: {TIMEZONE}")
    print(f"🗓️  Timestamps: {len(stamps)} (15 em 15 min)")
    print(f"🈚  Idiomas alvo: {('todos' if not only_lang else ','.join(sorted(only_lang)))} | 🇧🇷 Brasil: {args.brasil}")
    print(f"⚙️  Download: {'sequencial' if args.sem_paralelo else f'paralelo ({MAX_WORKERS} threads)'}")

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
        print("❌ Nada baixado. Tente aumentar a janela ou rodar mais tarde."); return

    frames = []
    for blob in blobs:
        try:
            frames.append(read_gkg_from_zip(blob))
        except Exception:
            pass
    if not frames:
        print("❌ Nenhum pacote válido após parse."); return

    df_all = pd.concat(frames, ignore_index=True)
    before_day = len(df_all)
    df_all = filter_today_local(df_all, TIMEZONE)
    after_day = len(df_all)

    df_all, stats = apply_filters(df_all, only_lang=only_lang, filter_brazil=args.brasil)

    if not df_all.empty:
        df_all["date_local_iso"] = df_all["date_local"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
        df_all["date_utc_iso"]   = df_all["date_utc"].dt.strftime("%Y-%m-%d %H:%M:%S%z")

    # (Opcional) baixar texto das matérias
    if args.baixar_texto and not df_all.empty:
        trafilatura, _ = maybe_import_trafilatura()
        if trafilatura is None:
            print("⚠️ Para baixar texto, instale: pip install trafilatura")
        else:
            print(f"📰 Extraindo texto de até {min(args.max_artigos, len(df_all))} artigos…")
            df_all = enrich_with_article_text(df_all, max_items=args.max_artigos, timeout=args.timeout)

    # Salvar
    jsonl_path = os.path.join(OUT_DIR, "hoje.jsonl")
    df_all.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)
    saved_msg = jsonl_path

    base = "hoje_com_texto" if args.baixar_texto else "hoje"
    if SAVE_PARQUET:
        try:
            import pyarrow  # noqa
            parquet_path = os.path.join(OUT_DIR, f"{base}.parquet")
            df_all.to_parquet(parquet_path, index=False)
            saved_msg += f" e {parquet_path}"
        except Exception as e:
            csv_path = os.path.join(OUT_DIR, f"{base}.csv")
            df_all.to_csv(csv_path, index=False, encoding="utf-8")
            print(f"⚠️ Parquet indisponível ({e}). Salvei CSV.")
            saved_msg += f" e {csv_path}"

    print(f"✅ Pacotes OK: {ok}, faltando/erros: {miss}")
    pt_url_mask  = stats.get("pt_url_mask", "—")
    pt_tr_info   = stats.get("pt_trans_info","—")
    apos_brasil  = stats.get("apos_brasil","—")
    print(f"📊 ingestão={sum(len(x) for x in frames)}, dia_local={after_day}/{before_day}, "
          f"pt_url_mask={pt_url_mask}, pt_trans_info={pt_tr_info}, "
          f"após_idioma={stats['apos_idioma']}, após_brasil={apos_brasil}, dedup={stats['apos_dedup']}")
    print(f"💾 Salvos: {saved_msg}")

if __name__ == "__main__":
    main()
