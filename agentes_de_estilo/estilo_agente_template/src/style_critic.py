import re
import json
from pathlib import Path

def carregar_stylebook():
    path = Path(__file__).parent.parent / "style" / "stylebook.json"
    return json.loads(path.read_text(encoding="utf-8"))

def avaliar_estilo(texto):
    style = carregar_stylebook()
    score = 0

    if any(t in texto for t in style["lexicon"]["catchphrases_top"]):
        score += 1
    if texto.count("?") / max(1, texto.count(".")) >= style["syntax"]["question_mark_density"]:
        score += 1
    if texto.count("!") / max(1, texto.count(".")) >= style["syntax"]["exclamation_density"]:
        score += 1

    for proibida in style["lexicon"]["avoid_words"]:
        if proibida in texto:
            score -= 1

    return score
