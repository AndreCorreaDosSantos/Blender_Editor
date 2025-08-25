# -*- coding: utf-8 -*-
"""
estilo_pipeline.py — Arquivo ÚNICO com tudo junto (limpeza + prompts + mineração + gerador)

Classes:
  - PromptEngine: carrega .env, processa templates ({{var|default}}) e chama a OpenAI
  - StyleMiner: lê transcrições limpas, divide em blocos, analisa, funde e salva stylebook.json
  - StyleGenerator: carrega stylebook.json e monta contexto de estilo para uso em prompts de geração

Subcomandos (CLI):
  - minerar       → roda o pipeline completo e gera dados/stylebook.json
  - contexto      → imprime/salva o contexto sintetizado do stylebook (dados/contexto_estilo.json)

Exemplos:
  python estilo_pipeline.py minerar --max_chars 6000 --model gpt-4o-mini
  python estilo_pipeline.py contexto --save

Observações:
  - .env deve conter OPENAI_API_KEY=...
  - Caminhos padrão assumem estrutura .../<base_dir>/dados/{limpas,parciais}/ e stylebook.json.
    Você pode sobrescrever com flags: --base_dir/--limpas_dir/--parciais_dir/--saida_final
"""

from __future__ import annotations
import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from string import Template

# ==========================
# CONFIGURAÇÕES PADRÃO
# ==========================
DEFAULT_MODEL = "gpt-4o-mini"  # Ex.: gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini
DEFAULT_IDIOMA = "pt-BR"       # pt-BR, en-US, es-ES
DEFAULT_MAX_ITENS = 25         # Máximo de itens por lista nos parciais.

# ==========================
# LIMPEZA (de limpeza.py)
# ==========================
RE_TIMECODE = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\b')
RE_BRACKETS = re.compile(r'\[(?:aplausos|música|risos|music|applause|laughs|inaudível).*?\]', re.I)

def limpar_texto_bruto(texto: str) -> str:
    """Remove timecodes, marcações e espaçamento excessivo."""
    texto = RE_TIMECODE.sub("", texto)
    texto = RE_BRACKETS.sub("", texto)
    return re.sub(r'\s+', ' ', texto).strip()

# ==========================
# PROMPTS (de prompts.py)
# ==========================
PROMPTS: Dict[str, str] = {}

# ========= BLOCO =========
PROMPTS["MINERAR_ESTILO_BLOCO"] = """
Você é um analista de estilo. Analise APENAS o trecho abaixo e responda em JSON **válido** (sem markdown, sem explicações).
Idioma de saída: {{idioma|pt-BR}}.

Objetivo: extrair sinais de estilo do autor.

REGRAS:
- Responda SOMENTE um JSON; nada de texto extra.
- Se não tiver evidência, use null ou [].
- Limite cada lista ao máximo de {{max_itens|10}} itens, ordenados por relevância.
- Não invente; baseie-se no trecho fornecido.
- Priorize detectar estrutura de piada (setup → incongruência → punch) e aponte frases candidatas a punch em "estruturas_piada.exemplo".
- Se detectar "lista de três" ou "callback", reflita em "ritmo_comico" e "estruturas_piada.formato".

SCHEMA DE RESPOSTA (copie a estrutura exatamente):
{
  "tom": "string | null",
  "humor": "string | null",
  "ritmo": "string | null",
  "ritmo_comico": "setup_curto_punch_rapido|punch_tardio|lista_de_tres|escada|improviso|misto|null",
  "estruturas_piada": [
    {"formato": "setup_punch|ironia_seca|hiperbole|comparacao_absurda|callback|anti_humor|sarcasmo|observacional",
     "exemplo": "string",
     "marcadores_lexicais": ["string", "string"]}
  ],
  "gatilhos_comicos": [
    {"tipo": "incongruencia|tabu|insulto|auto_depreciacao|escatologia|política|absurdo",
     "intensidade": "baixa|media|alta",
     "exemplo": "string"}
  ],
  "moldes_frasais": [
    {"molde": "Sabe o que é pior? ...", "uso": "transição_para_punch|abrir_setup|fechar_com_zombaria"}
  ],
  "vicios_expressao": [{"texto": "string", "exemplo": "string"}],
  "marcadores_discurso": [{"texto": "string", "frequencia_estimada": "baixa|media|alta"}],
  "bordoes": [{"texto": "string", "exemplo": "string"}],
  "interjeicoes": [{"texto": "string"}],
  "temas_recorrentes": [{"tema": "string"}],
  "pontuacoes_enfase": {
    "caixa_alta": "baixa|media|alta|null",
    "pausas_elongadas": "baixa|media|alta|null"
  },
  "exemplos_representativos": ["string"],
  "confianca_global": 0.0
}

TRECHO:
{{trecho}}
"""

