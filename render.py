"""Genera las imágenes de los posts con el diseño de la marca.

Todo se dibuja al doble de resolución y se reduce al final, así líneas y círculos
quedan suavizados. Las coordenadas se escriben en el espacio de 1080 px y pasan por s().
"""
from __future__ import annotations

import datetime as dt
import io
import math
import re
from functools import lru_cache
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

import brand as B
import horarios
import kerning

S = 2  # supersampling
T = B.THEME


def s(v: float) -> int:
    return int(round(v * S))


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    file, weight = T["fonts"][kind]
    f = ImageFont.truetype(str(B.FONTS / file), s(size))
    if weight:
        f.set_variation_by_name(weight)
    f.pf_path = str(B.FONTS / file)  # para leer su kerning
    return f


def kern(f, a: str, b: str) -> float:
    path = getattr(f, "pf_path", None)
    return kerning.kern(path, f.size, a, b) if path else 0.0


SLANT = math.tan(math.radians(7))  # inclinación del estilo "impacto"


def slanted(x, y, w, h):
    """Paralelogramo inclinado 7° (coordenadas en el espacio de 1080 px, ya escaladas)."""
    k = h * SLANT
    return [(s(x + k), s(y)), (s(x + w + k), s(y)), (s(x + w), s(y + h)), (s(x), s(y + h))]


def case(text: str) -> str:
    return text.upper() if T["upper"] else text


# ---------------------------------------------------------------- pintura de texto

@lru_cache(maxsize=64)
def gold_gradient(w: int, h: int) -> Image.Image:
    """Degradé vertical dorado: brillo arriba, oro al centro, sombra abajo."""
    col = Image.new("RGB", (1, h))
    stops = [(0.0, B.ACENTO_CLARO), (0.45, B.ACENTO), (1.0, B.ACENTO_OSCURO)]
    for y in range(h):
        t = y / max(h - 1, 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                col.putpixel((0, y), tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    return col.resize((w, h))


def paint(d, xy, text, f, fill):
    """d.text con kerning, que además acepta fill=B.DEGRADE para texto con el degradé del acento."""
    if len(text) > 1 and getattr(f, "pf_path", None):
        x, y = xy
        for i, ch in enumerate(text):
            _paint_one(d, (x, y), ch, f, fill)
            x += f.getlength(ch) + (kern(f, ch, text[i + 1]) if i + 1 < len(text) else 0)
        return
    _paint_one(d, xy, text, f, fill)


def _paint_one(d, xy, text, f, fill):
    if fill != B.DEGRADE:
        d.text(xy, text, font=f, fill=fill)
        return
    x, y = int(xy[0]), int(xy[1])
    left, top, right, bottom = f.getbbox(text)
    if right <= 0 or bottom <= top:  # espacios: nada que pintar
        return
    mask = Image.new("L", (right, bottom), 0)
    ImageDraw.Draw(mask).text((0, 0), text, font=f, fill=255)
    fill_img = Image.new("RGB", (right, bottom), B.ACENTO)
    fill_img.paste(gold_gradient(right, bottom - top), (0, top))  # el degradé cubre solo la altura del glifo
    d.canvas.paste(fill_img, (x, y), mask)


def klen(text: str, f) -> float:
    """Ancho real del texto con kerning, en píxeles del lienzo."""
    return f.getlength(text) + sum(kern(f, a, b) for a, b in zip(text, text[1:]))


def tracked_len(text: str, f, tracking: float) -> float:
    return klen(text, f) + s(tracking) * max(len(text) - 1, 0)


def tracked(d, xy, text, f, fill, tracking=3.0):
    """Texto con espaciado entre letras (etiquetas en mayúsculas)."""
    x, y = xy
    for i, ch in enumerate(text):
        _paint_one(d, (x, y), ch, f, fill)
        x += f.getlength(ch) + s(tracking) + (kern(f, ch, text[i + 1]) if i + 1 < len(text) else 0)
    return x


# ---------------------------------------------------------------- utilidades de texto

def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if f.getlength(trial) <= s(width) or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_text(text: str, kind: str, width: int, max_lines: int, start: int, minimum: int):
    """Busca el tamaño de letra más grande con el que el texto cabe en max_lines."""
    for size in range(start, minimum - 1, -2):
        f = font(kind, size)
        lines = wrap(text, f, width)
        if len(lines) <= max_lines and all(f.getlength(l) <= s(width) for l in lines):
            return f, lines, size
    f = font(kind, minimum)
    lines = wrap(text, f, width)[:max_lines]
    lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return f, lines, minimum


def _norm(word: str) -> str:
    return re.sub(r"[^\wáéíóúüñ]", "", word.lower())


def draw_rich_lines(d, lines, f, x, y, leading, color, highlight=(), hl_color=B.DEGRADE):
    """Dibuja líneas palabra por palabra pintando en dorado las palabras destacadas."""
    hl = {_norm(w) for phrase in highlight for w in phrase.split()}
    space = f.getlength(" ")
    for line in lines:
        cx = s(x)
        for word in line.split(" "):
            paint(d, (cx, s(y)), word, f, hl_color if _norm(word) in hl else color)
            cx += klen(word, f) + space
        y += leading
    return y


def text_w(text, f) -> float:
    return klen(text, f) / S


# ---------------------------------------------------------------- elementos de marca

@lru_cache(maxsize=4)
def _spotlight(w: int, h: int) -> Image.Image:
    """Fondo negro con un foco cálido arriba, como un estadio de noche."""
    base = Image.new("RGB", (w, h), B.NEGRO)
    glow = Image.new("RGB", (w, h), B.FOCO)
    # el centro del degradé radial queda a un 25 % de la altura
    mask = Image.radial_gradient("L").resize((int(w * 1.6), int(h * 1.6)))
    mask = mask.point(lambda v: 255 - v).crop((int(w * 0.3), int(h * 0.55), int(w * 1.3), int(h * 1.55)))
    return Image.composite(glow, base, mask)


# Foto de estadio que va muy tenue detrás de los posts (dict de photos.find_photo o None).
# Se fija con set_background() antes de renderizar; su crédito va en el caption.
BACKGROUND: dict | None = None


def set_background(photo: dict | None) -> None:
    global BACKGROUND
    BACKGROUND = photo


@lru_cache(maxsize=4)
def _stadium_backdrop(path: str, w: int, h: int) -> Image.Image:
    """Estadio desaturado, teñido de dorado oscuro y casi transparente sobre el negro."""
    ph = ImageOps.grayscale(Image.open(path))
    ph = ImageOps.fit(ph, (w, h), Image.LANCZOS, centering=(0.5, 0.45))
    tinted = ImageOps.colorize(ph, black=B.NEGRO, white=B.TINTE)
    img = Image.blend(_spotlight(w, h), tinted, 0.30)
    # más oscuro arriba (marca) y abajo (texto), un poco más visible al centro
    shade = _gradient_mask(w, h, [(0, 150), (0.22, 40), (0.6, 70), (1, 210)])
    return Image.composite(Image.new("RGB", (w, h), B.NEGRO), img, shade)


def canvas(size=B.POST_SIZE):
    if BACKGROUND:
        img = _stadium_backdrop(str(BACKGROUND["path"]), s(size[0]), s(size[1])).copy()
    else:
        img = _spotlight(s(size[0]), s(size[1])).copy()
    d = ImageDraw.Draw(img)
    d.canvas = img  # paint() necesita la imagen para pegar el degradé dorado
    return img, d


def pitch_pattern(d, size=B.POST_SIZE):
    """Líneas de cancha muy tenues: círculo central y área, cortados por el borde."""
    w, h = size
    lw = s(2)
    cx, cy, r = w + 40, h * 0.62, 330
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], outline=B.LINEA, width=lw)
    d.line([s(cx), 0, s(cx), s(h)], fill=B.LINEA, width=lw)
    d.rectangle([s(-10), s(h * 0.30), s(170), s(h * 0.30 + 400)], outline=B.LINEA, width=lw)
    d.rectangle([s(-10), s(h * 0.30 + 120), s(60), s(h * 0.30 + 280)], outline=B.LINEA, width=lw)
    d.arc([s(170 - 90), s(h * 0.30 + 110), s(170 + 90), s(h * 0.30 + 290)], -70, 70, fill=B.LINEA, width=lw)


