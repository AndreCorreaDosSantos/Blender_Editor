import os
from dotenv import load_dotenv
from string import Template
from openai import OpenAI
from agentes.agente_template.src.utils.prompts import PROMPTS

# 🔑 carrega as variáveis do arquivo .env
load_dotenv()


# -*- coding: utf-8 -*-
"""
motor_de_prompts.py — camada que conversa com a IA
"""


# se for usar OpenAI oficial
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def preencher_prompt(chave: str, variaveis: dict) -> str:
    """
    Substitui {{variavel}} no template pelo valor de variaveis["variavel"].
    Usa string.Template para maior robustez.
    """
    if chave not in PROMPTS:
        raise KeyError(f"Prompt '{chave}' não encontrado em prompts.py")

    template = PROMPTS[chave]

    # converte {{x}} -> $x (compatível com Template)
    template = template.replace("{{", "${").replace("}}", "}")
    return Template(template).safe_substitute(**variaveis)

def gerar(chave: str, variaveis: dict, model="gpt-4o-mini") -> str:
    """
    Gera saída da IA a partir de uma chave de prompt e variáveis.
    """
    prompt = preencher_prompt(chave, variaveis)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Você é um especialista em análise de estilo."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()
