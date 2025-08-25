# ferramentas/pipeline_legendas.py
import sys
import subprocess
from pathlib import Path

# =========================
#  Descoberta de caminhos
# =========================
HERE = Path(__file__).resolve()          # .../Blender_Editor/ferramentas/pipeline_legendas.py
FERRAMENTAS = HERE.parent                # .../Blender_Editor/ferramentas

def find_project_root(start: Path) -> Path:
    """
    Sobe diretórios até encontrar a pasta 'agentes'.
    Se não achar em até 6 níveis, assume 'start.parent' (raiz padrão).
    """
    p = start
    for _ in range(6):
        if (p / "agentes").exists():
            return p
        p = p.parent
    return start.parent

BASE = find_project_root(FERRAMENTAS)    # raiz do projeto (Blender_Editor)

# Pastas/arquivos do agente template
AGENTE_DIR     = BASE / "agentes" / "agente_template"
PASTA_BRUTAS   = AGENTE_DIR / "dados" / "brutas"
PASTA_LIMPAS   = AGENTE_DIR / "dados" / "limpas"
ESTILO_SCRIPT  = AGENTE_DIR / "src" / "estilo_pipeline.py"

PASTA_LIMPAS.mkdir(parents=True, exist_ok=True)

# Garantir imports relativos ao projeto funcionem
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from agentes.agente_template.src.utils.limpeza import limpar_texto_bruto  # noqa: E402


# =========================
#  Helpers de prompt
# =========================
def prompt_menu():
    print("\n🎯 Pipeline de Legendas & Estilo")
    print("1) Baixar links")
    print("2) Baixar transcrições")
    print("3) Limpar transcrições")
    print("4) Rodar TUDO (1 → 2 → 3)")
    print("5) Pular links e rodar só transcrições + limpeza")
    print("6) Pular links e transcrições (rodar só limpeza)")
    print("7) Rodar Estilo (minerar/contexto)")
    print("8) Rodar TUDO + Estilo (1 → 2 → 3 → 7[minerar])")
    print("0) Sair")
    while True:
        op = input("👉 Escolha: ").strip()
        if op in {"0","1","2","3","4","5","6","7","8"}:
            return op
        print("❌ Opção inválida.")

def ask(msg, default=None, allowed=None):
    tip = f" (Enter={default})" if default is not None else ""
    while True:
        val = input(f"{msg}{tip}: ").strip()
        if not val and default is not None:
            return str(default)
        if allowed and val not in allowed:
            print(f"❌ Valor inválido. Opções: {', '.join(allowed)}")
            continue
        return val

def prompt_bool(msg, default=False):
    d = "s" if default else "n"
    val = input(f"{msg} [s/n] (Enter={d}): ").strip().lower()
    if not val:
        return default
    return val in {"s","sim","y","yes"}


def prompt_estilo_args():
    """
    Coleta interativamente os argumentos do estilo_pipeline.py
    (compatível com teu CLI).
    """
    print("\n🧠 Estilo — escolha o modo:")
    print("1) minerar  (gera stylebook.json a partir das transcrições limpas)")
    print("2) contexto (gera/imprime contexto do stylebook)")
    cmd = "minerar" if ask("👉 Escolha [1-2]", "1", {"1","2"}) == "1" else "contexto"

    # Defaults alinhados com teu estilo_pipeline.py
    model     = ask("💬 Modelo OpenAI", "gpt-4o-mini")
    idioma    = ask("🌐 Idioma de saída", "pt-BR")

    # Monta a linha base
    args = [cmd, "--model", model, "--idioma", idioma]

    # Caminhos (por padrão enviamos --base_dir apontando ao agente)
    usar_padrao = prompt_bool(f"Usar base_dir padrão? {AGENTE_DIR}", True)
    if usar_padrao:
        args += ["--base_dir", str(AGENTE_DIR)]
    else:
        base_dir = ask("Informe um --base_dir absoluto", str(AGENTE_DIR))
        args += ["--base_dir", base_dir]

    if cmd == "minerar":
        max_chars = ask("✂️  max_chars", "2000")
        max_itens = ask("📦 max_itens", "25")
        clean     = prompt_bool("Aplicar --clean_first?", False)
        no_part   = prompt_bool("Desativar parciais (--no_partials)?", False)

        args += ["--max_chars", str(max_chars), "--max_itens", str(max_itens)]
        if clean:
            args.append("--clean_first")
        if no_part:
            args.append("--no_partials")

        # Overrides opcionais de pastas/saídas
        if prompt_bool("Quer sobrescrever pastas (limpas/parciais/saida_final)?", False):
            limpas_dir   = ask("  --limpas_dir", str(PASTA_LIMPAS))
            parciais_dir = ask("  --parciais_dir", str(AGENTE_DIR / "dados" / "parciais"))
            saida_final  = ask("  --saida_final", str(AGENTE_DIR / "dados" / "stylebook.json"))
            args += ["--limpas_dir", limpas_dir, "--parciais_dir", parciais_dir, "--saida_final", saida_final]

    else:  # contexto
        if prompt_bool("Salvar JSON do contexto em dados/contexto_estilo.json? (--save)", True):
            args.append("--save")
        # Override opcional de stylebook
        if prompt_bool("Quer sobrescrever o caminho do stylebook.json? (--saida_final)", False):
            saida_final = ask("  --saida_final", str(AGENTE_DIR / "dados" / "stylebook.json"))
            args += ["--saida_final", saida_final]

    return args


