"""La historia de un partido terminado: qué lo hace contable y cómo titularlo.

A partir de los goles (minuto y equipo) se reconstruye el marcador minuto a minuto para detectar
remontadas, goles agónicos, goleadas, partidos locos, dobletes y batacazos. Con eso Claude escribe
una etiqueta y un titular con gancho; sin Claude se usa un titular de plantilla con la misma historia.
"""
from __future__ import annotations

import json
import re

import ia


def minute_value(text: str) -> float:
    """"45'+2'" → 45.02, "90'+5'" → 90.05, "67'" → 67."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")]
    if not nums:
        return 0.0
    return nums[0] + (nums[1] / 100 if len(nums) > 1 else 0)


def clean_player(name: str) -> str:
    return re.sub(r"\s*\((p|e\.c\.)\)$", "", name)


def surname(name: str) -> str:
    parts = clean_player(name).split()
    return parts[-1] if parts else name


def story(m: dict, is_big=lambda team: False) -> dict:
    """Hechos del partido, en orden de interés. Cada hecho tiene un tipo y los datos para contarlo."""
    h, a = m["home"], m["away"]
    hs, as_ = int(h["score"]), int(a["score"])
    goals = sorted(m.get("goals", []), key=lambda g: minute_value(g["minute"]))
    score = {"home": 0, "away": 0}
    worst = {"home": 0, "away": 0}  # peor desventaja que sufrió cada equipo
    timeline = []
    for g in goals:
        side = "home" if g["team"] == h["full_name"] else "away"
        score[side] += 1
        for s, o in (("home", "away"), ("away", "home")):
            worst[s] = min(worst[s], score[s] - score[o])
        timeline.append({**g, "side": side, "score": f"{score['home']}-{score['away']}"})

    winner = "home" if hs > as_ else "away" if as_ > hs else None
    win_team = {"home": h, "away": a}.get(winner)
    lose_team = {"home": a, "away": h}.get(winner)
    facts = []

    # gol decisivo: el que dejó al ganador arriba para siempre (o el empate final)
    decisive = None
    if timeline:
        if winner:
            lead_from = None
            for i, t in enumerate(timeline):
                hh, aa = map(int, t["score"].split("-"))
                ahead = (hh > aa) if winner == "home" else (aa > hh)
                lead_from = (i if lead_from is None else lead_from) if ahead else None
            decisive = timeline[lead_from] if lead_from is not None else None
        elif hs == as_ and hs > 0:
            decisive = timeline[-1]

    if winner and worst[winner] <= -1:
        facts.append({"tipo": "remontada", "desventaja": -worst[winner]})
    if decisive and minute_value(decisive["minute"]) >= 85:
        facts.append({"tipo": "agonico", "minuto": decisive["minute"], "jugador": clean_player(decisive["player"]),
                      "empate": winner is None})
    if winner and is_big(lose_team) and not is_big(win_team):
        facts.append({"tipo": "batacazo"})
    if hs + as_ >= 6 and min(hs, as_) >= 2:  # muchos goles de ambos lados (un 5-1 es goleada, no locura)
        facts.append({"tipo": "partido_loco", "goles": hs + as_})
    if winner and abs(hs - as_) >= 3:
        facts.append({"tipo": "goleada", "diferencia": abs(hs - as_)})
    counts = {}
    for t in timeline:
        if "(e.c.)" not in t["player"]:
            key = (clean_player(t["player"]), t["side"])
            counts[key] = counts.get(key, 0) + 1
    for (player, side), k in sorted(counts.items(), key=lambda kv: -kv[1]):
        if k >= 2:
            facts.append({"tipo": "hat_trick" if k >= 3 else "doblete", "jugador": player, "goles": k,
                          "equipo": {"home": h, "away": a}[side]["name"]})
    if winner and min(hs, as_) == 0 and abs(hs - as_) <= 2:
        facts.append({"tipo": "valla_invicta"})

    priority = ["remontada", "agonico", "batacazo", "hat_trick", "partido_loco", "goleada", "doblete", "valla_invicta"]
    facts.sort(key=lambda f: priority.index(f["tipo"]))

    # protagonista para la foto: quien hizo más goles del ganador; si no, el del gol decisivo
    hero = None
    for (player, side), k in sorted(counts.items(), key=lambda kv: -kv[1]):
        if side == (winner or side):
            hero = (player, {"home": h, "away": a}[side])
            break
    if decisive and (hero is None or counts.get((hero[0], decisive["side"]), 0) < 2):
        hero = (clean_player(decisive["player"]), {"home": h, "away": a}[decisive["side"]])
    return {"hechos": facts, "linea": timeline, "ganador": win_team, "perdedor": lose_team, "decisivo": decisive,
            "protagonista": hero}


KICKERS = {"remontada": "REMONTADA", "agonico": "AGÓNICO", "batacazo": "BATACAZO", "partido_loco": "PARTIDO LOCO",
           "goleada": "GOLEADA", "hat_trick": "HAT-TRICK", "doblete": "DOBLETE", "valla_invicta": "RESULTADO FINAL"}


def template(m: dict, st: dict) -> dict:
    """Titular de respaldo (sin Claude), contando el hecho más llamativo."""
    h, a = m["home"], m["away"]
    hs, as_ = int(h["score"]), int(a["score"])
    win, lose = st["ganador"], st["perdedor"]
    top = st["hechos"][0] if st["hechos"] else {"tipo": ""}
    kicker = KICKERS.get(top["tipo"], "RESULTADO FINAL")
    if not win:
        if top["tipo"] == "agonico":
            return {"etiqueta": "AGÓNICO", "titular": f"{surname(top['jugador'])} rescata el empate al {top['minuto']}",
                    "destacar": [surname(top["jugador"])]}
        return {"etiqueta": kicker, "titular": f"{h['name']} y {a['name']} empatan {hs}-{as_}", "destacar": []}
    ws, ls = max(hs, as_), min(hs, as_)
    t = top["tipo"]
    if t == "remontada":
        goles = {1: "un gol", 2: "dos goles", 3: "tres goles"}.get(top["desventaja"], f"{top['desventaja']} goles")
        line = f"El {win['name']} remonta {goles} y vence {ws}-{ls} al {lose['name']}"
    elif t == "agonico":
        line = f"{surname(top['jugador'])} lo gana al {top['minuto']}: {win['name']} {ws}-{ls} {lose['name']}"
    elif t == "partido_loco":
        line = f"{top['goles']} goles y triunfo del {win['name']} {ws}-{ls} sobre el {lose['name']}"
    elif t in ("hat_trick", "doblete"):
        line = f"{'Hat-trick' if t == 'hat_trick' else 'Doblete'} de {surname(top['jugador'])} y el {win['name']} vence {ws}-{ls}"
    elif t == "goleada":
        line = f"El {win['name']} golea {ws}-{ls} al {lose['name']}"
    else:
        line = f"El {win['name']} vence {ws}-{ls} al {lose['name']}"
    hero = st["protagonista"][0] if st["protagonista"] else None
    return {"etiqueta": kicker, "titular": line, "destacar": [surname(hero)] if hero else [win["name"]]}


SYSTEM = """Eres el editor de PASE FILTRADO, cuenta de Instagram de noticias de fútbol en español para
Latinoamérica y España. Escribes la portada de un resultado: tiene que enganchar en un segundo.
- La etiqueta es la idea fuerza en 1 a 3 palabras, en mayúsculas (ej. "REMONTADA", "LOCURA EN ANFIELD", "AGÓNICO").
- El titular cuenta la historia, no solo el marcador: remontada, gol en el último minuto, figura, batacazo.
  De 6 a 11 palabras, con el marcador. Nada de clichés vacíos ("partidazo", "se vivió un gran encuentro").
