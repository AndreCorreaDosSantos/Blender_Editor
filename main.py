import os, subprocess
from pathlib import Path

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
BASE = Path(__file__).resolve().parent
SCRIPT = BASE / "animar.py"  # <<< cuidado com 'python' (sem 'pythoon')

env = os.environ.copy()
env["PROJECT_NAME"] = "Projeto_Teste_01"

# FORMATOS:
#   16x9  → YouTube (horizontal), Facebook horizontal
#   9x16  → TikTok, Instagram Reels, YouTube Shorts (vertical)
#   1x1   → Instagram feed quadrado
#   4x5   → Instagram feed retrato
#   LxA   → Personalizado (ex.: "1080x1920")
env["FORMAT"] = "9x16"   # mude aqui
env["FPS"] = "60"        # 24=cinema | 30=redes | 60=fluído
env["WAIT_INPUT"] = "0"  # "1" para pausar no final

args = [BLENDER, "--factory-startup", "--python", str(SCRIPT)]
print("▶️ Rodando:", " ".join(f'"{a}"' if " " in a else a for a in args))
subprocess.run(args, check=True, env=env)
