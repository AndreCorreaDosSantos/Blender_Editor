import bpy

def _get_sequencer_ctx():
    """
    Garante que há uma área do tipo SEQUENCE_EDITOR ativa,
    e retorna (window, area, region) para usar em override.
    """
    wm = bpy.context.window_manager
    win = bpy.context.window or (wm.windows[0] if wm.windows else None)
    if not win:
        raise RuntimeError("❌ Sem janela ativa (GUI).")

    scr = win.screen
    area = next((a for a in scr.areas if a.type == 'SEQUENCE_EDITOR'), None)
    if area is None:
        # Se nenhuma área for Sequencer, converte a primeira área disponível
        area = scr.areas[0]
        reg0 = next((r for r in area.regions if r.type == 'WINDOW'), None)
        with bpy.context.temp_override(window=win, area=area, region=reg0):
            area.type = 'SEQUENCE_EDITOR'

    region = next((r for r in area.regions if r.type == 'WINDOW'), None)

    # Garante que esteja em modo de visualização SEQUENCER_PREVIEW
    space = next((s for s in area.spaces if s.type == 'SEQUENCE_EDITOR'), None)
    if space:
        try:
            space.view_type = 'SEQUENCER_PREVIEW'
            space.show_safe_areas = True
        except:
            pass

    return win, area, region


def _label_channel(channel: int, name: str, color=(0.2, 0.2, 0.2), frames=12):
    """
    Cria um strip de COR curto no canal especificado, apenas para rotulá-lo visualmente.
    O strip é mudo, travado e não interfere na edição.
    """
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
            s.color = color  # alguns builds do Blender podem não suportar
        except:
            pass
    print(f"🏷️ Canal {channel} rotulado como '{name}'")


def setup_tracks_template():
    """
    Cria a estrutura padrão de trilhas usada no estilo CapCut:
    - Overlays, Vídeo 1, Vídeo 2, Áudio SFX, Música
    Cada trilha recebe uma cor, nome e um pequeno strip para identificação.
    """
    template = [
        (6, "Overlays/Títulos", (0.55, 0.35, 0.85)),
        (5, "Vídeo 2",          (0.25, 0.55, 1.00)),
        (4, "Vídeo 1",          (0.25, 0.55, 1.00)),
        (2, "Áudio SFX",        (0.10, 0.75, 0.35)),
        (1, "Áudio Música",     (0.00, 0.60, 0.25)),
    ]
    for ch, name, col in template:
        _label_channel(ch, name, col)

    # Foca no início da timeline para o editor ver os rótulos
    win, area, region = _get_sequencer_ctx()
    with bpy.context.temp_override(window=win, area=area, region=region):
        try:
            bpy.ops.sequencer.view_all()
            bpy.ops.sequencer.view_frame()
        except:
            pass

    print("🧭 Trilhas configuradas: 6=Overlays, 4–5=Vídeo, 1–2=Áudio")
