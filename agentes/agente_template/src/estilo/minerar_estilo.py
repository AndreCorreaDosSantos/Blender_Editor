# -*- coding: utf-8 -*-
"""
minerar_estilo.py — versão blocos + fusão via IA (com melhorias)
Orquestra a clonagem de estilo lendo transcrições limpas, dividindo em blocos,
enviando cada bloco para a IA e consolidando as análises em um stylebook final.

Entradas:
  - agentes/agente_template/dados/limpas/*.txt

Saídas:
  - agentes/agente_template/dados/parciais/stylebook_parcial_XX.json
  - agentes/agente_template/dados/stylebook.json

Uso:
  python -m agentes.agente_template.src.estilo.minerar_estilo \
    --max_chars 6000 \
    --model gpt-4o-mini
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# ⚠️ Importa o motor de prompts (é ele quem faz a requisição para a IA)
from agentes.agente_template.src.estilo.motor_de_prompts import gerar

# =======================
#  Caminhos de Arquivo
# =======================
# Este arquivo está em: agentes/agente_template/src/estilo/minerar_estilo.py
# Queremos chegar na raiz: agentes/agente_template/
BASE = Path(__file__).resolve().parents[2]
PASTA_LIMPAS = BASE / "dados" / "limpas"
PASTA_PARCIAIS = BASE / "dados" / "parciais"
SAIDA_FINAL = BASE / "dados" / "stylebook.json"
PASTA_PARCIAIS.mkdir(parents=True, exist_ok=True)


# =======================
#  Utilidades
# =======================
def dividir_em_blocos(texto: str, max_chars: int = 6000) -> List[str]:
    """
    Divide um texto longo em blocos de tamanho seguro para a IA, preservando quebras de linha.
    Usa contagem de caracteres para evitar estouro de contexto.
    """
    blocos, atual, tamanho = [], [], 0
    for linha in texto.splitlines():
        ln = linha or ""
        if tamanho + len(ln) > max_chars and atual:
            blocos.append("\n".join(atual))
            atual, tamanho = [], 0
        atual.append(ln)
        tamanho += len(ln)
    if atual:
        blocos.append("\n".join(atual))
    return blocos


def _json_load_safely(payload: str) -> Any:
    """
    Tenta fazer json.loads; se falhar, retorna um dict com o erro e um trecho da resposta.
    """
    try:
        return json.loads(payload)
    except Exception:
        return {"_erro_parse_json": True, "_amostra_resposta": payload[:800]}


# =======================
#  Pipeline
# =======================
def analisar_blocos(texto: str, max_chars: int, model: str) -> List[Dict[str, Any]]:
    """
    Divide o corpus em blocos e chama a IA para cada bloco usando o prompt MINERAR_ESTILO_BLOCO.
    Salva os parciais em /dados/parciais.
    """
    blocos = dividir_em_blocos(texto, max_chars=max_chars)
    print(f"🔹 {len(blocos)} bloco(s) gerado(s) (≈ {sum(map(len, blocos))} chars totais)")

    analises: List[Dict[str, Any]] = []
    for i, bloco in enumerate(blocos, 1):
        print(f"  → Processando bloco {i}/{len(blocos)} (≈ {len(bloco)} chars)…")
        try:
            resp = gerar("MINERAR_ESTILO_BLOCO", {"trecho": bloco}, model=model)
        except Exception as e:
            # Captura erro de chamada à IA e registra
            data = {"_erro_chamada_ia": True, "_mensagem": str(e)}
        else:
            data = _json_load_safely(resp)

        analises.append(data)
        # salva cada parcial
        parcial_fp = PASTA_PARCIAIS / f"stylebook_parcial_{i:02}.json"
        parcial_fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    ✅ Parcial salva em: {parcial_fp}")
    return analises


def fundir_analises(analises: List[Dict[str, Any]], model: str) -> Dict[str, Any]:
    """
    Consolida as análises parciais em um único stylebook via prompt MINERAR_ESTILO_FUSAO.
    """
    print("🔧 Fundindo análises parciais…")
    # Passa as análises como JSON (texto) para a IA consolidar
    analises_texto = json.dumps(analises, ensure_ascii=False, indent=2)
    try:
        fusao_resp = gerar("MINERAR_ESTILO_FUSAO", {"analises": analises_texto}, model=model)
    except Exception as e:
        return {"_erro_fusao": True, "_mensagem": str(e)}
    return _json_load_safely(fusao_resp)


def minerar_estilo(max_chars: int, model: str) -> Path:
    """
    Orquestra:
      1) Lê transcrições limpas
      2) Analisa por blocos (chamadas à IA)
      3) Consolida (chamada à IA)
      4) Salva stylebook final
    """
    # 1) junta todas as legendas limpas
    arquivos = sorted(PASTA_LIMPAS.glob("*.txt"))
    textos = [f.read_text(encoding="utf-8", errors="ignore") for f in arquivos]
    corpus = "\n\n".join(textos).strip()

    if not corpus:
        raise RuntimeError(f"Nenhum texto encontrado em {PASTA_LIMPAS}. "
                           "Verifique se suas transcrições limpas (.txt) estão nessa pasta.")

    print(f"📖 Corpus carregado a partir de {len(arquivos)} arquivo(s) em {PASTA_LIMPAS}")
    print(f"   Tamanho total ≈ {len(corpus)} chars")

    # 2) roda por blocos
    analises = analisar_blocos(corpus, max_chars=max_chars, model=model)

    # 3) fusão final
    stylebook_final = fundir_analises(analises, model=model)

    # 4) adiciona metadados
    if isinstance(stylebook_final, dict):
        stylebook_final.setdefault("versao", "2.0-blocos")
        stylebook_final["gerado_em"] = datetime.utcnow().isoformat()
        stylebook_final.setdefault("_fonte", "fusão_de_blocos")
    else:
        # fallback se a IA retornou algo que não é dict
        stylebook_final = {
            "_erro_formato": True,
            "_amostra": str(stylebook_final)[:800],
            "versao": "2.0-blocos",
            "gerado_em": datetime.utcnow().isoformat(),
            "_fonte": "fusão_de_blocos"
        }

    # 5) salva resultado
    SAIDA_FINAL.write_text(json.dumps(stylebook_final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Stylebook consolidado salvo em: {SAIDA_FINAL}")
    return SAIDA_FINAL


# =======================
#  CLI
# =======================
def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Clonagem de estilo por blocos + fusão via IA.")
    ap.add_argument("--max_chars", type=int, default=6000,
                    help="Tamanho máximo (em caracteres) de cada bloco enviado à IA (padrão: 6000).")
    ap.add_argument("--model", type=str, default="gpt-4o-mini",
                    help="Modelo da IA a ser usado (ex.: gpt-4o, gpt-4o-mini).")
    return ap.parse_args()


def main():
    args = _parse_args()
    print(f"🚀 Iniciando minerar_estilo.py | modelo={args.model} | max_chars={args.max_chars}")
    print(f"📂 PASTA_LIMPAS:   {PASTA_LIMPAS}")
    print(f"📂 PASTA_PARCIAIS: {PASTA_PARCIAIS}")
    print(f"📝 SAIDA_FINAL:    {SAIDA_FINAL}")
    minerar_estilo(max_chars=args.max_chars, model=args.model)


if __name__ == "__main__":
    main()