def speedlines(d, right, y, length=300, color=None, gap=22):
    """Líneas de velocidad: franjas inclinadas que se acortan, ancladas a la derecha."""
    color = color or B.ACENTO
    for i, (frac, hh) in enumerate(((1.0, 14), (0.72, 9), (0.5, 6), (0.32, 4))):
        w = length * frac
        d.polygon(slanted(right - w - i * 6, y + i * gap, w, hh), fill=color if i % 2 == 0 else B.TEXTO)


def frame(d, size=B.POST_SIZE):
    """Marco fino con esquinas doradas (o líneas de velocidad en el estilo inclinado)."""
    w, h = size
    if T.get("slant"):
        speedlines(d, w, 10, 330, gap=15)  # arriba, sin tocar la fecha
        d.rectangle([0, s(h - 10), s(w), s(h)], fill=B.ACENTO)
        return
    m, k = 28, 44
    d.rectangle([s(m), s(m), s(w - m), s(h - m)], outline=B.LINEA, width=s(1.5))
    for cx, cy, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        d.line([s(cx), s(cy), s(cx + dx * k), s(cy)], fill=B.ACENTO, width=s(3))
        d.line([s(cx), s(cy), s(cx), s(cy + dy * k)], fill=B.ACENTO, width=s(3))


def star(d, cx, cy, r, fill=B.ACENTO):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((s(cx + rr * math.cos(a)), s(cy + rr * math.sin(a))))
    d.polygon(pts, fill=fill)


def pass_line(d, start, end, dash=18, gap=12, width=3, ball=9):
    """La firma visual: una línea de pase discontinua que termina en el balón."""
    if T.get("slant"):
        speedlines(d, end[0] + 40, end[1] + 40, 360)
        return
    (x1, y1), (x2, y2) = start, end
    length = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length - ball * 2.5:
        a, b = pos, min(pos + dash, length - ball * 2.5)
        d.line([s(x1 + ux * a), s(y1 + uy * a), s(x1 + ux * b), s(y1 + uy * b)], fill=B.ACENTO, width=s(width))
        pos += dash + gap
    d.ellipse([s(x2 - ball), s(y2 - ball), s(x2 + ball), s(y2 + ball)], fill=B.ACENTO_CLARO)