# ========= FUSÃO =========
PROMPTS["MINERAR_ESTILO_FUSAO"] = """
Você é um consolidador de estilo. Receberá várias análises parciais (JSONs) do mesmo autor.
Saída: um ÚNICO JSON **válido** (sem markdown), idioma {{idioma|pt-BR}}.

TAREFA:
- Unificar campos mantendo consistência; deduplicar itens (case-insensitive, trim).
- Agregar relevância: priorize o que aparece com mais recorrência entre análises.
- Não invente itens novos; use apenas o que estiver nos insumos.
- Limite cada lista ao máximo de {{max_itens|15}} itens, ordenados por relevância.
- Forneça um campo de "confianca_global" (0–1) considerando concordância entre parciais.
- Se houver conflito, escolha o consenso; se não houver, mantenha as duas visões com nota breve em "observacoes".
- Agregue “estruturas_piada”, “gatilhos_comicos” e “moldes_frasais” somando recorrência; deduplique por forma e sinônimos.

SCHEMA FINAL (copie a estrutura exatamente):
{
  "tom": "string | null",
  "humor": "string | null",
  "ritmo": "string | null",
  "ritmo_comico": "setup_curto_punch_rapido|punch_tardio|lista_de_tres|escada|improviso|misto|null",
  "estruturas_piada": [{"formato": "string", "exemplo": "string", "marcadores_lexicais": ["string"], "peso": 0.0}],
  "gatilhos_comicos": [{"tipo": "string", "intensidade": "baixa|media|alta", "exemplo": "string", "peso": 0.0}],
  "moldes_frasais": [{"molde": "string", "uso": "string", "peso": 0.0}],
  "vicios_expressao": [{"texto": "string", "exemplo": "string"}],
  "marcadores_discurso": [{"texto": "string", "peso": 0.0}],
  "bordoes": [{"texto": "string", "exemplo": "string", "peso": 0.0}],
  "interjeicoes": [{"texto": "string", "peso": 0.0}],
  "temas_recorrentes": [{"tema": "string", "peso": 0.0}],
  "pontuacoes_enfase": {
    "caixa_alta": "baixa|media|alta|null",
    "pausas_elongadas": "baixa|media|alta|null"
  },
  "exemplos_representativos": ["string"],
  "observacoes": "string | null",
  "confianca_global": 0.0
}

INSUMOS (lista de JSONs parciais):
{{analises}}
"""

