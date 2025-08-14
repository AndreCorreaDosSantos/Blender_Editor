import os
import openai
from pathlib import Path
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ✅ Corrige a leitura da chave
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o"

# ✅ Corrige os caminhos
PASTA_RAW = Path("D_agentes_de_estilo/estilo_agente_template/data/raw_transcripts").resolve()
PASTA_LIMPA = Path("D_agentes_de_estilo/estilo_agente_template/data/clean_transcripts").resolve()
PASTA_LIMPA.mkdir(parents=True, exist_ok=True)

MODEL = "gpt-4o"  # ou "gpt-3.5-turbo" se quiser economizar

def corrigir_legenda(texto):
    prompt = f"""
O texto abaixo foi extraído de legendas automáticas do YouTube. Ele contém erros de pontuação, palavras desconexas e frases quebradas. Reescreva como se fosse uma fala contínua, fluida e natural, mantendo o estilo original da pessoa.

- Corrija os erros, mas NÃO mude o conteúdo.
- Una frases quebradas de forma coerente.
- Preserve o tom opinativo, informal, direto.

Texto original:
\"\"\"
{texto}
\"\"\"
"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    resposta = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2048
    )

    return resposta.choices[0].message.content.strip()

def processar_legendas():
    arquivos_txt = list(PASTA_RAW.glob("*.txt"))
    print(f"📂 Encontrados {len(arquivos_txt)} arquivos de legenda.")

    for arquivo in arquivos_txt:
        nome_arquivo = arquivo.stem
        destino = PASTA_LIMPA / f"{nome_arquivo}.txt"

        if destino.exists():
            print(f"✅ Já corrigido: {nome_arquivo}")
            continue

        print(f"🛠️ Corrigindo: {nome_arquivo}")
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()

        try:
            texto_corrigido = corrigir_legenda(conteudo)

            with open(destino, "w", encoding="utf-8") as f:
                f.write(texto_corrigido)

            print(f"✅ Salvo em: {destino.name}")
            time.sleep(1.5)  # evita limite de rate
        except Exception as e:
            print(f"❌ Erro ao processar {nome_arquivo}: {e}")

if __name__ == "__main__":
    processar_legendas()
