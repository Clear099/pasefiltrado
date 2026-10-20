"""Insignia de PASE FILTRADO: estadio de noche, pizarra táctica, balón y letras de brocha.

Todo se dibuja desde cero (sin fotos de terceros), así el logo no necesita créditos.
Uso: python badge.py  → assets/brand/insignia.png (transparente) y assets/brand/perfil.jpg
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

import brand as B

SIZE = 2160          # se dibuja al doble y se reduce al final
C = SIZE / 2
R_OUT = SIZE * 0.445  # radio de la insignia
RED = (230, 22, 34)
WHITE = (246, 246, 244)
rng = random.Random(7)  # semilla fija: el logo sale idéntico cada vez


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(B.FONTS / name), size)


# ---------------------------------------------------------------- texturas

def noise(size, sigma=60, blur=0.0, stretch=1) -> Image.Image:
    """Ruido gris; stretch>1 lo estira en horizontal para que parezcan vetas de brocha."""
    w, h = size
    n = Image.effect_noise((max(1, w // stretch), h), sigma).convert("L")
    if stretch > 1:
        n = n.resize((w, h), Image.BILINEAR)
    return n.filter(ImageFilter.GaussianBlur(blur)) if blur else n


def percentile(img: Image.Image, frac: float) -> int:
    hist = img.histogram()
    total, acc = sum(hist), 0
    for v, n in enumerate(hist):
        acc += n
        if acc >= total * frac:
            return v
    return 255


def dry_brush(mask: Image.Image, amount=0.07, stretch=10) -> Image.Image:
    """Vetas de brocha seca: se elimina solo la fracción `amount` del trazo, en hilos horizontales."""
    veins = noise(mask.size, 60, blur=0.8, stretch=stretch)
    cut_at = percentile(veins, amount)
    return ImageChops.multiply(mask, veins.point(lambda v: 0 if v < cut_at else 255))


def ragged(mask: Image.Image, scale=6, strength=120) -> Image.Image:
    """Borde irregular: se suaviza el alfa, se le suma ruido de grano grueso y se vuelve a cortar."""
    soft = mask.filter(ImageFilter.GaussianBlur(scale * 0.6))
    grain = noise(mask.size, 90, blur=scale * 0.35).point(lambda v: int((v - 128) * strength / 128 + 128))
    mixed = ImageChops.add(soft, grain, scale=1.0, offset=-128)
    return mixed.point(lambda v: 255 if v > 128 else 0)


def streaks(mask: Image.Image, reach=0.06) -> Image.Image:
    """Colas de brocha: extiende el trazo hacia los lados en hilos horizontales."""
    w, h = mask.size
    small = mask.resize((max(1, int(w * reach)), h), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    hairs = noise((w, h), 95, blur=0.5, stretch=40).point(lambda v: 255 if v > 175 else 0)
    tails = ImageChops.multiply(small.point(lambda v: 255 if v > 60 else 0), hairs)
    return ImageChops.lighter(mask, tails)


# ---------------------------------------------------------------- fondo: estadio de noche

def stadium() -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), (6, 6, 7))
    d = ImageDraw.Draw(img)
    # grada: bandas horizontales con "público" (ruido) que se apagan hacia arriba
    for i in range(14):
        y = SIZE * 0.42 + i * SIZE * 0.028
        shade = int(10 + 8 * (i / 14))
        d.rectangle([0, y, SIZE, y + SIZE * 0.022], fill=(shade, shade, shade + 2))
    band = (int(SIZE * 0.42), int(SIZE * 0.82))
    crowd = noise((SIZE, band[1] - band[0]), 80, blur=2.2).point(lambda v: max(0, (v - 110) * 2))
    crowd_rgb = Image.merge("RGB", [crowd] * 3)
    fade = Image.linear_gradient("L").resize((SIZE, band[1] - band[0])).point(lambda v: int(min(v, 255 - v) * 2 * 0.25))
    img.paste(Image.composite(crowd_rgb, img.crop((0, band[0], SIZE, band[1])), fade), (0, band[0]))
    # techo de la grada (estructura oscura arriba)
    for i in range(12):
        x0 = SIZE * (-0.1 + i * 0.11)
        d.line([x0, SIZE * 0.06, x0 + SIZE * 0.25, SIZE * 0.30], fill=(20, 20, 22), width=10)
    # focos con resplandor
    glow = Image.new("L", (SIZE, SIZE), 0)
    gd = ImageDraw.Draw(glow)
    for cx in (SIZE * 0.17, SIZE * 0.83):
        cy = SIZE * 0.36
        pw, ph = SIZE * 0.115, SIZE * 0.07
        d.rectangle([cx - pw / 2 - 10, cy - ph / 2 - 10, cx + pw / 2 + 10, cy + ph / 2 + 10], fill=(28, 28, 30))
        for row in range(3):
            for col in range(5):
                x = cx - pw / 2 + pw * (col + 0.5) / 5
                y = cy - ph / 2 + ph * (row + 0.5) / 3
                r = SIZE * 0.0085
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 250))
        gd.ellipse([cx - pw, cy - ph * 1.6, cx + pw, cy + ph * 1.6], fill=170)
    glow = glow.filter(ImageFilter.GaussianBlur(SIZE * 0.05))
    img = Image.composite(Image.new("RGB", img.size, (235, 235, 240)), img, glow.point(lambda v: v * 0.55))
    # resplandor de cada foco: las luces "queman" alrededor
    bulbs = Image.new("L", (SIZE, SIZE), 0)
    bdraw = ImageDraw.Draw(bulbs)
    for cx in (SIZE * 0.17, SIZE * 0.83):
        cy = SIZE * 0.36
        pw, ph = SIZE * 0.115, SIZE * 0.07
        for row in range(3):
            for col in range(5):
                x = cx - pw / 2 + pw * (col + 0.5) / 5
                y = cy - ph / 2 + ph * (row + 0.5) / 3
                rr = SIZE * 0.011
                bdraw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=255)
    bloom = ImageChops.add(bulbs.filter(ImageFilter.GaussianBlur(8)).point(lambda v: v * 0.35),
                           bulbs.filter(ImageFilter.GaussianBlur(40)).point(lambda v: v * 0.45))
    img = ImageChops.screen(img, Image.merge("RGB", [bloom] * 3))
    # haces de luz muy tenues hacia el centro
    beams = Image.new("L", (SIZE, SIZE), 0)
    bd = ImageDraw.Draw(beams)
    for cx, sign in ((SIZE * 0.17, 1), (SIZE * 0.83, -1)):
        bd.polygon([(cx, SIZE * 0.36), (cx + sign * SIZE * 0.55, SIZE * 0.70), (cx + sign * SIZE * 0.30, SIZE * 0.80)], fill=40)
    beams = beams.filter(ImageFilter.GaussianBlur(SIZE * 0.03))
    img = Image.composite(Image.new("RGB", img.size, (200, 200, 205)), img, beams)
    return img


def grass(img: Image.Image, top: float):
    """Pasto en primer plano: briznas cortas y oscuras, más claras donde pega la luz del balón."""
    d = ImageDraw.Draw(img)
    d.rectangle([0, top, SIZE, SIZE], fill=(14, 16, 14))
    for _ in range(9000):
        x = rng.uniform(0, SIZE)
        y = rng.uniform(top - SIZE * 0.01, SIZE)
        depth = (y - top) / (SIZE - top)
        h = SIZE * (0.012 + 0.03 * depth) * rng.uniform(0.6, 1.3)
        lean = rng.uniform(-0.35, 0.35) * h
        near = 1 - min(1, abs(x - C) / (SIZE * 0.35))
        v = int(26 + 50 * near * rng.uniform(0.5, 1) + 30 * depth * rng.uniform(0, 1))
        d.line([x, y, x + lean, y - h], fill=(v, v + 6, v), width=rng.choice((2, 3, 3, 4)))


# ---------------------------------------------------------------- balón

PHI = (1 + 5 ** 0.5) / 2


def _norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v)


def _icosa():
    pts = []
    for a in (-1, 1):
        for b in (-PHI, PHI):
            pts += [(0, a, b), (a, b, 0), (b, 0, a)]
    return [_norm(p) for p in pts]


def _rot(v, ax, ay):
    x, y, z = v
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    return x, y, z


def _slerp(a, b, t):
    return _norm(tuple(a[i] * (1 - t) + b[i] * t for i in range(3)))


def ball(diameter: int) -> Image.Image:
    """Balón clásico (icosaedro truncado) con sombreado y desgaste. Devuelve RGBA."""
    D = diameter
    r = D / 2
    ico = _icosa()
    min_d = min(math.dist(a, b) for i, a in enumerate(ico) for b in ico[i + 1:])
    neigh = {i: [j for j in range(12) if j != i and math.dist(ico[i], ico[j]) < min_d * 1.01] for i in range(12)}
    ax, ay = 0.45, -0.35  # orientación para que se vea un pentágono casi de frente
    rot = [_rot(p, ax, ay) for p in ico]

    def proj(v):
        return (r + v[0] * r * 0.985, r - v[1] * r * 0.985)

    img = Image.new("RGB", (D, D), (236, 236, 232))
    d = ImageDraw.Draw(img)
    # vértices de pentágono: a 1/3 del camino hacia cada vecino del icosaedro
    pent = {(i, j): _norm(tuple(rot[i][k] * 2 / 3 + rot[j][k] / 3 for k in range(3))) for i in range(12) for j in neigh[i]}
    for i in range(12):
        if rot[i][2] < -0.05:
            continue
        verts = [pent[(i, j)] for j in neigh[i]]
        center = rot[i]
        # ordenar los vértices alrededor del centro
        ref = _norm(tuple(verts[0][k] - center[k] for k in range(3)))
        other = _norm((center[1] * ref[2] - center[2] * ref[1], center[2] * ref[0] - center[0] * ref[2], center[0] * ref[1] - center[1] * ref[0]))
        verts.sort(key=lambda v: math.atan2(sum((v[k] - center[k]) * other[k] for k in range(3)),
                                            sum((v[k] - center[k]) * ref[k] for k in range(3))))
        poly = []
        for a_, b_ in zip(verts, verts[1:] + verts[:1]):
            for t in range(6):
                poly.append(proj(_slerp(a_, b_, t / 6)))
        d.polygon(poly, fill=(22, 22, 24))
    # costuras de los hexágonos: de cada vértice de pentágono al del pentágono vecino
    for i in range(12):
        for j in neigh[i]:
            if i < j:
                a_, b_ = pent[(i, j)], pent[(j, i)]
                pts = [_slerp(a_, b_, t / 8) for t in range(9)]
                vis = [proj(p) for p in pts if p[2] > 0]
                if len(vis) > 1:
                    d.line(vis, fill=(70, 70, 72), width=max(2, D // 260))
    # sombreado: luz arriba a la izquierda
    light = Image.radial_gradient("L").resize((int(D * 2.0), int(D * 2.0)))
    light = light.crop((int(D * 0.62), int(D * 0.62), int(D * 1.62), int(D * 1.62)))
    shade = light.point(lambda v: int(255 - v * 0.62))
    img = ImageChops.multiply(img, Image.merge("RGB", [shade] * 3))
    # desgaste: manchas oscuras pequeñas
    wear = noise((D, D), 70, blur=1.0).point(lambda v: 255 if v > 70 else 150)
    img = ImageChops.multiply(img, Image.merge("RGB", [wear] * 3))
    mask = Image.new("L", (D, D), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, D - 1, D - 1], fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


# ---------------------------------------------------------------- pizarra táctica

def chalk(d, pts, width=7, color=(150, 150, 150, 170), dash=None):
    """Trazo de tiza con leve temblor; dash=(lleno, vacío) en pasos para líneas discontinuas."""
    jit = [(x + rng.uniform(-2, 2), y + rng.uniform(-2, 2)) for x, y in pts]
    if dash:
        on, off = dash
        for i in range(0, len(jit) - 1, on + off):
            d.line(jit[i:i + on + 1], fill=color, width=width)
    else:
        d.line(jit, fill=color, width=width)


def tactic_x(d, x, y, s=34):
    chalk(d, [(x - s, y - s), (x + s, y + s)])
    chalk(d, [(x - s, y + s), (x + s, y - s)])


def tactic_o(d, x, y, s=30):
    pts = [(x + s * math.cos(t / 20 * 2 * math.pi), y + s * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]
    chalk(d, pts)


def tactic_arrow(d, p0, p1, bend=0.35, dashed=True):
    (x0, y0), (x1, y1) = p0, p1
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    cx, cy = mx - (y1 - y0) * bend, my + (x1 - x0) * bend
    pts = [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1)
           for t in (i / 40 for i in range(41))]
    chalk(d, pts, dash=(2, 2) if dashed else None)
    ang = math.atan2(y1 - pts[-3][1], x1 - pts[-3][0])
    for side in (-1, 1):
        a = ang + math.pi + side * 0.5
        chalk(d, [(x1, y1), (x1 + 40 * math.cos(a), y1 + 40 * math.sin(a))])


# ---------------------------------------------------------------- letras de brocha

def brush_text(text: str, fnt: ImageFont.FreeTypeFont, color, angle=-6, roughness=0.07, slant=0.22,
               bold: int = 1) -> Image.Image:
    """Texto con textura de brocha, en cursiva (slant) y girado. Devuelve RGBA recortado."""
    l, t, r_, b = fnt.getbbox(text)
    pad = 60
    mask = Image.new("L", (r_ - l + pad * 2, b - t + pad * 2), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=fnt, fill=255)
    # cursiva: se inclina la parte de arriba hacia la derecha
    w, h = mask.size
    extra = int(slant * h)
    mask = mask.transform((w + extra, h), Image.AFFINE, (1, slant, -extra, 0, 1, 0), resample=Image.BICUBIC)
    mask = mask.filter(ImageFilter.MaxFilter(bold)) if bold > 1 else mask  # trazo de marcador más grueso
    mask = ragged(mask, scale=4, strength=110)
    mask = dry_brush(mask, roughness, stretch=60)
    layer = Image.new("RGBA", mask.size, color + (0,))
    layer.putalpha(mask)
    return layer.rotate(angle, resample=Image.BICUBIC, expand=True)


def brush_stroke(length: int, thick: int, color, angle=-6) -> Image.Image:
    """Pincelada: gruesa al inicio, se afina y deshilacha hacia el final."""
    mask = Image.new("L", (length + 80, thick * 3), 0)
    d = ImageDraw.Draw(mask)
    top = []
    bot = []
    for i in range(41):
        t = i / 40
        x = 40 + t * length
        w = thick * (1 - 0.85 * t ** 1.6) * (0.85 + 0.15 * math.sin(t * 9))
        cy = thick * 1.5 + math.sin(t * 3.1) * thick * 0.12
        top.append((x, cy - w / 2))
        bot.append((x, cy + w / 2))
    d.polygon(top + bot[::-1], fill=255)
    mask = ragged(mask, scale=4, strength=140)
    mask = dry_brush(mask, 0.12, stretch=40)
    layer = Image.new("RGBA", mask.size, color + (0,))
    layer.putalpha(mask)
    return layer.rotate(angle, resample=Image.BICUBIC, expand=True)


def crown(width: int, color) -> Image.Image:
    """Corona dibujada a mano, solo contorno."""
    h = int(width * 0.62)
    img = Image.new("RGBA", (width + 60, h + 60), color + (0,))
    d = ImageDraw.Draw(img)
    o = 30
    pts = [(o, o + h * 0.70), (o + width * 0.04, o + h * 0.12), (o + width * 0.30, o + h * 0.48), (o + width * 0.50, o),
           (o + width * 0.70, o + h * 0.48), (o + width * 0.96, o + h * 0.12), (o + width, o + h * 0.70)]
    for k in range(3):
        jit = [(x + rng.uniform(-3, 3), y + rng.uniform(-3, 3)) for x, y in pts]
        d.line(jit + [jit[0]], fill=color + (255,), width=16, joint="curve")
    base_y = o + h * 0.84
    d.line([(o - 6, base_y), (o + width + 6, base_y - 6)], fill=color + (255,), width=20)
    a = dry_brush(img.getchannel("A"), 0.08, stretch=8)
    img.putalpha(a)
    return img


# ---------------------------------------------------------------- insignia

def rough_ring(size, radius, width) -> Image.Image:
    """Anillo blanco de borde áspero, como pintado a mano."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    cx, cy = size[0] / 2, size[1] / 2
    d.ellipse([cx - radius - width / 2, cy - radius - width / 2, cx + radius + width / 2, cy + radius + width / 2],
              outline=255, width=int(width * 0.8))
    for k in range(26):  # pasadas de pincel que se salen un poco del anillo
        rr = radius + rng.uniform(-width * 0.6, width * 0.6)
        start = rng.uniform(0, 360)
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], start, start + rng.uniform(25, 90), fill=255,
              width=int(width * rng.uniform(0.12, 0.3)))
    return ragged(m, scale=7, strength=150)