- "destacar" son 1 o 2 palabras del titular que irán en rojo (el protagonista o el equipo).
- El caption: primera línea con gancho, luego 2 a 4 líneas con lo que pasó (goles clave, minutos, datos),
  y una pregunta concreta para comentar. Máximo 2 emojis. Sin hashtags.
- Usa SOLO los datos entregados. No inventes nada."""

SCHEMA = {
    "type": "object",
    "properties": {
        "etiqueta": {"type": "string"},
        "titular": {"type": "string"},
        "destacar": {"type": "array", "items": {"type": "string"}},
        "caption": {"type": "string"},
    },
    "required": ["etiqueta", "titular", "destacar", "caption"],
    "additionalProperties": False,
}


def headline(m: dict, st: dict, stats: dict | None) -> dict:
    """Etiqueta, titular, palabras a destacar y caption. Usa Claude si hay clave; si no, la plantilla."""
    base = template(m, st)
    if not ia.allowed("resultados"):
        return {**base, "caption": None}
    h, a = m["home"], m["away"]
    facts = {
        "competicion": m["competition"], "estadio": m.get("venue"),
        "local": h["full_name"], "visita": a["full_name"], "marcador": f"{h['score']}-{a['score']}",
        "goles": [{"minuto": t["minute"], "jugador": t["player"], "equipo": h["full_name"] if t["side"] == "home"
                   else a["full_name"], "marcador_tras_el_gol": t["score"]} for t in st["linea"]],
        "hechos_destacados": st["hechos"], "estadisticas": stats or {},
    }
    out = ia.ask_json("resultados", SYSTEM, "Datos del partido:\n" + json.dumps(facts, ensure_ascii=False, indent=1),
                      SCHEMA, effort="low", max_tokens=4000)
    if not out or not out.get("titular"):
        return {**base, "caption": None}
    return {"etiqueta": out["etiqueta"].upper()[:28], "titular": out["titular"], "destacar": out["destacar"][:2],
            "caption": out["caption"]}
