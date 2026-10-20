"""Fuentes de contenido: noticias por RSS y partidos/resultados desde la API pública de ESPN."""
from __future__ import annotations

import calendar
import datetime as dt
import html
import re
import time
from zoneinfo import ZoneInfo

import feedparser
import requests

UA = {"User-Agent": "Mozilla/5.0"}  # ESPN bloquea agentes con "bot"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^\wáéíóúüñ ]", " ", t)
    return " ".join(w for w in t.split() if len(w) > 2)


def similar(a: str, b: str) -> float:
    wa, wb = set(normalize_title(a).split()), set(normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def fetch_news(feeds: list[dict], max_age_hours: int) -> list[dict]:
    """Noticias recientes de todos los feeds, sin duplicados entre fuentes."""
    now = time.time()
    items: list[dict] = []
    for feed in feeds:
        try:
            r = requests.get(feed["url"], headers=UA, timeout=20)
            parsed = feedparser.parse(r.content)
        except requests.RequestException as e:
            print(f"[fuentes] {feed['name']}: {e}")
            continue
        for e in parsed.entries:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if not ts:
                continue
            age_h = (now - calendar.timegm(ts)) / 3600  # feedparser entrega UTC
            if age_h > max_age_hours or age_h < -2:
                continue
            title = _clean(e.get("title", ""))
            source = feed["name"]
            # Google News agrega " - Medio" al final del titular
            if source == "Google News" and " - " in title:
                title, source = title.rsplit(" - ", 1)
            summary = _clean(e.get("summary", ""))
            if summary.startswith(title[:40]):
                summary = ""  # Google News repite el titular como descripción
            items.append({
                "title": title,
                "summary": summary[:600],
                "source": source,
                "link": e.get("link", ""),
                "age_hours": round(age_h, 1),
                "lang": "en" if "bbc" in feed["url"] else "es",
            })
    items.sort(key=lambda x: x["age_hours"])
    unique: list[dict] = []
    for it in items:
        if all(similar(it["title"], u["title"]) < 0.6 for u in unique):
            unique.append(it)
    return unique


def _team(c: dict) -> dict:
    t = c["team"]
    return {
        "name": t.get("shortDisplayName") or t.get("displayName"),
        "full_name": t.get("displayName"),
        "score": c.get("score", "0"),
        "color": t.get("color"),
        "id": t.get("id"),
        "logo": t.get("logo"),
    }


def fetch_matches(leagues: dict[str, str], day: dt.date, tz: str) -> list[dict]:
    """Partidos de un día (en hora local) para las ligas configuradas."""
    zone = ZoneInfo(tz)
    out = []
    # ESPN agrupa por fecha UTC: se piden el día y el siguiente y se filtra por fecha local
    dates = {day, day + dt.timedelta(days=1)}
    for code, label in leagues.items():
        for d in sorted(dates):
            try:
                data = requests.get(ESPN.format(league=code), params={"dates": d.strftime("%Y%m%d")},
                                    headers=UA, timeout=20).json()
            except (requests.RequestException, ValueError) as e:
                print(f"[espn] {code}: {e}")
                continue
            for ev in data.get("events", []):
                kickoff = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(zone)
                if kickoff.date() != day:
                    continue
                comp = ev["competitions"][0]
                teams = {c["homeAway"]: c for c in comp["competitors"]}
                if "home" not in teams or "away" not in teams:
                    continue
                home, away = _team(teams["home"]), _team(teams["away"])
                names = {home["id"]: home["full_name"], away["id"]: away["full_name"]}
                goals = []
                for det in comp.get("details", []):
                    if not det.get("scoringPlay"):
                        continue
                    who = (det.get("athletesInvolved") or [{}])[0].get("displayName", "")
                    suffix = " (p)" if det.get("penaltyKick") else " (e.c.)" if det.get("ownGoal") else ""
                    goals.append({
                        "minute": det.get("clock", {}).get("displayValue", ""),
                        "player": who + suffix,
                        "team": names.get(det.get("team", {}).get("id"), ""),
                    })
                state = ev["status"]["type"]
                out.append({
                    "id": f"{code}-{ev['id']}",
                    "competition": label,
                    "league": code,
                    "kickoff": kickoff,
                    "time": kickoff.strftime("%H:%M"),
                    "state": state.get("state"),            # pre / in / post
                    "completed": state.get("completed", False),
                    "status_detail": state.get("shortDetail", ""),
                    "home": home,
                    "away": away,
                    "goals": goals,
                    "venue": comp.get("venue", {}).get("fullName"),
                    "venue_city": comp.get("venue", {}).get("address", {}).get("city"),
                })
    # sin duplicados (un partido puede aparecer en dos consultas)
    seen, unique = set(), []
    for m in sorted(out, key=lambda m: (list(leagues).index(m["league"]), m["kickoff"])):
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return unique


def _plain(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def region(league: str) -> str:
    if league.startswith("fifa."):
        return "selecciones"
    if league.startswith("conmebol.") or league.split(".")[0] in ("arg", "bra", "uru", "chi", "col", "per", "par", "ecu"):
        return "sudamerica"
    return "europa"


def is_big_team(team: dict, big_teams: dict[str, list[str]], league: str) -> bool:
    """Coincidencia exacta (sin tildes) con el nombre completo o corto, mirando solo los grandes
    de la región de la liga: así el Liverpool uruguayo no cuenta como el inglés,
    y 'Inter' no calza con 'Inter Bogotá'."""
    names = {_plain(team.get("full_name")), _plain(team.get("name"))}
    candidates = big_teams.get(region(league), []) + big_teams.get("selecciones", [])
    return any(_plain(b) in names for b in candidates)


def match_interest(m: dict, big_teams: list[str], leagues: dict[str, str]) -> float:
    """Puntaje simple para elegir el partido destacado del día."""
    score = 10 - list(leagues).index(m["league"]) * 0.6
    for team in (m["home"], m["away"]):
        if is_big_team(team, big_teams, m["league"]):
            score += 6
    total_goals = int(m["home"]["score"] or 0) + int(m["away"]["score"] or 0)
    return score + min(total_goals, 6) * 0.5


SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary"


def match_summary(m: dict) -> dict:
    """Datos de previa de un partido: últimas 5 de cada equipo, historial y goleadores."""
    event_id = m["id"].split("-", 1)[1]
    try:
        s = requests.get(SUMMARY.format(league=m["league"]), params={"event": event_id},
                         headers=UA, timeout=20).json()
    except (requests.RequestException, ValueError) as e:
        print(f"[espn] resumen {m['id']}: {e}")
        return {}

    form = {}
    for t in s.get("lastFiveGames", []):
        form[t["team"].get("displayName")] = [{
            "result": {"W": "G", "D": "E", "L": "P"}.get(e.get("gameResult"), "·"),
            "score": e.get("score", ""),
            "opponent": e.get("opponent", {}).get("displayName", ""),
            "opponent_team": {"name": e.get("opponent", {}).get("abbreviation", ""),
                              "logo": e.get("opponent", {}).get("logo"), "id": e.get("opponent", {}).get("id")},
            "date": e.get("gameDate", "")[:10],
        } for e in t.get("events", [])]

    h2h = None
    for series in s.get("seasonseries", []):
        if series.get("type") != "head-to-head":
            continue
        games = []
        for e in series.get("events", []):
            comps = {c["homeAway"]: c for c in e.get("competitors", [])}
            if "home" in comps and "away" in comps:
                games.append({
                    "date": e.get("date", "")[:10],
                    "home": comps["home"]["team"].get("displayName"),
                    "away": comps["away"]["team"].get("displayName"),
                    "home_score": comps["home"].get("score"),
                    "away_score": comps["away"].get("score"),
                })
        h2h = {"games": games}
        break

    leaders = {}
    comp = None
    try:
        sb = requests.get(ESPN.format(league=m["league"]), params={"dates": m["kickoff"].astimezone(dt.timezone.utc).strftime("%Y%m%d")},
                          headers=UA, timeout=20).json()
        comp = next(e["competitions"][0] for e in sb.get("events", []) if e["id"] == event_id)
    except (requests.RequestException, ValueError, StopIteration):
        pass
    for c in (comp or {}).get("competitors", []):
        for group in c.get("leaders", []):
            if group.get("name") == "goals" and group.get("leaders"):
                top = group["leaders"][0]
                leaders[c["team"].get("displayName")] = {"player": top["athlete"]["displayName"], "goals": top["displayValue"]}
    return {"form": form, "h2h": h2h, "leaders": leaders}


def h2h_tally(h2h: dict | None, home: str, away: str) -> tuple[int, int, int]:
    """Victorias del local, empates y victorias del visitante en el historial."""
    hw = dr = aw = 0
    for g in (h2h or {}).get("games", []):
        hs, as_ = int(g["home_score"] or 0), int(g["away_score"] or 0)
        if hs == as_:
            dr += 1
        else:
            winner = g["home"] if hs > as_ else g["away"]
            hw += winner == home
            aw += winner == away
    return hw, dr, aw


def marquee(matches: list[dict], big_teams: list[str], leagues: dict[str, str]) -> dict | None:
    """El partido del día: el de mayor interés, solo si de verdad es atractivo."""
    best, best_score = None, 0.0
    for m in matches:
        score = match_interest(m, big_teams, leagues)
        if is_big_team(m["home"], big_teams, m["league"]) and is_big_team(m["away"], big_teams, m["league"]):
            score += 8  # duelo entre dos grandes
        if score > best_score:
            best, best_score = m, score
    return best if best_score >= 20 else None


STAT_KEYS = {"possessionPct": "Posesión", "totalShots": "Remates", "shotsOnTarget": "Remates al arco",
             "wonCorners": "Córners", "offsides": "Fueras de juego", "yellowCards": "Tarjetas amarillas",
             "redCards": "Tarjetas rojas", "foulsCommitted": "Faltas", "saves": "Atajadas"}


def match_stats(m: dict) -> dict:
    """Estadísticas del partido por equipo: {"home": {"Posesión": 52.5, ...}, "away": {...}}. {} si no hay."""
    event_id = m["id"].split("-", 1)[1]
    try:
        s = requests.get(SUMMARY.format(league=m["league"]), params={"event": event_id}, headers=UA, timeout=20).json()
    except (requests.RequestException, ValueError) as e:
        print(f"[espn] estadísticas {m['id']}: {e}")
        return {}
    out = {}
    for t in s.get("boxscore", {}).get("teams", []):
        side = "home" if t.get("team", {}).get("id") == m["home"]["id"] else "away"
        vals = {}
        for st in t.get("statistics", []):
            if st.get("name") in STAT_KEYS:
                try:
                    vals[STAT_KEYS[st["name"]]] = float(st.get("displayValue", "0"))
                except ValueError:
                    pass
        out[side] = vals
    return out if len(out) == 2 and out["home"] and out["away"] else {}