def logo_mark(d, x, y, size):
    """Escudo circular: doble anillo dorado, estrella y monograma PF.

    En el estilo inclinado se usa el logo elegido en config.json (ver logos.py).
    """
    c, r = size / 2, size / 2
    if T.get("slant"):
        import logos  # logos usa las utilidades de este módulo
        logos.LOGOS[B.LOGO](d, x, y, size)
        return
    d.ellipse([s(x), s(y), s(x + size), s(y + size)], outline=B.ACENTO, width=max(s(size * 0.045), 2))
    inner = size * 0.09
    d.ellipse([s(x + inner), s(y + inner), s(x + size - inner), s(y + size - inner)],
              outline=B.ACENTO_OSCURO, width=max(s(size * 0.012), 1))
    star(d, x + c, y + size * 0.26, size * 0.065, B.ACENTO_CLARO)
    f = font("score", int(size * 0.40))
    left, top, right, bottom = f.getbbox("PF")
    paint(d, (s(x + c) - f.getlength("PF") / 2, s(y + c + size * 0.07) - (top + bottom) / 2), "PF", f, B.DEGRADE)


def header(d, date: dt.date | None = None, size=B.POST_SIZE, right: str | None = None):
    if T.get("slant"):
        logo_mark(d, 54, 52, 96)  # la insignia lleva detalle: un poco más grande
        f = font("display", 40)
        paint(d, (s(166), s(78)), "PASE", f, B.TEXTO)
        paint(d, (s(166) + klen("PASE ", f), s(78)), "FILTRADO", f, B.ACENTO)
    else:
        logo_mark(d, 62, 62, 76)
        f = font("label", 25)
        tracked(d, (s(156), s(88)), "PASE FILTRADO", f, B.TEXTO, 5)
    label = right or date_label(date or dt.date.today())  # en carruseles: número de slide
    fd = font("label", 22)
    tracked(d, (s(size[0] - 62) - tracked_len(label, fd, 3), s(90)), label, fd, B.SECUNDARIO, 3)


MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def date_label(date: dt.date) -> str:
    return f"{date.day:02d} {MESES[date.month - 1]} {date.year}"


def chip(d, x, y, text, filled=False, dot=None, bg=None):
    """Etiqueta de categoría: borde dorado, o dorada rellena para última hora."""
    f = font("label", 22)
    pad, h = 20, 46
    dot_w = 22 if dot else 0
    w = tracked_len(text, f, 4) / S + pad * 2 + dot_w
    if T.get("slant"):
        # bloque inclinado: rojo con texto blanco; las especiales en blanco con texto negro
        f = font("label", 26)
        w = tracked_len(text, f, 2) / S + pad * 2 + dot_w + h * SLANT
        d.polygon(slanted(x, y, w, h), fill=B.TEXTO if filled else B.ACENTO)
        if dot:
            d.ellipse([s(x + pad), s(y + h / 2 - 6), s(x + pad + 12), s(y + h / 2 + 6)], fill=B.ACENTO)
        _, top, _, bottom = f.getbbox("A")
        tracked(d, (s(x + pad + dot_w + h * SLANT / 2), s(y + h / 2) - (top + bottom) / 2), text, f,
                B.NEGRO if filled else B.SOBRE_ACENTO, 2)
        return w
    if filled:
        d.rectangle([s(x), s(y), s(x + w), s(y + h)], fill=B.ACENTO)
    else:
        d.rectangle([s(x), s(y), s(x + w), s(y + h)], fill=bg, outline=B.ACENTO, width=s(2))
    if dot:
        d.ellipse([s(x + pad), s(y + h / 2 - 6), s(x + pad + 12), s(y + h / 2 + 6)], fill=dot)
    _, top, _, bottom = f.getbbox("A")
    tracked(d, (s(x + pad + dot_w), s(y + h / 2) - (top + bottom) / 2), text, f, B.SOBRE_ACENTO if filled else B.ACENTO, 4)
    return w


def footer(d, source: str | None = None, size=B.POST_SIZE, label="FUENTE"):
    w, h = size
    y = h - 96
    d.line([s(62), s(y - 24), s(w - 62), s(y - 24)], fill=B.LINEA, width=s(1.5))
    f = font("label", 21)
    if source:
        tracked(d, (s(62), s(y)), f"{label} · {source.upper()}", f, B.SECUNDARIO, 3)
    fh = font("label", 24)
    paint(d, (s(w - 62) - fh.getlength(B.HANDLE), s(y - 3)), B.HANDLE, fh, B.DEGRADE)


