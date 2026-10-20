"""Reel animado del resultado (1080x1920, ~10 s, MP4 H.264 con pista de audio silenciosa).

Se dibujan "estados" acumulativos con las mismas piezas de diseño de los posts (etiqueta, escudos,
marcador, cada gol, titular) y se animan con barridos inclinados entre estados y un zoom lento.
Así cada cuadro no se redibuja desde cero y el video sale en pocos segundos.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

import brand as B
import logos
import render as R
from render import case, font, paint, s

W, H = R.STORY_SIZE
FPS = 30
WIPE = 8  # cuadros que dura cada barrido


def _canvas():
    img, d = R.canvas(R.STORY_SIZE)
    R.speedlines(d, W, 10, 380, gap=15)
    R.logo_mark(d, 62, 70, 110)
    f = font("display", 54)
    paint(d, (s(196), s(96)), "PASE", f, B.TEXTO)
    paint(d, (s(196) + R.klen("PASE ", f), s(96)), "FILTRADO", f, B.ACENTO)
    d.rectangle([0, s(H - 12), s(W), s(H)], fill=B.ACENTO)
    return img, d


def _snap(img) -> Image.Image:
    return img.resize((W, H), Image.LANCZOS)


def states(m: dict, st: dict, head: dict) -> list[tuple[Image.Image, float]]:
    """Lista de (imagen, segundos en pantalla), cada una agrega algo a la anterior."""
    h, a = m["home"], m["away"]
    out = []
    img, d = _canvas()
    out.append((_snap(img), 0.5))

    # etiqueta de impacto y competición
    cw = R.kicker_block(d, 62, 250, head["etiqueta"])
    R.tracked(d, (s(62 + cw + 20), s(272)), m["competition"].upper(), font("label", 24), B.TEXTO, 3)
    out.append((_snap(img), 0.7))

    # escudos y marcador
    cy, r = 620, 175
    for team, cx in ((h, 220), (a, W - 220)):
        R.crest_badge(d, team, cx, cy, r)
        fn, lines, nsize = R.fit_text(case(team["name"]), "display", 380, 1, 60, 34)
        paint(d, (s(cx) - R.klen(lines[0], fn) / 2, s(cy + r + 28)), lines[0], fn, B.TEXTO)
    hs, as_ = int(h["score"]), int(a["score"])
    fsc = font("score", 150)
    score = f"{hs}–{as_}"
    _, top, _, bottom = fsc.getbbox("0")
    paint(d, (s(W / 2) - fsc.getlength(score) / 2, s(cy) - (top + bottom) / 2), score, fsc, B.TEXTO)
    out.append((_snap(img), 1.4))

    # goles, uno por uno
    # Instagram tapa los ~380 px de abajo con el usuario y el texto: todo debe terminar antes
    timeline = st["linea"][:7]
    y = 930
    row = 66 if len(timeline) <= 6 else 58
    fp, fsm = font("strong", 34), font("score", 34)
    for t in timeline:
        cyr = y + row / 2
        mark = t["score"].replace("-", " – ")
        bw = R.text_w(mark, fsm) + 28
        d.rectangle([s(W / 2 - bw / 2), s(cyr - 22), s(W / 2 + bw / 2), s(cyr + 22)],
                    fill=B.ACENTO if t is st.get("decisivo") else B.GRAFITO)
        _, tt, _, tb = fsm.getbbox("0")
        paint(d, (s(W / 2) - fsm.getlength(mark) / 2, s(cyr) - (tt + tb) / 2), mark, fsm, B.TEXTO)
        _, pt, _, pb = fp.getbbox("Ag")
        if t["side"] == "home":
            txt = f"{t['player']}  {t['minute']}"
            d.text((s(W / 2 - bw / 2 - 22) - fp.getlength(txt), s(cyr) - (pt + pb) / 2), txt, font=fp, fill=B.TEXTO)
        else:
            txt = f"{t['minute']}  {t['player']}"
            d.text((s(W / 2 + bw / 2 + 22), s(cyr) - (pt + pb) / 2), txt, font=fp, fill=B.TEXTO)
        y += row
        out.append((_snap(img), 0.45))

    # titular
    start, minimum = B.THEME["headline_size"]
    f, lines, size = R.fit_text(case(head["titular"]), "display", W - 124, 3, 92, 60)
    ty = max(y + 40, 1540 - size * B.THEME["leading"] * len(lines))
    R.draw_rich_lines(d, lines, f, 62, ty, size * B.THEME["leading"], B.TEXTO, head.get("destacar", []))
    out.append((_snap(img), 2.6))

    # cierre
    end, de = _canvas()
    logo = logos._insignia(s(520))
    end.paste(logo, (s(W / 2) - logo.width // 2, s(420)), logo)
    fc = font("display", 92)
    for k, line in enumerate((case("Fútbol sin relleno"), case("Síguenos"))):
        paint(de, (s(W / 2) - R.klen(line, fc) / 2, s(1040 + k * 110)), line, fc, B.ACENTO if k else B.TEXTO)
    fh = font("display", 64)
    paint(de, (s(W / 2) - R.klen(B.HANDLE, fh) / 2, s(1300)), B.HANDLE, fh, B.TEXTO)
    out.append((_snap(end), 1.6))
    return out


def _wipe_mask(progress: float) -> Image.Image:
    """Máscara de barrido inclinado (7°, como el resto de la marca), de izquierda a derecha."""
    m = Image.new("L", (W, H), 0)
    k = H * R.SLANT
    x = -k + (W + 2 * k) * progress
    ImageDraw.Draw(m).polygon([(-k, 0), (x + k, 0), (x, H), (-k, H)], fill=255)
    return m


def frames(seq: list[tuple[Image.Image, float]]):
    total = sum(int(sec * FPS) for _, sec in seq)
    n = 0
    prev = None
    for img, sec in seq:
        count = int(sec * FPS)
        for i in range(count):
            frame = img
            if prev is not None and i < WIPE:
                t = (i + 1) / WIPE
                frame = Image.composite(img, prev, _wipe_mask(1 - (1 - t) ** 3))  # entra rápido y frena
            # zoom lento de todo el video
            z = 1 + 0.045 * n / max(total - 1, 1)
            cw, ch = W / z, H / z
            frame = frame.crop((int((W - cw) / 2), int((H - ch) / 2), int((W + cw) / 2), int((H + ch) / 2)))
            yield frame.resize((W, H), Image.BILINEAR)
            n += 1
        prev = img


def render_reel(m: dict, st: dict, head: dict, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",  # Instagram espera una pista de audio
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in frames(states(m, st, head)):
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg no pudo generar el reel")
    return out
