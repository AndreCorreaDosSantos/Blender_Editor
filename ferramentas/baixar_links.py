import subprocess
import os
import re

def _coletar_ids(url, limite, tab):
    # Força a aba correta e evita warnings atrapalhando a saída
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--playlist-end", str(limite),
        "--get-id",
        "--no-warnings",
        "--ignore-errors",
        "--extractor-args", f"youtube:tab={tab}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # Se quiser debugar: print(r.stderr)
    ids = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    return ids[:limite]

def get_links(canal_url, limite=5, tipo="videos"):
    """
    tipo: "videos" (longos), "shorts", ou "ambos"
    """
    base = canal_url.rstrip("/")
    def url_tab(tab):  # garante URL com a aba explícita
        suffix = "/videos" if tab == "videos" else "/shorts"
        return base + suffix if not base.endswith(suffix) else base

    if tipo == "videos":
        ids = _coletar_ids(url_tab("videos"), limite, "videos")
        # fallback: se não achou nada, tenta shorts
        if not ids:
            ids = _coletar_ids(url_tab("shorts"), limite, "shorts")
    elif tipo == "shorts":
        ids = _coletar_ids(url_tab("shorts"), limite, "shorts")
    elif tipo == "ambos":
        vids = _coletar_ids(url_tab("videos"), limite, "videos")
        sh = _coletar_ids(url_tab("shorts"), limite, "shorts")
        # dedup mantendo ordem
        ids = list(dict.fromkeys(vids + sh))
        ids = ids[:limite]  # se quiser limitar o total combinado
    else:
        raise ValueError("tipo deve ser 'videos', 'shorts' ou 'ambos'.")

    return [f"https://www.youtube.com/watch?v={i}" for i in ids]

def extrair_nome_canal(canal_url):
    m = re.search(r"youtube\.com/(@[\w\d_-]+)", canal_url)
    return m.group(1).replace("@", "") if m else "canal_desconhecido"

# ===== CONFIG =====
canal_url = "https://www.youtube.com/@Laestro1"
limite = 6
tipo = "shorts"       # "videos" | "shorts" | "ambos"
# ===================

nome_canal = extrair_nome_canal(canal_url)
VIDEOS = get_links(canal_url, limite=limite, tipo=tipo)

base_path = os.path.dirname(os.path.abspath(__file__))
arquivo_saida = os.path.join(base_path, f"links_{nome_canal}_{tipo}.txt")

with open(arquivo_saida, "w", encoding="utf-8") as f:
    for link in VIDEOS:
        f.write(link + "\n")

print(f"✅ {len(VIDEOS)} links salvos em '{arquivo_saida}'")