# ==========================
# PromptEngine
# ==========================
@dataclass
class PromptEngine:
    model: str = DEFAULT_MODEL
    system_prompt: str = "Você é um especialista em análise de estilo."
    api_key_env: str = "OPENAI_API_KEY"

    def __post_init__(self):
        # Carrega .env se disponível
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except Exception:
            pass
        # Valida API key
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Variável {self.api_key_env} não encontrada. Configure seu .env com {self.api_key_env}=..."
            )
        # Instancia cliente OpenAI
        from openai import OpenAI  # type: ignore
        self._client = OpenAI(api_key=api_key)

    # Suporte a {{var|default}} e {{var}} além de ${var}
    @staticmethod
    def _render_mustache(template: str, vars: Dict[str, Any]) -> str:
        def repl(match):
            key = match.group(1)
            default = match.group(2)
            val = vars.get(key, default if default is not None else "")
            return str(val)
        return re.sub(r"\{\{(\w+)(?:\|([^}]+))?\}\}", repl, template)

    def preencher_prompt(self, chave: str, variaveis: Dict[str, Any]) -> str:
        if chave not in PROMPTS:
            raise KeyError(f"Prompt '{chave}' não encontrado.")
        template = PROMPTS[chave]
        # 1) mustache {{x|def}}  2) Template ${x}
        temp = self._render_mustache(template, variaveis)
        return Template(temp.replace("{{", "${").replace("}}", "}")).safe_substitute(**variaveis)

    def gerar(self, chave: str, variaveis: Dict[str, Any]) -> str:
        prompt = self.preencher_prompt(chave, variaveis)
        force_json = chave.startswith("MINERAR_")

        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2 if force_json else 0.7,
        )
        # Tenta ativar response_format JSON quando aplicável
        if force_json:
            try:
                kwargs["response_format"] = {"type": "json_object"}  # pode não estar disponível em SDK antigo
            except Exception:
                pass

        resp = self._client.chat.completions.create(**kwargs)  # type: ignore
        return (resp.choices[0].message.content or "").strip()