def finish(img, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    final = img.resize((img.width // S, img.height // S), Image.LANCZOS)
    # Instagram solo acepta JPEG por la API de publicación
    final.save(out, "JPEG", quality=93, optimize=True, progressive=True)
    return out


def base(size=B.POST_SIZE, date=None, right=None):
    img, d = canvas(size)
    if not BACKGROUND:
        pitch_pattern(d, size)
    frame(d, size)
    header(d, date, size, right)
    return img, d


# ---------------------------------------------------------------- plantillas

def render_news(post: dict, out: Path) -> Path:
    """Noticia / fichaje / última hora: titular grande, bajada y fuente."""
    W, H = B.POST_SIZE
    img, d = base()
    category = post.get("category", "NOTICIA").upper()
    breaking = category in ("ÚLTIMA HORA", "POLÉMICA")

    cw = chip(d, 62, 196, category, filled=breaking, dot=B.ROJO if breaking else None)
    if post.get("competition"):
        tracked(d, (s(62 + cw + 20), s(209)), post["competition"].upper(), font("label", 22), B.SECUNDARIO, 3)
    status_badge(d, post.get("status"), W - 62, 219)

    start, minimum = T["headline_size"]
    f, lines, size = fit_text(case(post["headline"]), "display", W - 124, 5, start, minimum)
    y = draw_rich_lines(d, lines, f, 62, 300, size * T["leading"], B.TEXTO, post.get("highlight", []))

    # separador dorado + bajada
    y += size * 0.22 + 22
    d.line([s(62), s(y), s(62 + 70), s(y)], fill=B.ACENTO, width=s(3))
    d.ellipse([s(62 + 80), s(y - 4), s(62 + 88), s(y + 4)], fill=B.ACENTO)
    y += 40
    if post.get("summary"):
        fs, slines, ssize = fit_text(post["summary"], "body", W - 124, 4, 38, 28)
        for line in slines:
            d.text((s(62), s(y)), line, font=fs, fill=(214, 208, 196))
            y += ssize * 1.38

    if y < H - 330:
        pass_line(d, (W - 420, H - 160), (W - 96, max(y + 30, H - 320)))
    footer(d, post.get("source"))
    return finish(img, out)


STATUS_LABELS = {"AVANZADO": "EN NEGOCIACIÓN", "RUMOR": "RUMOR"}


def status_badge(d, status: str | None, right: float, cy: float):
    """Semáforo de fichajes: sello dorado si está confirmado, etiqueta gris si no."""
    if status == "CONFIRMADO":
        stamp(d, "PASE COMPLETADO", right, cy)
    elif status in STATUS_LABELS:
        f = font("label", 20)
        txt = STATUS_LABELS[status]
        w = tracked_len(txt, f, 4) / S + 40 + 22
        x = right - w
        d.rectangle([s(x), s(cy - 23), s(right), s(cy + 23)], outline=B.SECUNDARIO, width=s(2))
        d.ellipse([s(x + 18), s(cy - 6), s(x + 30), s(cy + 6)], fill=B.ACENTO if status == "AVANZADO" else B.SECUNDARIO)
        _, top, _, bottom = f.getbbox("A")
        tracked(d, (s(x + 40), s(cy) - (top + bottom) / 2), txt, f, B.TEXTO, 4)


def stamp(d, text: str, right: float, cy: float, angle: float = 6):
    """Sello tipo timbre, levemente girado: la firma de los fichajes confirmados."""
    f = font("label", 24)
    tw = tracked_len(text, f, 4)
    pad, check = s(22), s(30)
    w, h = int(tw + pad * 3 + check), s(66)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rectangle([0, 0, w - 1, h - 1], outline=B.ACENTO + (255,), width=s(3))
    ld.rectangle([s(6), s(6), w - 1 - s(6), h - 1 - s(6)], outline=B.ACENTO_OSCURO + (255,), width=s(1.5))
    # visto bueno dibujado (no depende de la fuente)
    cx0, cy0 = pad, h / 2
    ld.line([(cx0, cy0), (cx0 + check * 0.35, cy0 + check * 0.35), (cx0 + check, cy0 - check * 0.4)],
            fill=B.ACENTO_CLARO + (255,), width=s(5), joint="curve")
    _, top, _, bottom = f.getbbox("A")
    x = cx0 + check + pad * 0.8
    for ch in text:
        ld.text((x, h / 2 - (top + bottom) / 2), ch, font=f, fill=B.ACENTO_CLARO + (255,))
        x += f.getlength(ch) + s(4)
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    d.canvas.paste(layer, (int(s(right) - layer.width), int(s(cy) - layer.height / 2)), layer)


@lru_cache(maxsize=None)
def _flag_disc(code: str, px: int) -> Image.Image:
    """Bandera recortada en círculo (RGBA) de px de diámetro."""
    img = Image.open(B.ROOT / "assets" / "banderas" / f"{code}.png").convert("RGBA")
    img = ImageOps.fit(img, (px, px), Image.LANCZOS)
    mask = Image.new("L", (px * 4, px * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, px * 4 - 1, px * 4 - 1], fill=255)
    img.putalpha(mask.resize((px, px), Image.LANCZOS))
    return img


def flag(d, code: str, cx: float, cy: float, size: float):
    """Bandera circular con anillo dorado, al estilo de los escudos."""
    disc = _flag_disc(code, s(size))
    d.canvas.paste(disc, (s(cx) - disc.width // 2, s(cy) - disc.height // 2), disc)
    r = size / 2
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], outline=B.ACENTO, width=max(s(size * 0.06), 2))


def flag_row(d, codes: list[str], cx: float, cy: float, size: float, gap: float = 6):
    """Banderas en fila, centradas en cx."""
    total = len(codes) * size + (len(codes) - 1) * gap
    x = cx - total / 2 + size / 2
    for code in codes:
        flag(d, code, x, cy, size)
        x += size + gap


def _team_color(c: str | None):
    if not c or not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return B.SECUNDARIO
    rgb = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return B.SECUNDARIO if sum(rgb) < 120 else rgb  # colores casi negros no se ven


CREST_CACHE = B.ROOT / "assets" / "cache" / "escudos"


@lru_cache(maxsize=None)
def crest(logo: str | None, team_id: str | None) -> Image.Image | None:
    """Escudo del equipo (PNG transparente de ESPN), guardado en caché local."""
    if not logo or not team_id or not logo.startswith("https://a.espncdn.com/"):
        return None
    path = CREST_CACHE / f"{team_id}.png"
    if not path.exists():
        try:
            r = requests.get(logo, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            r.raise_for_status()
            Image.open(io.BytesIO(r.content)).verify()
        except (requests.RequestException, OSError) as e:
            print(f"[escudos] {team_id}: {e}")
            return None
        CREST_CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    img = Image.open(path).convert("RGBA")
    img = img.crop(img.getbbox() or (0, 0, img.width, img.height))
    alpha = img.getchannel("A")
    solid = alpha.point(lambda v: 255 if v > 128 else 0)
    if ImageStat.Stat(img.convert("L"), mask=solid).mean[0] < 70:
        # escudo oscuro (Juventus, etc.): contorno marfil para que no se pierda en el fondo negro
        pad = max(6, img.width // 36)
        big = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        big.paste(img, (pad, pad))
        ring = big.getchannel("A").filter(ImageFilter.MaxFilter(pad * 2 + 1))
        backing = Image.new("RGBA", big.size, B.TEXTO + (255,))
        backing.putalpha(ring)
        img = Image.alpha_composite(backing, big)
    return img


def paste_crest(d, team: dict, cx: float, cy: float, box: float) -> bool:
    """Pega el escudo centrado dentro de un cuadrado de lado box. False si no hay escudo."""
    img = crest(team.get("logo"), team.get("id"))
    if img is None:
        return False
    k = s(box) / max(img.width, img.height)
    img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    d.canvas.paste(img, (s(cx) - img.width // 2, s(cy) - img.height // 2), img)
    return True


def initials(name: str) -> str:
    words = [w for w in re.split(r"[\s-]+", name) if w and w[0].isalnum()]
    return "".join(w[0] for w in words[:3]).upper() or "?"


def crest_badge(d, team: dict, cx: float, cy: float, r: float):
    """Escudo dentro de una placa oscura con doble anillo dorado, como el logo de la marca."""
    if T.get("slant"):
        # el color del club como segundo color, sobre la base negra
        ring = _team_color(team.get("color"))
        if ring == B.SECUNDARIO or sum(ring) > 690:
            ring = B.TEXTO
        d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=B.GRAFITO, outline=ring, width=s(r * 0.06))
    else:
        d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=B.GRAFITO, outline=B.ACENTO, width=s(r * 0.04))
        ri = r * 0.89
        d.ellipse([s(cx - ri), s(cy - ri), s(cx + ri), s(cy + ri)], outline=B.ACENTO_OSCURO, width=max(s(r * 0.012), 1))
    if not paste_crest(d, team, cx, cy, r * 1.18):
        # sin escudo: iniciales sobre el color del club
        rc = r * 0.7
        d.ellipse([s(cx - rc), s(cy - rc), s(cx + rc), s(cy + rc)], fill=_team_color(team.get("color")))
        txt = initials(team.get("full_name") or team["name"])
        f, _, _ = fit_text(txt, "score", int(rc * 1.5), 1, int(r * 0.8), 20)
        _, top, _, bottom = f.getbbox(txt)
        paint(d, (s(cx) - f.getlength(txt) / 2, s(cy) - (top + bottom) / 2), txt, f, B.TEXTO)


def mini_crest(d, team: dict | None, cx: float, cy: float, size: float):
    """Escudo pequeño para las listas; si falta, un punto con el color del club."""
    if team and paste_crest(d, team, cx, cy, size):
        return
    r = size * 0.22
    color = _team_color(team.get("color")) if team else B.SECUNDARIO
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=color)


def render_result(match: dict, out: Path) -> Path:
    """Resultado: escudos en anillos dorados, marcador al centro y goleadores de cada lado."""
    W, H = B.POST_SIZE
    img, d = base(date=match.get("date"))
    cw = chip(d, 62, 196, (match.get("kicker") or "RESULTADO FINAL").upper())
    tracked(d, (s(62 + cw + 20), s(209)), match["competition"].upper(), font("label", 22), B.SECUNDARIO, 3)

    home, away = match["home"], match["away"]
    hs, as_ = int(home["score"]), int(away["score"])
    cy, r = 470, 148
    sides = ((home, hs, as_, 228), (away, as_, hs, W - 228))

    # escudos y nombres
    for team, score, other, cx in sides:
        crest_badge(d, team, cx, cy, r)
        fn, nlines, nsize = fit_text(case(team["name"]), "display", 330, 2, 58, 34)
        ny = cy + r + 34
        for line in nlines:
            paint(d, (s(cx) - fn.getlength(line) / 2, s(ny)), line, fn, B.TEXTO if score >= other else B.SECUNDARIO)
            ny += nsize * 1.12

    # marcador central: el ganador en dorado
    fsc, _, _ = fit_text(f"{hs}{as_}", "score", 210, 1, 150, 80)
    dash = font("score", 90)
    gap = s(14)
    parts = ((str(hs), fsc, B.DEGRADE if hs > as_ else B.TEXTO), ("–", dash, B.SECUNDARIO),
             (str(as_), fsc, B.DEGRADE if as_ > hs else B.TEXTO))
    x = s(W / 2) - (sum(f.getlength(txt) for txt, f, _ in parts) + gap * 2) / 2
    for txt, f, fill in parts:
        _, top, _, bottom = f.getbbox(txt)
        paint(d, (x, s(cy) - (top + bottom) / 2), txt, f, fill)
        x += f.getlength(txt) + gap
    fl = font("label", 22)
    tracked(d, (s(W / 2) - tracked_len("FINAL", fl, 5) / 2, s(cy + 100)), "FINAL", fl, B.SECUNDARIO, 5)

    # goleadores: los de cada equipo bajo su escudo
    goals = match.get("goals", [])
    y = cy + r + 34 + 2 * 58 * 1.12 + 24
    if goals:
        d.line([s(62), s(y), s(W - 62), s(y)], fill=B.LINEA, width=s(1.5))
        y += 30
        tracked(d, (s(W / 2) - tracked_len("GOLES", fl, 5) / 2, s(y)), "GOLES", fl, B.ACENTO, 5)
        y += 50
        fg = font("body", 28)
        col_w = W / 2 - 62 - 30
        for idx, (team, _, _, _) in enumerate(sides):
            gy = y
            names = {team.get("full_name"), team.get("name")}
            for g in [g for g in goals if g["team"] in names][:6]:
                player = g["player"]
                line = f"{player}  {g['minute']}" if idx == 0 else f"{g['minute']}  {player}"
                while fg.getlength(line) > s(col_w) and len(player) > 4:
                    player = player[:-2].rstrip() + "…"
                    line = f"{player}  {g['minute']}" if idx == 0 else f"{g['minute']}  {player}"
                gx = s(62) if idx == 0 else s(W - 62) - fg.getlength(line)
                d.text((gx, s(gy)), line, font=fg, fill=(214, 208, 196))
                gy += 44
                if gy > H - 190:
                    break
    else:
        pass_line(d, (90, H - 200), (W - 96, H - 300))
    footer(d, match.get("venue"), label="ESTADIO")
    return finish(img, out)


def render_list(title: str, subtitle: str, rows: list[dict], out: Path, kind="agenda") -> Path:
    """Lista de partidos: agenda del día (hora) o resultados del día (marcador)."""
    W, H = B.POST_SIZE
    img, d = base()
    chip(d, 62, 196, subtitle.upper())
    f, lines, size = fit_text(case(title), "display", W - 124, 1, 112, 64)
    draw_rich_lines(d, lines, f, 62, 268, size, B.TEXTO, [title.split()[-1]])
    y = 268 + size * 1.3 + 24

    rows = rows[:10]
    cols, col_w = [], 80
    if kind == "agenda" and rows and rows[0].get("kickoff"):
        # columnas de horario: banderas arriba, una hora por grupo de países en cada fila
        cols = horarios.groups(rows[0]["kickoff"])
        x0 = W - 62 - len(cols) * col_w
        for j, g in enumerate(cols):
            cx = x0 + col_w * (j + 0.5)
            codes = g["countries"]
            for k in range(0, len(codes), 2):
                flag_row(d, codes[k:k + 2], cx, y + 14 + (k // 2) * 30, 26, 4)
        y += 14 + ((max(len(g["countries"]) for g in cols) + 1) // 2) * 30 + 6
    n_comps = len({r.get("competition") for r in rows})
    row_h = max(60, min(108, (H - 170 - y - n_comps * 46) / max(len(rows), 1)))
    last_comp = None
    fr = font("strong", int(min(32 if cols else 40, row_h * 0.4)))
    fs = font("score", int(min(48, row_h * 0.46)))
    for r in rows:
        if r.get("competition") != last_comp:
            last_comp = r.get("competition")
            tracked(d, (s(62), s(y + 6)), last_comp.upper(), font("label", 20), B.ACENTO, 4)
            y += 44
        d.rectangle([s(62), s(y), s(W - 62), s(y + row_h - 12)], fill=B.GRAFITO)
        d.rectangle([s(62), s(y), s(62 + 4), s(y + row_h - 12)], fill=B.ACENTO)
        mid = s(y + (row_h - 12) / 2)
        _, ft, _, fb = fr.getbbox("Ag")
        ty = mid - (ft + fb) / 2
        cs = (row_h - 12) * 0.62  # tamaño del escudo pequeño
        my = y + (row_h - 12) / 2
        if kind == "agenda" and cols:
            ftime = font("strong", 26)
            _, tt, _, tb = ftime.getbbox("0")
            for j, g in enumerate(cols):
                local = r["kickoff"].astimezone(horarios.ZoneInfo(horarios.PAISES[g["countries"][0]]))
                west = r["kickoff"].astimezone(horarios.ZoneInfo(horarios.PAISES["mx"]))
                hhmm = local.strftime("%H:%M")
                cx = x0 + col_w * (j + 0.5)
                paint(d, (s(cx) - ftime.getlength(hhmm) / 2, mid - (tt + tb) / 2), hhmm, ftime, B.NUMEROS)
                if local.date() > west.date():
                    fp = font("label", 13)
                    paint(d, (s(cx) + ftime.getlength(hhmm) / 2 - s(4), mid - (tt + tb) / 2 - s(10)), "+1", fp, B.SECUNDARIO)
            x = 84
            mini_crest(d, r.get("home_team"), x + cs / 2, my, cs)
            x += cs + 12
            txt = f"{r['home']}  vs  "
            d.text((s(x), ty), txt, font=fr, fill=B.TEXTO)
            x += text_w(txt, fr)
            mini_crest(d, r.get("away_team"), x + cs / 2, my, cs)
            d.text((s(x + cs + 12), ty), r["away"], font=fr, fill=B.TEXTO)
        elif kind == "agenda":
            paint(d, (s(90), ty), r.get("time", ""), fr, B.NUMEROS)
            x = 90 + text_w("00:00", fr) + 40
            mini_crest(d, r.get("home_team"), x + cs / 2, my, cs)
            x += cs + 14
            txt = f"{r['home']}  vs  "
            d.text((s(x), ty), txt, font=fr, fill=B.TEXTO)
            x += text_w(txt, fr)
            mini_crest(d, r.get("away_team"), x + cs / 2, my, cs)
            d.text((s(x + cs + 14), ty), r["away"], font=fr, fill=B.TEXTO)
        else:
            score = f"{r['home_score']} – {r['away_score']}"
            sw = fs.getlength(score) / S
            _, st, _, sb = fs.getbbox("0")
            cx = W / 2
            paint(d, (s(cx - sw / 2), mid - (st + sb) / 2), score, fs, B.NUMEROS)
            hx = cx - sw / 2 - 20 - cs
            mini_crest(d, r.get("home_team"), hx + cs / 2, my, cs)
            d.text((s(hx - 16) - fr.getlength(r["home"]), ty), r["home"], font=fr, fill=B.TEXTO)
            ax = cx + sw / 2 + 20
            mini_crest(d, r.get("away_team"), ax + cs / 2, my, cs)
            d.text((s(ax + cs + 16), ty), r["away"], font=fr, fill=B.TEXTO)
        y += row_h
        if y > H - 170:
            break
    footer(d, "ESPN")
    return finish(img, out)


def render_stat(post: dict, out: Path) -> Path:
    """Dato: una cifra enorme y su contexto."""
    W, H = B.POST_SIZE
    img, d = base()
    chip(d, 62, 196, "DATO")
    number = str(post["number"])
    f, _, size = fit_text(number, "score", W - 124, 1, 400, 160)
    _, top, _, bottom = f.getbbox(number)
    paint(d, (s(56), s(300) - top), number, f, B.DEGRADE)
    y = 300 + (bottom - top) / S + 56
    start, minimum = T["headline_size"]
    fh, lines, hsize = fit_text(case(post["headline"]), "display", W - 124, 4, int(start * 0.8), minimum)
    y = draw_rich_lines(d, lines, fh, 62, y, hsize * T["leading"], B.TEXTO, post.get("highlight", []))
    y += hsize * 0.22 + 18
    if post.get("summary"):
        fs, slines, ssize = fit_text(post["summary"], "body", W - 124, 3, 34, 26)
        for line in slines:
            d.text((s(62), s(y)), line, font=fs, fill=(214, 208, 196))
            y += ssize * 1.38
    if y < H - 320:
        pass_line(d, (W - 380, H - 160), (W - 96, H - 300))
    footer(d, post.get("source"))
    return finish(img, out)


def render_avatar(out: Path, size=1080) -> Path:
    """Foto de perfil: el logo centrado (Instagram la recorta en círculo)."""
    if T.get("slant"):
        img = Image.new("RGB", (s(size), s(size)), (0, 0, 0))
        d = ImageDraw.Draw(img)
        d.canvas = img
        logo_mark(d, size * 0.02, size * 0.02, size * 0.96)
        return finish(img, out)
    img, d = canvas((size, size))
    logo_mark(d, size * 0.14, size * 0.14, size * 0.72)
    return finish(img, out)


def render_cover(label: str, out: Path, size=1080) -> Path:
    """Portada de historia destacada: anillo dorado con el nombre de la sección."""
    img, d = canvas((size, size))
    r, c = size * 0.36, size / 2
    d.ellipse([s(c - r), s(c - r), s(c + r), s(c + r)], outline=B.ACENTO, width=s(10))
    star(d, c, c - r * 0.48, size * 0.035, B.ACENTO_CLARO)
    f, lines, _ = fit_text(case(label), "display", int(r * 1.45), 1, 150, 60)
    _, top, _, bottom = f.getbbox(lines[0])
    paint(d, (s(c) - f.getlength(lines[0]) / 2, s(c + size * 0.03) - (top + bottom) / 2), lines[0], f, B.DEGRADE)
    return finish(img, out)


# ---------------------------------------------------------------- portada con foto

def _gradient_mask(w: int, h: int, stops: list[tuple[float, int]]) -> Image.Image:
    """Máscara vertical: lista de (posición 0-1, opacidad 0-255) interpolada."""
    col = Image.new("L", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        for (t0, a0), (t1, a1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                col.putpixel((0, y), int(a0 + (a1 - a0) * (t - t0) / max(t1 - t0, 1e-6)))
                break
    return col.resize((w, h))


def _photo_canvas(photo_path: Path, focus_y: float, size=B.POST_SIZE):
    """Foto recortada a 4:5 con degradados negros arriba (marca) y abajo (texto)."""
    W, H = s(size[0]), s(size[1])
    ph = Image.open(photo_path).convert("RGB")
    k = max(W / ph.width, H / ph.height)
    ph = ph.resize((int(ph.width * k + 0.5), int(ph.height * k + 0.5)), Image.LANCZOS)
    top = int((ph.height - H) * focus_y)
    left = (ph.width - W) // 2
    img = ph.crop((left, top, left + W, top + H))
    shade = Image.new("RGB", (W, H), B.NEGRO)
    img = Image.composite(shade, img, _gradient_mask(W, H, [(0, 190), (0.18, 0), (0.33, 0), (0.6, 235), (1, 255)]))
    d = ImageDraw.Draw(img)
    d.canvas = img
    return img, d


def scoreboard(d, match: dict, y: float, h: float = 116):
    """Barra de marcador: escudo, nombre, resultado dorado al centro, nombre, escudo."""
    W = B.POST_SIZE[0]
    x0, x1 = 62, W - 62
    region = d.canvas.crop((s(x0), s(y), s(x1), s(y + h)))
    region = Image.blend(region, Image.new("RGB", region.size, B.NEGRO), 0.72)
    d.canvas.paste(region, (s(x0), s(y)))
    d.rectangle([s(x0), s(y), s(x1), s(y + h)], outline=B.ACENTO, width=s(2))
    home, away = match["home"], match["away"]
    hs, as_ = int(home["score"]), int(away["score"])
    cy = y + h / 2
    fsc = font("score", 76)
    score = f"{hs} – {as_}"
    sw = fsc.getlength(score) / S
    _, top, _, bottom = fsc.getbbox("0")
    paint(d, (s(W / 2 - sw / 2), s(cy) - (top + bottom) / 2), score, fsc, B.NUMEROS)
    cs = h * 0.66
    side_w = (x1 - x0) / 2 - sw / 2 - 40 - cs - 20
    for team, score_, other, left in ((home, hs, as_, True), (away, as_, hs, False)):
        fn, lines, _ = fit_text(case(team["name"]), "display", int(side_w), 1, 44, 26)
        name = lines[0]
        _, nt, _, nb = fn.getbbox(name)
        color = B.TEXTO if score_ >= other else B.SECUNDARIO
        if left:
            mini_crest(d, team, x0 + 22 + cs / 2, cy, cs)
            paint(d, (s(x0 + 22 + cs + 18), s(cy) - (nt + nb) / 2), name, fn, color)
        else:
            mini_crest(d, team, x1 - 22 - cs / 2, cy, cs)
            paint(d, (s(x1 - 22 - cs - 18) - fn.getlength(name), s(cy) - (nt + nb) / 2), name, fn, color)


def kicker_block(d, x, y, text: str) -> float:
    """Etiqueta de impacto grande (ej. "LOCURA EN ANFIELD"): bloque rojo inclinado con letras blancas."""
    f, lines, size = fit_text(text.upper(), "display", 760, 1, 50, 30)
    h = size * 1.32
    w = text_w(lines[0], f) + 44 + h * SLANT
    if T.get("slant"):
        d.polygon(slanted(x, y, w, h), fill=B.ACENTO)
    else:
        d.rectangle([s(x), s(y), s(x + w), s(y + h)], fill=B.ACENTO)
    _, top, _, bottom = f.getbbox(lines[0])
    paint(d, (s(x + 22 + h * SLANT / 2), s(y + h / 2) - (top + bottom) / 2), lines[0], f, B.SOBRE_ACENTO)
    return w


def render_photo(post: dict, photo: dict, out: Path, match: dict | None = None, focus_y: float = 0.0) -> Path:
    """Portada con foto libre: marca arriba, marcador (opcional) y titular abajo, crédito en el pie."""
    W, H = B.POST_SIZE
    img, d = _photo_canvas(photo["path"], focus_y)
    frame(d)
    header(d, post.get("date"))

    start, minimum = T["headline_size"]
    f, lines, size = fit_text(case(post["headline"]), "display", W - 124, 3, int(start * 0.8), minimum)
    text_h = size * T["leading"] * len(lines)
    y_title = H - 172 - text_h
    if match:
        y_board = y_title - 116 - 34
        y_chip = y_board - 66
        scoreboard(d, match, y_board)
    else:
        y_chip = y_title - 74
    category = post.get("category", "NOTICIA").upper()
    breaking = category in ("ÚLTIMA HORA", "POLÉMICA")
    if post.get("kicker"):
        y_chip -= 14
        cw = kicker_block(d, 62, y_chip, post["kicker"])
        ty = y_chip + 22
    else:
        cw = chip(d, 62, y_chip, category, filled=breaking, dot=B.ROJO if breaking else None, bg=B.NEGRO)
        ty = y_chip + 13
    if post.get("competition"):
        tracked(d, (s(62 + cw + 20), s(ty)), post["competition"].upper(), font("label", 22), B.TEXTO, 3)
    draw_rich_lines(d, lines, f, 62, y_title, size * T["leading"], B.TEXTO, post.get("highlight", []))

    # pie: crédito de la foto (lo exige la licencia) y usuario
    y = H - 96
    d.line([s(62), s(y - 24), s(W - 62), s(y - 24)], fill=B.LINEA, width=s(1.5))
    fc = font("label", 17)
    credit = f"FOTO · {photo['author']} / {photo['license']}".upper()
    while tracked_len(credit, fc, 2) > s(W - 124 - 260) and len(credit) > 10:
        credit = credit[:-2].rstrip() + "…"
    tracked(d, (s(62), s(y + 3)), credit, fc, B.SECUNDARIO, 2)
    fh = font("label", 24)
    paint(d, (s(W - 62) - fh.getlength(B.HANDLE), s(y - 3)), B.HANDLE, fh, B.DEGRADE)
    return finish(img, out)
