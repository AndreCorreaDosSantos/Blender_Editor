import re
from pathlib import Path

def load_phrases(file):
    return (Path(__file__).parent.parent / "style" / file)

def remove_ia_markers(text):
    negatives = load_phrases("negatives.txt").read_text(encoding="utf-8").splitlines()
    for n in negatives:
        text = re.sub(re.escape(n), "", text, flags=re.IGNORECASE)
    return text

def sprinkle_bordoes(text, max_insert=2):
    frases = re.split(r"(?<=[.!?])\\s+", text)
    bordoes = load_phrases("catchphrases.txt").read_text(encoding="utf-8").splitlines()
    for i in range(min(max_insert, len(frases))):
        frases[i] += " " + bordoes[i % len(bordoes)]
    return " ".join(frases)

def punch_up(text):
    text = remove_ia_markers(text)
    return sprinkle_bordoes(text)
