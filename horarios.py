"""Horarios de un partido para todo el mundo hispanohablante, agrupados por hora local."""
from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

import brand as B

PAISES: dict[str, str] = json.loads((B.ROOT / "config.json").read_text(encoding="utf-8"))["paises"]


def groups(kickoff: dt.datetime) -> list[dict]:
    """Países con la misma hora local, de oeste a este.

    Cada grupo: {"time": "16:00", "plus_day": False, "countries": ["cl", "ar", ...]}.
    Se calcula para cada partido porque los cambios de horario no coinciden entre países.
    """
    west = kickoff.astimezone(ZoneInfo(PAISES["mx"])).date()  # día de referencia: el país más al oeste
    out: dict[tuple, dict] = {}
    for code, tz in PAISES.items():
        local = kickoff.astimezone(ZoneInfo(tz))
        key = (local.utcoffset(), local.strftime("%H:%M"))
        g = out.setdefault(key, {"time": local.strftime("%H:%M"), "countries": [], "plus_day": local.date() > west})
        g["countries"].append(code)
    return [out[k] for k in sorted(out)]


def flag_emoji(code: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("a")) for c in code.lower())


def caption_line(kickoff: dt.datetime, one_flag: bool = False) -> str:
    """Ej.: 🇲🇽 13:00 | 🇨🇴🇵🇪🇪🇨 14:00 | 🇨🇱🇦🇷🇺🇾🇵🇾 16:00 | 🇪🇸 21:00"""
    parts = []
    for g in groups(kickoff):
        flags = flag_emoji(g["countries"][0]) if one_flag else "".join(flag_emoji(c) for c in g["countries"])
        parts.append(f"{flags} {g['time']}{' (+1)' if g['plus_day'] else ''}")
    return " | ".join(parts)
