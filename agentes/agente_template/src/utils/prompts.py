PROMPTS = {}

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

SCHEMA DE RESPOSTA (copie a estrutura exatamente):
{
  "tom": "string | null",
  "humor": "string | null",
  "ritmo": "string | null",
  "vicios_expressao": [{"texto": "string", "exemplo": "string"}],
  "marcadores_discurso": [{"texto": "string", "frequencia_estimada": "baixa|media|alta"}],
  "bordoes": [{"texto": "string", "exemplo": "string"}],
  "interjeicoes": [{"texto": "string"}],
  "temas_recorrentes": [{"tema": "string"}],
  "pontuacoes_enfase": {
    "caixa_alta": "baixa|media|alta|null",
    "pausas_elongadas": "baixa|media|alta|null"
  },
  "exemplos_representativos": ["string", "string"],
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

SCHEMA FINAL (copie a estrutura exatamente):
{
  "tom": "string | null",
  "humor": "string | null",
  "ritmo": "string | null",
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