def paste_center(base, layer, cx, cy):
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def badge() -> Image.Image:
    # interior: estadio + pasto + balón
    inner = stadium()
    grass(inner, SIZE * 0.80)
    inner = inner.convert("RGBA")
    bd = int(SIZE * 0.29)
    ball_cy = SIZE * 0.835
    shadow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shadow).ellipse([C - bd * 0.55, ball_cy + bd * 0.40, C + bd * 0.55, ball_cy + bd * 0.56], fill=220)
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    inner = Image.composite(Image.new("RGBA", inner.size, (0, 0, 0, 255)), inner, shadow)
    paste_center(inner, ball(bd), C, ball_cy)
    # briznas por delante de la base del balón
    front = Image.new("RGBA", inner.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(front)
    for _ in range(1600):
        x = rng.uniform(C - bd * 0.75, C + bd * 0.75)
        y = rng.uniform(ball_cy + bd * 0.36, ball_cy + bd * 0.62)
        h = SIZE * rng.uniform(0.012, 0.032)
        v = int(rng.uniform(34, 95))
        fd.line([x, y, x + rng.uniform(-0.3, 0.3) * h, y - h], fill=(v, v + 7, v, 255), width=rng.choice((2, 3, 4)))
    inner.alpha_composite(front)

    # pizarra táctica (gris tiza)
    chalk_layer = Image.new("RGBA", inner.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(chalk_layer)
    tactic_x(cd, SIZE * 0.25, SIZE * 0.17)
    tactic_x(cd, SIZE * 0.35, SIZE * 0.23)
    tactic_o(cd, SIZE * 0.19, SIZE * 0.29)
    tactic_arrow(cd, (SIZE * 0.24, SIZE * 0.32), (SIZE * 0.33, SIZE * 0.12))
    tactic_x(cd, SIZE * 0.12, SIZE * 0.49)
    tactic_o(cd, SIZE * 0.13, SIZE * 0.60)
    tactic_arrow(cd, (SIZE * 0.13, SIZE * 0.56), (SIZE * 0.22, SIZE * 0.46), dashed=False)
    tactic_x(cd, SIZE * 0.86, SIZE * 0.58)
    tactic_x(cd, SIZE * 0.76, SIZE * 0.72)
    tactic_o(cd, SIZE * 0.87, SIZE * 0.70)
    tactic_arrow(cd, (SIZE * 0.78, SIZE * 0.75), (SIZE * 0.86, SIZE * 0.62))
    inner.alpha_composite(chalk_layer)

    # letras y adornos
    shadow_col = (0, 0, 0)
    paste_center(inner, crown(int(SIZE * 0.18), WHITE), C + SIZE * 0.01, SIZE * 0.16)
    pase = brush_text("PASE", font("PermanentMarker-Regular.ttf", int(SIZE * 0.21)), WHITE, angle=5, bold=9)
    filtrado = brush_text("FILTRADO", font("PermanentMarker-Regular.ttf", int(SIZE * 0.135)), RED, angle=5, bold=7)
    under = brush_stroke(int(SIZE * 0.62), int(SIZE * 0.045), RED, angle=5)
    for layer, cx, cy in ((pase, C - SIZE * 0.01, SIZE * 0.345), (filtrado, C, SIZE * 0.525), (under, C, SIZE * 0.625)):
        sh = Image.new("RGBA", layer.size, shadow_col + (0,))
        sh.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.85)))
        paste_center(inner, sh, cx + 10, cy + 14)
        paste_center(inner, layer, cx, cy)

    # recorte circular + anillo
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    circle = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(circle).ellipse([C - R_OUT, C - R_OUT, C + R_OUT, C + R_OUT], fill=255)
    circle = circle.filter(ImageFilter.GaussianBlur(1))
    out.paste(inner, (0, 0), circle)
    ring = rough_ring((SIZE, SIZE), R_OUT, int(SIZE * 0.028))
    white = Image.new("RGBA", (SIZE, SIZE), WHITE + (255,))
    out = Image.composite(white, out, ring)
    return out.resize((SIZE // 2, SIZE // 2), Image.LANCZOS)


def highlight_cover(label: str, color=RED) -> Image.Image:
    """Portada de historia destacada con el mismo lenguaje de la insignia."""
    inner = stadium().point(lambda v: int(v * 0.55)).convert("RGBA")
    chalk_layer = Image.new("RGBA", inner.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(chalk_layer)
    tactic_x(cd, SIZE * 0.30, SIZE * 0.30)
    tactic_o(cd, SIZE * 0.70, SIZE * 0.72)
    tactic_arrow(cd, (SIZE * 0.33, SIZE * 0.72), (SIZE * 0.68, SIZE * 0.30))
    inner.alpha_composite(chalk_layer)
    # tamaño según el ancho: la palabra ocupa ~55 % del círculo, sin pasar de un máximo
    probe = font("PermanentMarker-Regular.ttf", 200)
    size = int(min(SIZE * 0.20, 200 * SIZE * 0.55 / probe.getlength(label.upper())))
    text = brush_text(label.upper(), font("PermanentMarker-Regular.ttf", size), color, angle=5, bold=7)
    under = brush_stroke(int(min(text.width * 0.9, SIZE * 0.6)), int(SIZE * 0.03), WHITE if color == RED else RED, angle=5)
    paste_center(inner, text, C, SIZE * 0.47)
    paste_center(inner, under, C, SIZE * 0.47 + text.height * 0.42)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    circle = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(circle).ellipse([C - R_OUT, C - R_OUT, C + R_OUT, C + R_OUT], fill=255)
    out.paste(inner, (0, 0), circle)
    ring = rough_ring((SIZE, SIZE), R_OUT, int(SIZE * 0.028))
    out = Image.composite(Image.new("RGBA", (SIZE, SIZE), WHITE + (255,)), out, ring)
    return out.convert("RGB").resize((SIZE // 2, SIZE // 2), Image.LANCZOS)


COVERS = {"Agenda": WHITE, "Resultados": RED, "Fichajes": RED, "Datos": WHITE, "Champions": WHITE, "Libertadores": RED}


def main():
    out_dir = B.ROOT / "assets" / "brand"
    out_dir.mkdir(parents=True, exist_ok=True)
    logo = badge()
    logo.save(out_dir / "insignia.png")
    bg = Image.new("RGB", logo.size, (0, 0, 0))
    bg.paste(logo, (0, 0), logo)
    bg.save(out_dir / "perfil.jpg", quality=95)
    for label, color in COVERS.items():
        highlight_cover(label, color).save(out_dir / f"destacada-{label.lower()}.jpg", quality=92)
    print(out_dir / "insignia.png")


if __name__ == "__main__":
    main()
