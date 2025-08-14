# scripts/limpar_transcricoes.py
import re
from pathlib import Path

RAIZ  = Path(__file__).resolve().parents[1] / "dados"
BRUTAS = RAIZ / "brutas"
LIMPAS = RAIZ / "limpas"
LIMPAS.mkdir(parents=True, exist_ok=True)

RE_TIMECODE = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\b')
RE_BRACKETS = re.compile(r'\[(?:aplausos|música|risos|music|applause|laughs|inaudível).*?\]', re.I)

def limpar(txt: str) -> str:
    txt = RE_TIMECODE.sub("", txt)
    txt = RE_BRACKETS.sub("", txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def main():
    arquivos = list(BRUTAS.glob("*.txt"))
    print(f"➡️ Limpando {len(arquivos)} arquivos...")
    for a in arquivos:
        conteudo = a.read_text(encoding="utf-8", errors="ignore")
        saida = limpar(conteudo)
        (LIMPAS / a.name).write_text(saida, encoding="utf-8")
        print("✅", a.name)
    print("🏁 Pronto em:", LIMPAS)

if __name__ == "__main__":
    main()
