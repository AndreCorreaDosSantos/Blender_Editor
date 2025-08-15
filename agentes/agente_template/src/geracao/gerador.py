from pathlib import Path
import json

# carrega o stylebook final
STYLEBOOK_PATH = Path(__file__).resolve().parents[2] / "dados" / "stylebook.json"

def carregar_stylebook() -> dict:
    if STYLEBOOK_PATH.exists():
        return json.loads(STYLEBOOK_PATH.read_text(encoding="utf-8"))
    return {}

def montar_contexto_estilo(sb: dict) -> dict:
    """
    Extrai partes úteis do stylebook para serem usadas no prompt do gerador.
    """
    return {
        "tom": sb.get("tom"),
        "humor": sb.get("humor"),
        "ritmo": sb.get("ritmo"),
        "marcadores": [m["texto"] for m in sb.get("marcadores_discurso", [])],
        "bordoes": [b["texto"] for b in sb.get("bordoes", [])],
        "interjeicoes": [i["texto"] for i in sb.get("interjeicoes", [])],
        "pausas": sb.get("pontuacoes_enfase", {}).get("pausas_elongadas")
    }

if __name__ == "__main__":
    sb = carregar_stylebook()
    contexto = montar_contexto_estilo(sb)
    print("🎯 Contexto carregado:", contexto)