# =========================
#  Ações (subprocess/IO)
# =========================
def run_baixar_links():
    script = FERRAMENTAS / "baixar_links.py"
    if not script.exists():
        print(f"❌ Não encontrei {script}")
        return
    print(f"▶️  Executando: {script}")
    subprocess.run([sys.executable, str(script)])

def run_baixar_transcricoes():
    script = FERRAMENTAS / "baixar_transcricoes.py"
    if not script.exists():
        print(f"❌ Não encontrei {script}")
        return
    print(f"▶️  Executando: {script}")
    subprocess.run([sys.executable, str(script)])

def limpar_transcricoes():
    print(f"📂 Procurando arquivos em: {PASTA_BRUTAS.resolve()}")
    arquivos = list(PASTA_BRUTAS.glob("*.txt"))
    if not arquivos:
        print("⚠️ Nenhum arquivo .txt encontrado em BRUTAS!")
        return
    print(f"➡️ Limpando {len(arquivos)} arquivos...\n")

    for a in arquivos:
        print(f"🔍 Lendo {a.name}...")
        texto = a.read_text(encoding="utf-8", errors="ignore")
        limpo = limpar_texto_bruto(texto)
        (PASTA_LIMPAS / a.name).write_text(limpo, encoding="utf-8")
        print(f"✅ {a.name} limpo e salvo.")

    print(f"\n🏁 Todos os arquivos foram salvos em: {PASTA_LIMPAS.resolve()}")

def run_estilo_pipeline(interactive=True, preset_args=None):
    if not ESTILO_SCRIPT.exists():
        print(f"❌ Não encontrei {ESTILO_SCRIPT}")
        return

    if interactive:
        args = prompt_estilo_args()
    else:
        # Defaults seguros para opção 8 (execução automática)
        args = preset_args or [
            "minerar",
            "--model", "gpt-4o-mini",
            "--idioma", "pt-BR",
            "--max_chars", "2000",
            "--max_itens", "25",
            "--base_dir", str(AGENTE_DIR),
        ]

    print(f"▶️  Executando: {ESTILO_SCRIPT} {' '.join(args)}")
    subprocess.run([sys.executable, str(ESTILO_SCRIPT), *args])


# =========================
#  Main
# =========================
def main():
    print(f"🗺️  Raiz detectada: {BASE}")
    print(f"📁 Ferramentas:     {FERRAMENTAS}")
    print(f"📁 Agente dir:      {AGENTE_DIR}")
    print(f"📁 BRUTAS:          {PASTA_BRUTAS}")
    print(f"📁 LIMPAS:          {PASTA_LIMPAS}")
    print(f"📄 Estilo script:   {ESTILO_SCRIPT}")

    while True:
        escolha = prompt_menu()
        if escolha == "0":
            print("👋 Encerrado.")
            break
        elif escolha == "1":
            run_baixar_links()
        elif escolha == "2":
            run_baixar_transcricoes()
        elif escolha == "3":
            limpar_transcricoes()
        elif escolha == "4":
            run_baixar_links()
            run_baixar_transcricoes()
            limpar_transcricoes()
        elif escolha == "5":
            run_baixar_transcricoes()
            limpar_transcricoes()
        elif escolha == "6":
            limpar_transcricoes()
        elif escolha == "7":
            run_estilo_pipeline(interactive=True)
        elif escolha == "8":
            run_baixar_links()
            run_baixar_transcricoes()
            limpar_transcricoes()
            run_estilo_pipeline(interactive=False)

if __name__ == "__main__":
    main()
