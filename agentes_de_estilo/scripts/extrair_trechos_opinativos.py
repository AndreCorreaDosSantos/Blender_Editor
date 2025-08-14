import os
import re

BASE_PATH = os.path.join("D_agentes_de_estilo", "estilo_agente_template", "data")
PASTA_TRANSCRICOES = os.path.join(BASE_PATH, "raw_transcripts")
PASTA_SAIDA = os.path.join(BASE_PATH, "clean_transcripts")
os.makedirs(PASTA_SAIDA, exist_ok=True)

MIN_PALAVRAS = 30
MAX_PALAVRAS = 150

def limpar_texto(texto):
    return re.sub(r'\s+', ' ', texto.strip())

def dividir_em_blocos(texto):
    # Divide por quebras duplas, ou simples se for o caso
    if "\n\n" in texto:
        blocos = re.split(r"\n{2,}", texto)
    else:
        blocos = texto.split("\n")

    # Junta linhas pequenas em blocos maiores (~parágrafos)
    paragrafo = ""
    resultado = []
    for linha in blocos:
        linha = limpar_texto(linha)
        if not linha:
            continue
        paragrafo += " " + linha
        if len(paragrafo.split()) >= 40:
            resultado.append(paragrafo.strip())
            paragrafo = ""
    if paragrafo:
        resultado.append(paragrafo.strip())
    return resultado

def extrair_trechos():
    for nome_arquivo in os.listdir(PASTA_TRANSCRICOES):
        if not nome_arquivo.endswith(".txt"):
            continue
        
        caminho_arquivo = os.path.join(PASTA_TRANSCRICOES, nome_arquivo)
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()

        blocos = dividir_em_blocos(conteudo)
        trechos_validos = []

        for i, bloco in enumerate(blocos):
            n_palavras = len(bloco.split())
            if MIN_PALAVRAS <= n_palavras <= MAX_PALAVRAS:
                trechos_validos.append(f"[Trecho {i+1} - {n_palavras} palavras]\n{bloco}\n")

        if trechos_validos:
            caminho_saida = os.path.join(PASTA_SAIDA, f"opinativo_{nome_arquivo}")
            with open(caminho_saida, "w", encoding="utf-8") as f_out:
                f_out.write("\n".join(trechos_validos))
            print(f"✅ {len(trechos_validos)} trechos salvos em: {caminho_saida}")
        else:
            print(f"⚠️ Nenhum trecho válido encontrado em: {nome_arquivo}")

if __name__ == "__main__":
    extrair_trechos()
