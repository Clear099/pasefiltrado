"""Logo del estilo "impacto": la insignia de badge.py (estadio, pizarra táctica, balón y letras de brocha)."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image

import brand as B
from render import s

INSIGNIA = B.ROOT / "assets" / "brand" / "insignia.png"


@lru_cache(maxsize=None)
def _insignia(px: int) -> Image.Image:
    if not INSIGNIA.exists():
        import badge  # se genera la primera vez
        badge.main()
    return Image.open(INSIGNIA).convert("RGBA").resize((px, px), Image.LANCZOS)


def logo_insignia(d, x, y, size):
    img = _insignia(s(size))
    d.canvas.paste(img, (s(x), s(y)), img)


LOGOS = {"insignia": logo_insignia}
