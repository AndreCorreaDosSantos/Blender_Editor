import json
from pathlib import Path

def load_stylebook():
    return json.loads((Path(__file__).parent.parent / "style" / "stylebook.json").read_text(encoding="utf-8"))

def load_few_shots():
    path = Path(__file__).parent.parent / "style" / "few_shots"
    return [p.read_text(encoding="utf-8").strip() for p in path.glob("*.txt")]

def gerar_prompt(dados):
    style = load_stylebook()
    shots = load_few_shots()

    prompt = f"""
Você vai escrever um texto opinativo que pareça 100% humano.

Título: {dados['titulo']}
Fonte: {dados['fonte']}
Data: {dados['data']}

Texto-base:
{dados['corpo']}

Use o estilo: {json.dumps(style, indent=2, ensure_ascii=False)}

Exemplos:
{chr(10).join(shots)}

[SAÍDA ESPERADA]
Texto curto a médio, natural, com tom emocional. Sem frases típicas de IA.
"""
    return prompt
