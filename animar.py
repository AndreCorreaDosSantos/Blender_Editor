# animar.py — prepara ambiente para edição no VSE (base estável)
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

# ========= Preparar o VSE =========
scene = bpy.context.scene
scene.sequence_editor_create()
print("🎬 VSE inicializado e pronto.")

# ========= Tentar ativar workspace 'Video Editing' (caminho que funcionou pra você) =========
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
        # Fallback: troca uma área para o Sequencer (simples e confiável)
        for area in bpy.context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.type = 'SEQUENCE_EDITOR'
                print("🔁 Fallback: área trocada para SEQUENCE_EDITOR.")
                break
except Exception as e:
    print("⚠️ Falha ao ativar workspace:", e)

# ========= Canvas + Preview lado a lado (igual antes) =========
scr = bpy.context.window.screen
for area in scr.areas:
    if area.type == 'SEQUENCE_EDITOR':
        for space in area.spaces:
            if space.type == 'SEQUENCE_EDITOR':
                try:
                    space.view_type = 'SEQUENCER_PREVIEW'   # timeline + preview
                    space.show_safe_areas = True            # guias (opcional)
                except Exception:
                    pass
        break

# ========= Formato/FPS vindos do main.py =========
fmt = os.getenv("FORMAT", "16x9").lower()
fps = int(os.getenv("FPS", "30"))

def set_format(x, y, fps_val=30):
    r = bpy.context.scene.render
    r.resolution_x = x
    r.resolution_y = y
    r.fps = fps_val
    print(f"📐 {x}x{y} @ {fps_val}fps")

def apply_format(fmt_str, fps_val):
    presets = {
        "16x9": (1920, 1080, "YouTube/Facebook horizontal"),
        "9x16": (1080, 1920, "TikTok/Reels/Shorts vertical"),
        "1x1":  (1080, 1080, "Instagram feed quadrado"),
        "4x5":  (1080, 1350, "Instagram feed retrato"),
    }
    if fmt_str in presets:
        w, h, desc = presets[fmt_str]
        set_format(w, h, fps_val)
        print(f"➡️  Preset aplicado: {desc} (FORMAT='{fmt_str}')")
    else:
        # Tenta "LxA" (ex.: "1080x1920")
        try:
            w, h = fmt_str.replace(" ", "").split("x")
            set_format(int(w), int(h), fps_val)
            print(f"➡️  Formato personalizado aplicado (FORMAT='{fmt_str}')")
        except Exception:
            # fallback seguro
            w, h, desc = presets["16x9"]
            set_format(w, h, fps_val)
            print(f"➡️  Fallback: {desc} (FORMAT='16x9')")

apply_format(fmt, fps)

print("✅ Ambiente preparado. Pronto para importar mídia.")

# ================== Template de trilhas ao estilo CapCut (com override) ==================
def _get_sequencer_ctx():
    """Garante uma área do tipo SEQUENCE_EDITOR e devolve (win, area, region)."""
    wm = bpy.context.window_manager
    win = bpy.context.window or (wm.windows[0] if wm.windows else None)
    if not win:
        raise RuntimeError("Sem janela ativa (GUI).")

    scr = win.screen
    area = next((a for a in scr.areas if a.type == 'SEQUENCE_EDITOR'), None)
    if area is None:
        # converte a primeira área para SEQUENCE_EDITOR
        area = scr.areas[0]
        reg0 = next((r for r in area.regions if r.type == 'WINDOW'), None)
        with bpy.context.temp_override(window=win, area=area, region=reg0):
            area.type = 'SEQUENCE_EDITOR'

    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    # Sequencer + Preview
    space = next((s for s in area.spaces if s.type == 'SEQUENCE_EDITOR'), None)
    if space:
        try:
            space.view_type = 'SEQUENCER_PREVIEW'
            space.show_safe_areas = True
        except:
            pass
    return win, area, region

def _label_channel(channel: int, name: str, color=(0.2, 0.2, 0.2), frames=12):
    """Cria um strip de COR curto, mudo e travado, apenas para nomear o canal."""
    scn = bpy.context.scene
    win, area, region = _get_sequencer_ctx()
    with bpy.context.temp_override(window=win, area=area, region=region, scene=scn):
        bpy.ops.sequencer.effect_strip_add(type='COLOR', frame_start=1, frame_end=frames, channel=channel)
        s = scn.sequence_editor.sequences_all[-1]
        s.name = f"[{name}]"
        s.mute = True
        s.lock = True
        s.select = False
        try:
            s.color = color  # nem sempre disponível, ok se falhar
        except:
            pass
    print(f"🏷️ Canal {channel} rotulado como {name}")

def setup_tracks_template():
    template = [
        (6, "Overlays/Títulos", (0.55, 0.35, 0.85)),
        (5, "Vídeo 2",          (0.25, 0.55, 1.00)),
        (4, "Vídeo 1",          (0.25, 0.55, 1.00)),
        (2, "Áudio SFX",        (0.10, 0.75, 0.35)),
        (1, "Áudio Música",     (0.00, 0.60, 0.25)),
    ]
    for ch, name, col in template:
        _label_channel(ch, name, col)
    # focar no início onde ficam os rótulos
    win, area, region = _get_sequencer_ctx()
    with bpy.context.temp_override(window=win, area=area, region=region):
        try:
            bpy.ops.sequencer.view_all()
            bpy.ops.sequencer.view_frame()
        except:
            pass
    print("🧭 Trilhas: 6=Overlays, 4–5=Vídeo, 1–2=Áudio")

setup_tracks_template()



if WAIT_INPUT:
    try:
        input("⏸️ Pressione Enter para continuar...")
    except Exception:
        pass