# ==========================
# StyleMiner (pipeline)
# ==========================
@dataclass
class StyleMiner:
    # Diretórios/arquivos
    base_dir: Optional[Path] = None
    limpas_dir: Optional[Path] = None
    parciais_dir: Optional[Path] = None
    saida_final: Optional[Path] = None

    # Execução
    max_chars: int = 1500
    engine: Optional[PromptEngine] = None
    salvar_parciais: bool = True
    idioma: str = DEFAULT_IDIOMA
    max_itens: int = DEFAULT_MAX_ITENS
    clean_first: bool = False  # usar limpeza adicional antes da blocagem

    def __post_init__(self):
        # Define caminhos padrão se não informados
        if self.base_dir is None:
            # arquivo normalmente em .../src/ → sobe 2 níveis → .../agente_template/
            self.base_dir = Path(__file__).resolve().parents[1]
        if self.limpas_dir is None:
            self.limpas_dir = self.base_dir / "dados" / "limpas"
        if self.parciais_dir is None:
            self.parciais_dir = self.base_dir / "dados" / "parciais"
        if self.saida_final is None:
            self.saida_final = self.base_dir / "dados" / "stylebook.json"

        self.parciais_dir.mkdir(parents=True, exist_ok=True)
        self.saida_final.parent.mkdir(parents=True, exist_ok=True)

        if self.engine is None:
            self.engine = PromptEngine()

    # ---------- utilidades ----------
    @staticmethod
    def _strip_code_fences(payload: str) -> str:
        txt = payload.strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.I | re.M)
        return txt

    @staticmethod
    def _json_load_safely(payload: str) -> Any:
        try:
            txt = StyleMiner._strip_code_fences(payload)
            return json.loads(txt)
        except Exception:
            return {"_erro_parse_json": True, "_amostra_resposta": (payload or "")[:1000]}

    @staticmethod
    def _dividir_em_blocos(texto: str, max_chars: int) -> List[str]:
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

    # ---------- etapas ----------
    def carregar_corpus(self) -> str:
        arquivos = sorted(self.limpas_dir.glob("*.txt"))
        textos = []
        for p in arquivos:
            t = p.read_text(encoding="utf-8", errors="ignore")
            if self.clean_first:
                t = limpar_texto_bruto(t)
            textos.append(t)
        corpus = "\n\n".join(textos).strip()
        if not corpus:
            raise RuntimeError(
                f"Nenhum texto encontrado em {self.limpas_dir}. "
                "Coloque suas transcrições limpas (.txt) nessa pasta."
            )
        print(f"📖 Corpus de {len(arquivos)} arquivo(s) | tamanho ≈ {len(corpus)} chars")
        return corpus

    def analisar_por_blocos(self, corpus: str) -> List[Dict[str, Any]]:
        blocos = self._dividir_em_blocos(corpus, max_chars=self.max_chars)
        print(f"🔹 {len(blocos)} bloco(s) (≈ {sum(map(len, blocos))} chars no total)")

        analises: List[Dict[str, Any]] = []
        for i, bloco in enumerate(blocos, 1):
            print(f"  → Bloco {i}/{len(blocos)} (≈ {len(bloco)} chars)…")
            try:
                resp = self.engine.gerar("MINERAR_ESTILO_BLOCO", {
                    "trecho": bloco,
                    "idioma": self.idioma,
                    "max_itens": self.max_itens,
                })
                data = self._json_load_safely(resp)
            except Exception as e:
                data = {"_erro_chamada_ia": True, "_mensagem": str(e)}

            analises.append(data)
            if self.salvar_parciais:
                parcial_fp = self.parciais_dir / f"stylebook_parcial_{i:02}.json"
                parcial_fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"    ✅ Parcial: {parcial_fp}")
        return analises

    def fundir_analises(self, analises: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("🔧 Fundindo análises parciais…")
        analises_texto = json.dumps(analises, ensure_ascii=False, indent=2)
        try:
            resp = self.engine.gerar("MINERAR_ESTILO_FUSAO", {
                "analises": analises_texto,
                "idioma": self.idioma,
                "max_itens": max(self.max_itens, 15),
            })
            final = self._json_load_safely(resp)
        except Exception as e:
            final = {"_erro_fusao": True, "_mensagem": str(e)}

        if isinstance(final, dict):
            final.setdefault("versao", "2.0-blocos")
            final["gerado_em"] = datetime.utcnow().isoformat()
            final.setdefault("_fonte", "fusão_de_blocos")
        else:
            final = {
                "_erro_formato": True,
                "_amostra": str(final)[:800],
                "versao": "2.0-blocos",
                "gerado_em": datetime.utcnow().isoformat(),
                "_fonte": "fusão_de_blocos",
            }
        return final

    def salvar_final(self, stylebook: Dict[str, Any]) -> Path:
        self.saida_final.write_text(json.dumps(stylebook, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Stylebook: {self.saida_final}")
        return self.saida_final

    # ---------- orquestrador ----------
    def rodar(self) -> Path:
        corpus = self.carregar_corpus()
        analises = self.analisar_por_blocos(corpus)
        final = self.fundir_analises(analises)
        return self.salvar_final(final)

# ==========================
# StyleGenerator (de gerador.py)
# ==========================
@dataclass
class StyleGenerator:
    base_dir: Optional[Path] = None
    saida_final: Optional[Path] = None  # stylebook.json

    def __post_init__(self):
        if self.base_dir is None:
            self.base_dir = Path(__file__).resolve().parents[1]
        if self.saida_final is None:
            self.saida_final = self.base_dir / "dados" / "stylebook.json"
        self.saida_final.parent.mkdir(parents=True, exist_ok=True)

    def carregar_stylebook(self) -> Dict[str, Any]:
        if self.saida_final.exists():
            return json.loads(self.saida_final.read_text(encoding="utf-8"))
        return {}

    def montar_contexto_estilo(self, sb: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extrai partes úteis do stylebook para prompts de geração.
        """
        if sb is None:
            sb = self.carregar_stylebook()
        return {
            "tom": sb.get("tom"),
            "humor": sb.get("humor"),
            "ritmo": sb.get("ritmo"),
            "ritmo_comico": sb.get("ritmo_comico"),
            "moldes_de_piada": [m.get("molde") for m in sb.get("moldes_frasais", []) if isinstance(m, dict) and m.get("molde")],
            "estruturas_piada": [e.get("formato") for e in sb.get("estruturas_piada", []) if isinstance(e, dict) and e.get("formato")],
            "gatilhos_comicos": [g.get("tipo") for g in sb.get("gatilhos_comicos", []) if isinstance(g, dict) and g.get("tipo")],
            "marcadores": [m.get("texto") for m in sb.get("marcadores_discurso", []) if isinstance(m, dict) and m.get("texto")],
            "bordoes": [b.get("texto") for b in sb.get("bordoes", []) if isinstance(b, dict) and b.get("texto")],
            "interjeicoes": [i.get("texto") for i in sb.get("interjeicoes", []) if isinstance(i, dict) and i.get("texto")],
            "pausas": (sb.get("pontuacoes_enfase") or {}).get("pausas_elongadas")
        }

# ==========================
# CLI
# ==========================
def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Clonagem de estilo (arquivo único).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # minerar
    ap_mine = sub.add_parser("minerar", help="Executa pipeline de mineração e gera stylebook.json")
    ap_mine.add_argument("--max_chars", type=int, default=4000, help="Tamanho máximo de cada bloco (chars).")
    ap_mine.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Modelo OpenAI (ex.: gpt-4o, gpt-4o-mini).")
    ap_mine.add_argument("--idioma", type=str, default=DEFAULT_IDIOMA, help="Idioma de saída (ex.: pt-BR, en-US, es-ES).")
    ap_mine.add_argument("--max_itens", type=int, default=DEFAULT_MAX_ITENS, help="Máximo de itens por lista nos parciais.")
    ap_mine.add_argument("--clean_first", action="store_true", help="Aplicar limpeza adicional antes da blocagem.")
    ap_mine.add_argument("--no_partials", action="store_true", help="Não salvar parciais.")
    # caminhos
    ap_mine.add_argument("--base_dir", type=str, default="", help="Raiz do agente (onde existe 'dados/').")
    ap_mine.add_argument("--limpas_dir", type=str, default="", help="Pasta com .txt limpos.")
    ap_mine.add_argument("--parciais_dir", type=str, default="", help="Pasta para salvar parciais.")
    ap_mine.add_argument("--saida_final", type=str, default="", help="Caminho do stylebook.json final.")

    # contexto
    ap_ctx = sub.add_parser("contexto", help="Extrai e imprime/salva contexto do stylebook para uso em prompts")
    ap_ctx.add_argument("--base_dir", type=str, default="", help="Raiz do agente (onde existe 'dados/').")
    ap_ctx.add_argument("--saida_final", type=str, default="", help="Caminho do stylebook.json.")
    ap_ctx.add_argument("--save", action="store_true", help="Salvar contexto em dados/contexto_estilo.json")

    return ap

def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.cmd == "minerar":
        engine = PromptEngine(model=args.model)
        base_dir = Path(args.base_dir).resolve() if args.base_dir else None
        limpas_dir = Path(args.limpas_dir).resolve() if args.limpas_dir else None
        parciais_dir = Path(args.parciais_dir).resolve() if args.parciais_dir else None
        saida_final = Path(args.saida_final).resolve() if args.saida_final else None

        miner = StyleMiner(
            base_dir=base_dir,
            limpas_dir=limpas_dir,
            parciais_dir=parciais_dir,
            saida_final=saida_final,
            max_chars=args.max_chars,
            engine=engine,
            salvar_parciais=not args.no_partials,
            idioma=args.idioma,
            max_itens=args.max_itens,
            clean_first=args.clean_first,
        )
        print(f"🚀 Minerando | modelo={args.model} | max_chars={args.max_chars} | idioma={args.idioma}")
        print(f"📂 LIMPAS:   {miner.limpas_dir}")
        print(f"📂 PARCIAIS: {miner.parciais_dir}")
        print(f"📝 SAÍDA:    {miner.saida_final}")
        miner.rodar()

    elif args.cmd == "contexto":
        base_dir = Path(args.base_dir).resolve() if args.base_dir else None
        saida_final = Path(args.saida_final).resolve() if args.saida_final else None
        gen = StyleGenerator(base_dir=base_dir, saida_final=saida_final)
        ctx = gen.montar_contexto_estilo()
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
        if args.save:
            destino = (gen.base_dir / "dados" / "contexto_estilo.json")
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"💾 Contexto salvo em: {destino}")

if __name__ == "__main__":
    main()
