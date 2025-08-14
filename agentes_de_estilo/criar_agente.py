# criar_agente.py
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE / "scripts"
SRC = BASE / "src"

def run(script, desc=""):
    # Mostra no console qual etapa está sendo executada
    print(f"\n➡️ {desc}...")

    # Executa o script Python passado como argumento.
    # - "subprocess.run" chama outro processo do sistema
    # - "capture_output=True" captura a saída (stdout e stderr)
    # - "text=True" converte os bytes da saída para string (UTF-8)
    result = subprocess.run(["python", str(script)], capture_output=True, text=True)

    # Se o script rodou sem erros (código de saída 0), mostra mensagem de sucesso
    if result.returncode == 0:
        print(f"✅ {desc} concluído.\n")
    else:
        # Caso contrário, mostra mensagem de erro + stderr (mensagens de erro do script)
        print(f"❌ Erro em {desc}:\n{result.stderr}\n")


def main():
    # 1) Limpar transcrições
    run(SCRIPTS / "limpar_transcricoes.py", "Limpando legendas brutas")

    # 2) Minerar estilo
    run(SRC / "minerar_estilo.py", "Gerando caderno de estilo")

    # 3) Gerar roteiro
    tema = input("🎬 Digite o tema do roteiro: ")
    result = subprocess.run(
        ["python", str(SRC / "gerador.py"), tema],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("📝 Roteiro gerado:\n")
        print(result.stdout)
    else:
        print("❌ Erro ao gerar roteiro:\n", result.stderr)

if __name__ == "__main__":
    main()
