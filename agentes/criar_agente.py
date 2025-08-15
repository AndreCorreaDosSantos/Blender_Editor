from pathlib import Path
from agente_template.src.utils.limpeza import limpar_texto_bruto

# Corrigido: sobe para a pasta "agentes/"
BASE = Path(__file__).resolve().parent.parent
PASTA_BRUTAS = Path(__file__).resolve().parent / "agente_template" / "dados" / "brutas"
PASTA_LIMPAS = Path(__file__).resolve().parent / "agente_template" / "dados" / "limpas"
PASTA_LIMPAS.mkdir(parents=True, exist_ok=True)

def limpar_transcricoes():
    print("📂 Procurando arquivos em:", PASTA_BRUTAS.resolve())

    arquivos = list(PASTA_BRUTAS.glob("*.txt"))
    if not arquivos:
        print("⚠️ Nenhum arquivo .txt encontrado!")
        return

    print(f"➡️ Limpando {len(arquivos)} arquivos...\n")
    for a in arquivos:
        print(f"🔍 Lendo {a.name}...")
        texto = a.read_text(encoding="utf-8", errors="ignore")
        limpo = limpar_texto_bruto(texto)
        (PASTA_LIMPAS / a.name).write_text(limpo, encoding="utf-8")
        print(f"✅ {a.name} limpo e salvo.")

    print(f"\n🏁 Todos os arquivos foram salvos em: {PASTA_LIMPAS.resolve()}")


if __name__ == "__main__":
    limpar_transcricoes()
