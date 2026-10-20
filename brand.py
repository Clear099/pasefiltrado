"""Identidad visual de PASE FILTRADO: colores, tipografías y elementos de marca."""
import json
import os
from pathlib import Path

NAME = "PASE FILTRADO"
HANDLE = "@pasefiltrado"
TAGLINE = "Filtramos el ruido. Te pasamos el fútbol."

ROOT = Path(__file__).parent
FONTS = ROOT / "assets" / "fonts"

# Paletas. El acento es el color de marca: palabras clave, etiquetas, marcadores.
PALETTES = {
    # negro y dorado, tono premium
    "oro": {
        "NEGRO": (11, 11, 12),            # fondo principal
        "GRAFITO": (24, 22, 20),          # filas y tarjetas
        "LINEA": (40, 36, 30),            # líneas del patrón
        "ACENTO": (212, 175, 55),         # #D4AF37
        "ACENTO_CLARO": (246, 222, 148),  # brillo del degradé
        "ACENTO_OSCURO": (168, 128, 46),  # sombra del degradé
        "TEXTO": (245, 241, 232),         # marfil
        "SECUNDARIO": (146, 139, 126),    # piedra
        "SOBRE_ACENTO": (11, 11, 12),     # texto encima del acento
        "ROJO": (214, 64, 52),            # punto de última hora
        "FOCO": (34, 30, 24),             # luz cálida del fondo
        "TINTE": (176, 150, 104),         # tono de la foto de estadio
        "NUMEROS": "degrade",             # horarios y marcadores de listas
    },
    # negro, blanco y rojo, estilo de transmisión deportiva
    "rojo": {
        "NEGRO": (8, 8, 9),
        "GRAFITO": (24, 24, 26),
        "LINEA": (44, 44, 48),
        "ACENTO": (230, 22, 34),          # #E61622
        "ACENTO_CLARO": (255, 70, 66),
        "ACENTO_OSCURO": (176, 8, 20),
        "TEXTO": (255, 255, 255),
        "SECUNDARIO": (150, 152, 158),
        "SOBRE_ACENTO": (255, 255, 255),
        "ROJO": (255, 255, 255),          # el punto de última hora va blanco sobre rojo
        "FOCO": (30, 30, 34),
        "TINTE": (150, 152, 160),
        "NUMEROS": (255, 255, 255),       # en blanco: el rojo queda solo para acentos
    },
}
DEGRADE = "degrade"  # relleno especial: texto con el degradé del acento

# Variantes de tipografía y estilo. Cada fuente es (archivo, peso con nombre o None si es estática).
THEMES = {
    # Serif de revista: titulares en minúsculas, tono premium y editorial
    "editorial": {
        "palette": "oro",
        "fonts": {
            "display": ("PlayfairDisplay.ttf", "ExtraBold"),
            "score": ("PlayfairDisplay.ttf", "Black"),
            "label": ("Outfit.ttf", "SemiBold"),
            "body": ("Outfit.ttf", "Regular"),
            "strong": ("Outfit.ttf", "Medium"),
        },
        "upper": False,
        "leading": 1.14,
        "headline_size": (100, 58),
        "slant": False,
    },
    # Condensada de transmisión, negro y dorado
    "transmision": {
        "palette": "oro",
        "fonts": {
            "display": ("Oswald.ttf", "SemiBold"),
            "score": ("Oswald.ttf", "Bold"),
            "label": ("Outfit.ttf", "SemiBold"),
            "body": ("Outfit.ttf", "Regular"),
            "strong": ("Outfit.ttf", "Medium"),
        },
        "upper": True,
        "leading": 1.12,
        "headline_size": (112, 62),
        "slant": False,
    },
    # Cursiva condensada, negro/blanco/rojo, todo inclinado 7°: velocidad y urgencia
    "impacto": {
        "palette": "rojo",
        "fonts": {
            "display": ("BarlowCondensed-BlackItalic.ttf", None),
            "score": ("BarlowCondensed-BlackItalic.ttf", None),
            "label": ("BarlowCondensed-BoldItalic.ttf", None),
            "body": ("BarlowSemiCondensed-Medium.ttf", None),
            "strong": ("BarlowSemiCondensed-SemiBold.ttf", None),
        },
        "upper": True,
        "leading": 1.02,
        "headline_size": (128, 70),
        "slant": True,
    },
}


def _theme_name() -> str:
    cfg = ROOT / "config.json"
    default = json.loads(cfg.read_text(encoding="utf-8")).get("theme", "editorial") if cfg.exists() else "editorial"
    return os.environ.get("PF_THEME", default)


def _config(key: str, default: str) -> str:
    cfg = ROOT / "config.json"
    return json.loads(cfg.read_text(encoding="utf-8")).get(key, default) if cfg.exists() else default


THEME_NAME = _theme_name()
LOGO = os.environ.get("PF_LOGO", _config("logo", "insignia"))  # logo del estilo inclinado (ver logos.py)
THEME = THEMES[THEME_NAME]
globals().update(PALETTES[THEME["palette"]])  # NEGRO, ACENTO, TEXTO... del tema activo

POST_SIZE = (1080, 1350)  # 4:5, el formato vertical que más ocupa el feed
