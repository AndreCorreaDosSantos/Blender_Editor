from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled
import os
import subprocess
import re

PASTA_LINKS = os.path.dirname(__file__)
ARQUIVOS_DISPONIVEIS = [f for f in os.listdir(PASTA_LINKS) if f.startswith("links_") and f.endswith(".txt")]

if not ARQUIVOS_DISPONIVEIS:
    print("❌ Nenhum arquivo 'links_*.txt' encontrado na pasta.")
    exit()

print("📂 Arquivos disponíveis:")
for i, nome in enumerate(ARQUIVOS_DISPONIVEIS):
    print(f"{i+1}. {nome}")

indice = input("👉 Digite o número do arquivo que deseja usar: ")

try:
    indice = int(indice) - 1
    nome_arquivo = ARQUIVOS_DISPONIVEIS[indice]
except (ValueError, IndexError):
    print("❌ Opção inválida.")
    exit()

CAMINHO_LINKS = os.path.join(PASTA_LINKS, nome_arquivo)

PASTA_DESTINO = os.path.join(os.path.dirname(__file__), "../estilo_agente_template/data/raw_transcripts")
os.makedirs(PASTA_DESTINO, exist_ok=True)

def extrair_video_id(url):
    if "watch?v=" in url:
        return url.split("watch?v=")[1][:11]
    return url[-11:]

def obter_titulo(video_id):
    try:
        comando = ["yt-dlp", f"https://www.youtube.com/watch?v={video_id}", "--get-title"]
        resultado = subprocess.run(comando, capture_output=True, text=True)
        titulo = resultado.stdout.strip()
        titulo = re.sub(r'[<>:"/\\|?*]', '', titulo)  # remove caracteres inválidos
        titulo = titulo[:100]  # limita tamanho
        return titulo or video_id
    except Exception as e:
        print(f"⚠️ Erro ao obter título de {video_id}: {e}")
        return video_id

with open(CAMINHO_LINKS, "r", encoding="utf-8") as f:
    VIDEOS = [linha.strip() for linha in f if linha.strip()]

for url in VIDEOS:
    video_id = extrair_video_id(url)
    print(f"🎬 Processando vídeo: {video_id}")

    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["pt", "pt-BR"])
        texto = "\n".join([item.text for item in transcript])

        titulo = obter_titulo(video_id)
        nome_arquivo = f"{titulo}.txt"
        caminho_arquivo = os.path.join(PASTA_DESTINO, nome_arquivo)

        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(texto)

        print(f"✅ Transcrição salva como: {nome_arquivo}")

    except TranscriptsDisabled:
        print(f"⚠️ Vídeo sem legendas disponíveis: {video_id}")
    except Exception as e:
        print(f"❌ Erro ao baixar vídeo {video_id}: {e}")
