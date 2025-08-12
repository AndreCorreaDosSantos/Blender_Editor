# animar.py — prepara ambiente para edição no VSE (sem debugpy)
import os
import bpy

# ========= Pause opcional (abre console no Windows e espera Enter) =========
WAIT_INPUT = os.getenv("WAIT_INPUT", "0") == "1"
if WAIT_INPUT:
    try:
        bpy.ops.wm.console_toggle()  # no Windows abre a System Console (para ver prints/input)
    except Exception:
        pass

# ========= Novo projeto (limpo) =========
# Não usamos read_factory_settings(use_empty=True) para não apagar workspaces.
print("🆕 Ambiente iniciado via --factory-startup.")

# ========= Nome do projeto =========
nome_projeto = os.getenv("PROJECT_NAME", "Projeto_Teste_01")
bpy.context.scene["project_name"] = nome_projeto
print(f"📛 Nome do projeto definido: {nome_projeto}")

# ========= Garantir workspace 'Video Editing' =========
ws_name = "Video Editing"
ws = bpy.data.workspaces.get(ws_name)
if ws is None:
    try:
        bpy.ops.workspace.append_activate(idname=ws_name)
        ws = bpy.data.workspaces.get(ws_name)
        print("🧩 Workspace 'Video Editing' anexado.")
    except Exception as e:
        print("⚠️ Não foi possível anexar o workspace:", e)

try:
    if ws:
        bpy.context.window.workspace = ws
        print("🎛️ Workspace 'Video Editing' ativado.")
    else:
        # Fallback: troca uma área para o Sequencer
        for area in bpy.context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.type = 'SEQUENCE_EDITOR'
                print("🔁 Fallback: área trocada para SEQUENCE_EDITOR.")
                break
except Exception as e:
    print("⚠️ Falha ao ativar workspace:", e)

# ========= Preparar o VSE =========
scene = bpy.context.scene
scene.sequence_editor_create()
print("🎬 VSE inicializado e pronto.")

# ========= Parâmetros base do projeto =========
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.fps = 30
print(f"📐 Resolução: {scene.render.resolution_x}x{scene.render.resolution_y} @ {scene.render.fps}fps")

print("✅ Ambiente preparado. Pronto para importar mídia.")

# Canvas + Preview lado a lado
scr = bpy.context.window.screen
for area in scr.areas:
    if area.type == 'SEQUENCE_EDITOR':
        for space in area.spaces:
            if space.type == 'SEQUENCE_EDITOR':
                space.view_type = 'SEQUENCER_PREVIEW'   # timeline + preview
                try:
                    space.show_safe_areas = True        # guias (opcional)
                except:
                    pass

# Formatos comuns (escolha um)
def set_format(x, y, fps=30):
    r = bpy.context.scene.render
    r.resolution_x = x
    r.resolution_y = y
    r.fps = fps
    print(f"📐 {x}x{y} @ {fps}fps")

# 16:9 horizontal (YouTube)
#set_format(1920, 1080, 30)

# 9:16 vertical (Reels/TikTok) -> use este no lugar do de cima se quiser
set_format(1080, 1920, 30)

# 1:1 quadrado
# set_format(1080, 1080, 30)

# 4:5 (Instagram feed)
# set_format(1080, 1350, 30)



if WAIT_INPUT:
    try:
        #input("⏸️ Pressione Enter para continuar...")
        print("Seguindo")
    except Exception:
        pass
