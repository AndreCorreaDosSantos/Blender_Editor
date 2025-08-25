import subprocess
import os
import re
from pathlib import Path

# ==============================
#  Utils de prompt no terminal
# ==============================
def prompt_opcao(msg, opcoes, default=None):
    """
    Exibe uma lista numerada de opções e retorna o índice (0-based) escolhido.
    Aceita default = índice (0-based) ou None.
    """
    print(msg)
    for i, o in enumerate(opcoes, 1):
        print(f"{i}. {o}")
    while True:
        raw = input(f"👉 Escolha [1-{len(opcoes)}]{f' (Enter={default+1})' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(opcoes):
                return n - 1
        print("❌ Opção inválida. Tente novamente.")

def prompt_inteiro(msg, minimo=1, default=None):
    while True:
        raw = input(f"{msg}{f' (Enter={default})' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit():
            val = int(raw)
            if val >= minimo:
                return val
        print(f"❌ Digite um inteiro ≥ {minimo}.")

def prompt_multiselect(msg, opcoes):
    """
    Permite selecionar múltiplos itens por índice separado por vírgula.
    Aceita 'a' para todos.
    Retorna lista de índices (0-based), sem repetição e em ordem.
    """
    print(msg)
    for i, o in enumerate(opcoes, 1):
        print(f"{i}. {o}")
    while True:
        raw = input("👉 Selecione números separados por vírgula (ex: 1,3,5) ou 'a' para todos: ").strip().lower()
        if raw == 'a':
            return list(range(len(opcoes)))
        try:
            idxs = []
            for tok in raw.split(','):
                tok = tok.strip()
                if not tok:
                    continue
                n = int(tok)
                if 1 <= n <= len(opcoes):
                    idxs.append(n - 1)
                else:
                    raise ValueError
            # dedup mantendo ordem
            dedup = list(dict.fromkeys(idxs))
            if dedup:
                return dedup
        except ValueError:
            pass
        print("❌ Entrada inválida. Tente novamente.")

# ==============================
#  Coletor com yt-dlp
# ==============================
def _coletar_ids(url, limite, tab):
    """
    Usa yt-dlp para listar IDs de vídeos de uma aba específica (videos/shorts).
    """
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
    if r.returncode != 0:
        # Não interrompe o fluxo, mas informa
        print(f"⚠️ yt-dlp retornou código {r.returncode} para {url} ({tab}). Stderr:\n{r.stderr.strip()}")
    ids = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    return ids[:limite]

def get_links(canal_url, limite=5, tipo="videos"):
    """
    tipo: "videos" (longos), "shorts", ou "ambos"
    """
    base = canal_url.rstrip("/")
    def url_tab(tab):
        suffix = "/videos" if tab == "videos" else "/shorts"
        return base + suffix if not base.endswith(suffix) else base

    if tipo == "videos":
        ids = _coletar_ids(url_tab("videos"), limite, "videos")
        if not ids:  # fallback
            ids = _coletar_ids(url_tab("shorts"), limite, "shorts")
    elif tipo == "shorts":
        ids = _coletar_ids(url_tab("shorts"), limite, "shorts")
    elif tipo == "ambos":
        vids = _coletar_ids(url_tab("videos"), limite, "videos")
        sh = _coletar_ids(url_tab("shorts"), limite, "shorts")
        ids = list(dict.fromkeys(vids + sh))[:limite]
    else:
        raise ValueError("tipo deve ser 'videos', 'shorts' ou 'ambos'.")

    return [f"https://www.youtube.com/watch?v={i}" for i in ids]

def extrair_nome_canal(canal_url):
    m = re.search(r"youtube\.com/(@[\w\d_-]+)", canal_url)
    return m.group(1).replace("@", "") if m else "canal_desconhecido"

# ==============================
#  Carregar lista de canais
# ==============================
def carregar_canais():
    """
    Tenta carregar de 'canais.txt' (um URL por linha).
    Se não existir, usa uma lista padrão que você pode editar aqui.
    """
    padrao = [
        "https://www.youtube.com/@Laestro1",
        # adicione mais canais padrão aqui, se quiser:
        # "https://www.youtube.com/@SeuCanal",
    ]
    txt = Path(__file__).with_name("canais.txt")
    if txt.exists():
        canais = []
        for linha in txt.read_text(encoding="utf-8").splitlines():
            u = linha.strip()
            if u and not u.startswith("#"):
                canais.append(u)
        return canais or padrao
    return padrao

# ==============================
#  Main interativo
# ==============================
def main():
    print("🎯 Coletor de links do YouTube (yt-dlp)\n")

    canais = carregar_canais()
    if not canais:
        print("❌ Nenhum canal configurado.")
        return

    # 1) Selecionar um ou vários canais
    idxs = prompt_multiselect("📺 Selecione o(s) canal(is):", canais)

    # 2) Selecionar tipo
    tipos = ["videos", "shorts", "ambos"]
    tipo_idx = prompt_opcao("🎞️ Selecione o tipo de conteúdo:", tipos, default=0)
    tipo = tipos[tipo_idx]

    # 3) Definir limite
    limite = prompt_inteiro("🔢 Limite de links por canal", minimo=1, default=10)

    base_path = os.path.dirname(os.path.abspath(__file__))
    total_geral = 0

    for i in idxs:
        canal_url = canais[i]
        nome_canal = extrair_nome_canal(canal_url)
        print(f"\n⏳ Coletando de {canal_url} | tipo={tipo} | limite={limite} ...")
        links = get_links(canal_url, limite=limite, tipo=tipo)

        arquivo_saida = os.path.join(base_path, f"links_{nome_canal}_{tipo}.txt")
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            for link in links:
                f.write(link + "\n")

        print(f"✅ {len(links)} links salvos em '{arquivo_saida}'")
        total_geral += len(links)

    print(f"\n🏁 Finalizado. Total de links coletados: {total_geral}")

if __name__ == "__main__":
    main()
