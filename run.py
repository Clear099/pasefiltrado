"""Genera los posts de un horario y los deja en cola para publicar.

Uso:
    python run.py --slot manana        # previa en carrusel del partido del día (o agenda si no hay)
    python run.py --slot noticias      # noticias, priorizando el partido del día
    python run.py --slot monitor       # cada 15 min: resultado al instante y última hora
    python run.py --slot resultados    # carrusel "La fecha en 1 minuto"
    python run.py --slot demo          # muestra de todo en output/demo, sin tocar la cola

Las imágenes quedan en posts/AAAA-MM-DD/ y la cola en data/pending.json.
Cada entrada de la cola tiene "image" (post simple) o "images" (carrusel).
publish.py sube a Instagram lo que esté en la cola.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

import brand as B
import horarios
import photos
import render
import slides
import sources
import writer

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CFG["timezone"])


def load(name: str, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name: str, value) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def tag(text: str) -> str:
    return "#" + re.sub(r"[^\wáéíóúüñ]", "", text.replace(" ", ""))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_caption(body: str, hashtags: list[str], source: str | None = None, bg_credit: bool = True) -> str:
    tags = []
    for h in CFG["hashtags_base"] + [tag(h.lstrip("#")) for h in hashtags]:
        if h.lower() not in (t.lower() for t in tags):
            tags.append(h)
    parts = [body.strip()]
    if source:
        parts.append(f"📰 Fuente: {source}")
    if bg_credit and render.BACKGROUND:
        parts.append(f"📷 Fondo: {render.BACKGROUND['credit'].removeprefix('Foto: ')}")
    parts.append(f"⚽ {B.HANDLE} · fútbol sin relleno")
    parts.append(" ".join(tags[:8]))
    return "\n\n".join(parts)[:2200]


def recent_history(days: int = 3) -> list[dict]:
    cutoff = (dt.datetime.now(TZ) - dt.timedelta(days=days)).isoformat()
    return [h for h in load("history.json", []) if h["date"] >= cutoff]


def already_queued_or_posted() -> list[dict]:
    return recent_history() + load("pending.json", [])


def done_keys() -> set[str]:
    return {h["key"] for h in already_queued_or_posted()}


def relevant(m: dict) -> bool:
    """Champions, top 5 y Libertadores siempre; el resto de Sudamérica solo si es un partido grande."""
    need = CFG.get("solo_partidos_grandes", {}).get(m["league"])
    if not need:
        return True
    big = sum(sources.is_big_team(t, CFG["big_teams"], m["league"]) for t in (m["home"], m["away"]))
    return big >= need


def matches_for(day: dt.date) -> list[dict]:
    return [m for m in sources.fetch_matches(CFG["leagues"], day, CFG["timezone"]) if relevant(m)]


def interest(m: dict) -> float:
    return sources.match_interest(m, CFG["big_teams"], CFG["leagues"])


def todays_marquee(matches: list[dict]) -> dict | None:
    """Partido del día: primero se busca en Champions, top 5 y Libertadores; si ahí no hay uno
    destacado, puede serlo un partido grande de Sudamérica (por ejemplo un clásico)."""
    core = [m for m in matches if m["league"] not in CFG.get("solo_partidos_grandes", {})]
    return (sources.marquee(core, CFG["big_teams"], CFG["leagues"])
            or sources.marquee(matches, CFG["big_teams"], CFG["leagues"]))


def stadium(venue: str | None = None, city: str | None = None) -> dict | None:
    """Foto libre del estadio para el fondo; si no hay, un estadio genérico.

    La ciudad ayuda a elegir bien: hay "Allianz Stadium" en Turín, Sídney y Viena.
    """
    photo = None
    if venue:
        query = f"{venue} {city}" if city and city.lower() not in venue.lower() else venue
        photo = photos.find_photo(query, min_width=1600, require=venue)
    return photo or photos.find_photo(CFG["fondo_generico"], min_width=1600)


def duel(m: dict) -> str:
    return f"{m['home']['full_name']} vs {m['away']['full_name']}"


# ---------------------------------------------------------------- noticias

def slot_news(out_dir: Path, n: int, focus: str | None = None, only_important: bool = False,
              allow_basic: bool = False) -> list[dict]:
    if not writer.has_ai() and not allow_basic:
        # sin Claude solo saldría el titular del medio tal cual: mejor no publicar noticias
        print("[noticias] sin ANTHROPIC_API_KEY: no se publican noticias")
        return []
    done = already_queued_or_posted()
    done_titles = [h["title"] for h in done]
    max_age = 2 if only_important else CFG["max_news_age_hours"]
    candidates = [
        c for c in sources.fetch_news(CFG["feeds"], max_age)
        if all(sources.similar(c["title"], t) < 0.6 for t in done_titles)
    ]
    print(f"[noticias] {len(candidates)} candidatas nuevas")
    entries = []
    for p in writer.pick_and_write(candidates, done_titles, n, focus=focus, only_important=only_important):
        name = f"{dt.datetime.now(TZ):%H%M}-{slug(p['headline'])}.jpg"
        if p["template"] == "stat" and p.get("number"):
            render.render_stat(p, out_dir / name)
        else:
            render.render_news(p, out_dir / name)
        entries.append({
            "key": "news:" + p["link"],
            "title": p["original_title"],
            "image": rel(out_dir / name),
            "caption": build_caption(p["caption"], p["hashtags"], p["source"]),
        })
    return entries


# ---------------------------------------------------------------- mañana: previa o agenda

def preview_caption(m: dict, summary: dict) -> str:
    h, a = m["home"], m["away"]
    lines = [f"🔥 PARTIDO DEL DÍA: {h['full_name']} vs {a['full_name']}",
             f"Hoy por la {m['competition']}{' en el ' + m['venue'] if m.get('venue') else ''}.\n"
             f"⏰ {horarios.caption_line(m['kickoff'])}"]
    facts = []
    for team in (h, a):
        games = summary.get("form", {}).get(team["full_name"], [])
        if games:
            wins = sum(g["result"] == "G" for g in games)
            facts.append(f"{team['name']}: {wins} victorias en sus últimos {len(games)}")
    hw, dr, aw = sources.h2h_tally(summary.get("h2h"), h["full_name"], a["full_name"])
    if hw + dr + aw:
        facts.append(f"Últimos {hw + dr + aw} cruces: {h['name']} {hw}, {a['name']} {aw} y {dr} empate{'s' if dr != 1 else ''}")
    lines.append("\n".join(f"• {f}" for f in facts))
    lines.append(f"¿Cómo termina? Deja tu marcador 👇\nMándaselo a ese amigo que es del {a['name']} o del {h['name']}.")
    return build_caption("\n\n".join(l for l in lines if l), [h["full_name"], a["full_name"], m["competition"]], "ESPN")


def slot_morning(out_dir: Path, today: dt.date) -> list[dict]:
    matches = [m for m in matches_for(today) if m["state"] == "pre"]
    mq = todays_marquee(matches)
    if mq:
        key = f"preview:{mq['id']}"
        if key in done_keys():
            return []
        summary = sources.match_summary(mq)
        render.set_background(stadium(mq.get("venue"), mq.get("venue_city")))
        paths = slides.preview_carousel(mq, summary, out_dir)
        print(f"[mañana] partido del día: {duel(mq)}")
        return [{"key": key, "title": f"Previa {duel(mq)}", "images": [rel(p) for p in paths],
                 "caption": preview_caption(mq, summary)}]
    return slot_agenda(out_dir, today, matches)


def slot_agenda(out_dir: Path, today: dt.date, matches: list[dict]) -> list[dict]:
    if not matches:
        print("[agenda] sin partidos hoy, publico una noticia")
        return slot_news(out_dir, 1)
    key = f"agenda:{today}"
    if key in done_keys():
        return []
    # las ligas más importantes primero, máximo 10 filas
    matches = sorted(matches, key=lambda m: -interest(m))[:10]
    matches.sort(key=lambda m: (list(CFG["leagues"]).index(m["league"]), m["kickoff"]))
    rows = [{"competition": m["competition"], "time": m["time"], "home": m["home"]["name"], "away": m["away"]["name"],
             "home_team": m["home"], "away_team": m["away"], "kickoff": m["kickoff"]} for m in matches]
    img = render.render_list("Partidos de hoy", "Agenda", rows, out_dir / "agenda.jpg", kind="agenda")
    lines = []
    for kickoff in sorted({r["kickoff"] for r in rows}):
        lines.append(f"⏰ {horarios.caption_line(kickoff, one_flag=True)}")
        lines += [f"⚽ {r['home']} vs {r['away']} ({r['competition']})" for r in rows if r["kickoff"] == kickoff]
        lines.append("")
    body = "Los partidos que no te puedes perder hoy 👇\n\n" + "\n".join(lines) + "\n¿Cuál vas a ver?"
    comps = [c.replace(" ", "") for c in dict.fromkeys(r["competition"] for r in rows)]
    return [{"key": key, "title": f"Agenda {today}", "image": rel(img),
             "caption": build_caption(body, comps + ["agendadeportiva"])}]


# ---------------------------------------------------------------- monitor: resultado al instante

def clean_player(name: str) -> str:
    """Quita las marcas de penal y autogol: 'Mbappé (p)' cuenta como 'Mbappé'."""
    return re.sub(r"\s*\((p|e\.c\.)\)$", "", name)


def surname(name: str) -> str:
    parts = clean_player(name).split()
    return parts[-1] if parts else name


def result_headline(m: dict) -> tuple[str, list[str]]:
    """Titular automático del resultado y palabras a destacar."""
    h, a = m["home"], m["away"]
    hs, as_ = int(h["score"]), int(a["score"])
    if hs == as_:
        return f"{h['name']} y {a['name']} empatan {hs}-{as_}", []
    win, lose = (h, a) if hs > as_ else (a, h)
    ws, ls = max(hs, as_), min(hs, as_)
    own = [g for g in m["goals"] if g["team"] == win["full_name"] and "(e.c.)" not in g["player"]]
    counts: dict[str, int] = {}
    for g in own:
        counts[clean_player(g["player"])] = counts.get(clean_player(g["player"]), 0) + 1
    if counts:
        star, k = max(counts.items(), key=lambda kv: kv[1])
        if k >= 2:
            label = {2: "Doblete", 3: "Hat-trick"}.get(k, f"{k} goles")
            return f"{label} de {surname(star)} y el {win['name']} vence {ws}-{ls} al {lose['name']}", [surname(star)]
    verb = "golea" if ws - ls >= 3 else "vence"
    return f"El {win['name']} {verb} {ws}-{ls} al {lose['name']}", [win["name"]]


def result_post(m: dict, out_dir: Path) -> dict:
    """Post del resultado: portada con foto libre del goleador si hay, si no tarjeta con escudos."""
    h, a = m["home"], m["away"]
    headline, highlight = result_headline(m)
    path = out_dir / f"final-{slug(h['name'])}-{slug(a['name'])}.jpg"
    winner = h if int(h["score"]) >= int(a["score"]) else a
    scorers = [clean_player(g["player"]) for g in m["goals"]
               if g["team"] == winner["full_name"] and "(e.c.)" not in g["player"]]
    photo = None
    if scorers:
        top = max(scorers, key=scorers.count)  # max conserva el primero en caso de empate
        photo = photos.find_photo(top, require=top, portrait=True)
    post = {"category": "RESULTADO FINAL", "competition": m["competition"], "headline": headline,
            "highlight": highlight, "date": m["kickoff"].date()}
    if photo:
        render.render_photo(post, photo, path, match=m)
    else:
        render.set_background(stadium(m.get("venue"), m.get("venue_city")))
        render.render_result({**m, "date": m["kickoff"].date()}, path)
    goals = "\n".join(f"⚽ {g['minute']} {g['player']}" for g in m["goals"])
    body = (f"{headline} 🔥\n\nFINAL | {h['full_name']} {h['score']}-{a['score']} {a['full_name']}\n"
            f"🏆 {m['competition']}\n\n{goals}\n\n¿Quién fue la figura del partido? 👇")
    caption = build_caption(body, [h["full_name"], a["full_name"], m["competition"]], "ESPN", bg_credit=not photo)
    if photo:
        caption += f"\n\n📷 {photo['credit']}"
    return {"key": f"match:{m['id']}", "title": f"{h['full_name']} vs {a['full_name']}",
            "image": rel(path), "caption": caption}


def posts_today() -> int:
    today = dt.datetime.now(TZ).date().isoformat()
    return sum(1 for h in load("history.json", []) if h["date"].startswith(today)) + len(load("pending.json", []))


def slot_monitor(out_dir: Path, today: dt.date) -> list[dict]:
    matches = matches_for(today)
    mq = todays_marquee(matches)
    keys = done_keys()
    entries = []
    instant_today = sum(1 for k in keys if k.startswith("match:") and any(k == f"match:{m['id']}" for m in matches))
    for m in sorted((m for m in matches if m["completed"]), key=lambda m: -interest(m)):
        if f"match:{m['id']}" in keys:
            continue
        is_marquee = mq is not None and m["id"] == mq["id"]
        if not is_marquee and (interest(m) < CFG["instant_min_interest"] or instant_today >= CFG["instant_max_per_day"]):
            continue
        print(f"[monitor] terminó {duel(m)}: {m['home']['score']}-{m['away']['score']}")
        entries.append(result_post(m, out_dir))
        instant_today += 1

    # una vez por hora, revisar si hay algo de última hora (entre 9:00 y 23:00)
    now = dt.datetime.now(TZ)
    if now.minute < 15 and 9 <= now.hour <= 23 and posts_today() + len(entries) < CFG["max_posts_per_day"]:
        entries += slot_news(out_dir, 1, focus=duel(mq) if mq else None, only_important=True)
    return entries


# ---------------------------------------------------------------- noche: la fecha en 1 minuto

def slot_results(out_dir: Path, today: dt.date) -> list[dict]:
    matches = [m for m in matches_for(today) if m["completed"]]
    key = f"results:{today}"
    if len(matches) < 3 or key in done_keys():
        print("[resultados] menos de 3 partidos terminados o ya publicado")
        return []
    mq = todays_marquee(matches)
    featured = mq or max(matches, key=interest)
    matches = sorted(matches, key=lambda m: (list(CFG["leagues"]).index(m["league"]), -interest(m), m["kickoff"]))
    render.set_background(stadium(featured.get("venue"), featured.get("venue_city")))
    paths = slides.results_carousel(featured, matches, out_dir, today, sorted(matches, key=lambda m: -interest(m)))
    lines = []
    for comp in dict.fromkeys(m["competition"] for m in matches):
        lines.append(f"🏆 {comp}")
        lines += [f"{m['home']['name']} {m['home']['score']}-{m['away']['score']} {m['away']['name']}"
                  for m in matches if m["competition"] == comp][:9]
        lines.append("")
    body = ("La fecha en 1 minuto 👉 desliza\n\n" + "\n".join(lines)
            + "\n¿Qué resultado no viste venir? 👇\nGuárdalo para no perderte nada.")
    return [{"key": key, "title": f"Resultados {today}", "images": [rel(p) for p in paths],
             "caption": build_caption(body, ["resultados"] + list(dict.fromkeys(m["competition"] for m in matches))[:3])}]


def slot_intro(out_dir: Path) -> list[dict]:
    """Carrusel de presentación de la cuenta (se publica una sola vez, para fijarlo en el perfil)."""
    if "intro" in {h["key"] for h in load("history.json", [])} | done_keys():
        print("[presentación] ya publicada")
        return []
    paths = slides.intro_carousel(out_dir)
    body = ("👋 Bienvenido a Pase Filtrado\n"
            "Filtramos el ruido. Te pasamos el fútbol ⚽\n\n"
            "🏆 Champions League, las 5 grandes de Europa y la Copa Libertadores\n"
            "🔥 El partido del día con previa, datos y tu pronóstico\n"
            "⚡ Resultados al instante, minutos después del pitazo\n"
            "✅ Fichajes con semáforo: confirmado, en negociación o rumor\n"
            "🌎 Cada partido con la hora de tu país, de México a España\n\n"
            "Activa las notificaciones 🔔 y mándaselo a tu grupo del fútbol 👇")
    return [{"key": "intro", "title": "Presentación de la cuenta", "images": [rel(p) for p in paths],
             "caption": build_caption(body, ["ChampionsLeague", "CopaLibertadores", "LaLiga", "PremierLeague"])}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True,
                    choices=["manana", "agenda", "noticias", "monitor", "resultados", "presentacion", "demo"])
    ap.add_argument("--date", help="AAAA-MM-DD, por defecto hoy (hora local)")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(TZ).date()
    out_dir = ROOT / ("output/demo" if args.slot == "demo" else f"posts/{today}")

    render.set_background(stadium())
    if args.slot in ("manana", "agenda"):
        entries = slot_morning(out_dir, today)
    elif args.slot == "noticias":
        mq = todays_marquee(matches_for(today))
        entries = slot_news(out_dir, CFG["news_per_run"], focus=duel(mq) if mq else None)
    elif args.slot == "monitor":
        entries = slot_monitor(out_dir, today)
    elif args.slot == "resultados":
        entries = slot_results(out_dir, today)
    elif args.slot == "presentacion":
        entries = slot_intro(ROOT / "posts" / "presentacion")
    else:
        entries = slot_morning(out_dir, today) + slot_news(out_dir, 2, allow_basic=True) \
            + slot_results(out_dir, today - dt.timedelta(days=2))
        for e in entries:
            print(f"\n=== {e.get('images') or e['image']}\n{e['caption']}")
        return

    created = dt.datetime.now(TZ).isoformat()
    for e in entries:
        e["created"] = created
    pending = load("pending.json", [])
    pending += entries
    save("pending.json", pending)
    for e in entries:
        print(f"[cola] {e.get('images') or e['image']}")
    print(f"{len(entries)} post(s) en cola, {len(pending)} pendientes en total")


if __name__ == "__main__":
    main()
