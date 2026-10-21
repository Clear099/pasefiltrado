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


def find_photo(query: str, min_width: int = 900, require: str | None = None, portrait: bool = False,
               min_year: int = 0) -> dict | None:
    """Busca la mejor foto libre para la consulta. Devuelve ruta local y crédito.

    require: todas sus palabras deben aparecer en el título del archivo (por ejemplo el nombre
    completo), para no publicar la foto de otra persona.
    portrait: solo fotos verticales; descarta tomas de estadio o de grupo.
    min_year: descarta fotos fechadas antes de ese año y las que no tienen fecha.
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
        if min_year:
            when = re.search(r"(1[89]\d\d|20\d\d)", _clean(meta.get("DateTimeOriginal", {}).get("value", "")))
            if not when or int(when.group(1)) < min_year:
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
    return _download(title, info, license_, author)


def _download(title: str, info: dict, license_: str, author: str) -> dict | None:
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


# nombres con los que Wikimedia suele categorizar a algunos clubes (además del nombre de ESPN)
TEAM_ALIASES = {
    "Paris Saint-Germain": ["PSG", "Paris SG"],
    "Internazionale": ["Inter Milan", "Inter"],
    "Bayern Munich": ["Bayern"],
    "Manchester United": ["Man Utd"],
    "Tottenham Hotspur": ["Tottenham"],
    "Atlético-MG": ["Atlético Mineiro"],
    "Atlético Madrid": ["Atletico Madrid"],
}


def _has_word(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(_plain(phrase))}(?![a-z])", _plain(text)) is not None


def find_player_photo(player: str, team: dict, min_year: int, min_width: int = 900) -> dict | None:
    """Foto libre del jugador con su club actual y reciente.

    Se exige: el jugador en el título o en las categorías, el club (o un alias) en el título,
    la descripción o las categorías, y que la foto sea de min_year o posterior. Así no sale,
    por ejemplo, una foto de cuando el jugador estaba en otro equipo.
    """
    names = [n.strip() for n in (team.get("full_name"), team.get("name")) if n and n.strip()]
    names += TEAM_ALIASES.get(team.get("full_name", ""), [])
    try:
        r = requests.get(API, params={
            "action": "query", "generator": "search", "gsrsearch": f"{player} {names[0]} filetype:bitmap",
            "gsrnamespace": 6, "gsrlimit": 40, "prop": "imageinfo", "iiprop": "url|size|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal|ImageDescription|Categories",
            "iiurlwidth": 1600, "format": "json",
        }, headers=UA, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[fotos] {player}: {e}")
        return None

    candidates = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page["imageinfo"][0]
        meta = info.get("extmetadata", {})
        license_ = _clean(meta.get("LicenseShortName", {}).get("value", ""))
        if not FREE.match(license_) or info["width"] < min_width:
            continue
        title = page["title"]
        cats = _clean(meta.get("Categories", {}).get("value", ""))
        desc = _clean(meta.get("ImageDescription", {}).get("value", ""))
        if not all(w in _plain(title + " " + cats) for w in _plain(player).split()):
            continue
        if not any(_has_word(" ".join((title, desc, cats)), n) for n in names):
            continue
        when = _clean(meta.get("DateTimeOriginal", {}).get("value", ""))
        year = re.search(r"(20\d\d)", when) or re.search(r"(20\d\d)", title + " " + cats)
        year = int(year.group(1)) if year else 0
        if year < min_year:
            continue
        in_title = all(w in _plain(title) for w in _plain(player).split())
        if not in_title:
            continue  # foto de grupo o de partido donde solo figura en las categorías: sale lejos o tapado
        score = (year - min_year) * 1.5
        score += 6 if in_title else 0
        score += 1.5 if not re.search(r"\band\b|,| y ", title) else 0   # foto individual, no de grupo
        score += 1 if info["height"] >= info["width"] else 0               # vertical: llena mejor la portada
        score += 0 if "SA" in license_.upper() else 1.5
        score += min(info["width"], 2000) / 2000
        candidates.append((score, title, info, license_, _clean(meta.get("Artist", {}).get("value", ""))))
    if not candidates:
        print(f"[fotos] sin foto reciente de {player} en {names[0]}")
        return None
    _, title, info, license_, author = max(candidates, key=lambda c: c[0])
    return _download(title, info, license_, author)
