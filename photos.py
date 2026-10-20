"""Fotos con licencia libre desde Wikimedia Commons, con su crédito.

Las fotos de agencias (Getty, AFP, Reuters...) que traen las noticias tienen derechos de autor
y provocan reclamos en Instagram; por eso solo se usan fotos con licencia que permite reutilizar.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata

import requests
from PIL import Image

import brand as B

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia exige un User-Agent identificable (nombre, contacto y librería); si no, responde 429
UA = {"User-Agent": "PaseFiltrado/1.0 (https://commons.wikimedia.org/wiki/User:PaseFiltrado) python-requests"}
CACHE = B.ROOT / "assets" / "cache" / "fotos"
FREE = re.compile(r"^(CC0|CC BY(-SA)? [1-4]\.0|Public domain|PD)", re.I)


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def find_photo(query: str, min_width: int = 900, require: str | None = None, portrait: bool = False) -> dict | None:
    """Busca la mejor foto libre para la consulta. Devuelve ruta local y crédito.

    require: todas sus palabras deben aparecer en el título del archivo (por ejemplo el nombre
    completo), para no publicar la foto de otra persona.
    portrait: solo fotos verticales; descarta tomas de estadio o de grupo.
    """
    try:
        r = requests.get(API, params={
            "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "iiurlwidth": 1600, "format": "json",
        }, headers=UA, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[fotos] {query}: {e}")
        return None

    candidates = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page["imageinfo"][0]
        meta = info.get("extmetadata", {})
        license_ = _clean(meta.get("LicenseShortName", {}).get("value", ""))
        if not FREE.match(license_) or info["width"] < min_width:
            continue
        if require and not all(w in _plain(page["title"]) for w in _plain(require).split()):
            continue
        if portrait and info["height"] < info["width"] * 1.05:
            continue
        # preferimos fotos grandes, que nombren lo buscado en el título y sin "compartir igual" (SA),
        # porque con SA nuestra imagen derivada también quedaría bajo CC BY-SA
        score = min(info["width"], 2000) / 1000
        score += sum(w.lower() in page["title"].lower() for w in query.split())
        score += 0 if "SA" in license_.upper() else 1.5
        score -= page.get("index", 0) * 0.05
        candidates.append((score, page["title"], info, license_, _clean(meta.get("Artist", {}).get("value", ""))))
    if not candidates:
        return None

    _, title, info, license_, author = max(candidates, key=lambda c: c[0])
    url = (info.get("thumburl") or info["url"]).split("?")[0]
    path = CACHE / (hashlib.sha1(title.encode()).hexdigest()[:16] + ".jpg")
    if not path.exists():
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except (requests.RequestException, OSError) as e:
            print(f"[fotos] descarga fallida {title}: {e}")
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=95)
    return {
        "path": path,
        "title": title,
        "author": author or "Wikimedia Commons",
        "license": license_,
        "page": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
        "credit": f"Foto: {author or 'autor desconocido'} / {license_} · Wikimedia Commons",
    }
