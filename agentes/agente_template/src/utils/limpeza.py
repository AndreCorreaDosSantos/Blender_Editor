# src/utils/limpeza.py
import re

RE_TIMECODE = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\b')
RE_BRACKETS = re.compile(r'\[(?:aplausos|música|risos|music|applause|laughs|inaudível).*?\]', re.I)

def limpar_texto_bruto(texto: str) -> str:
    """Remove timecodes, marcações e espaçamento excessivo."""
    texto = RE_TIMECODE.sub("", texto)
    texto = RE_BRACKETS.sub("", texto)
    return re.sub(r'\s+', ' ', texto).strip()
