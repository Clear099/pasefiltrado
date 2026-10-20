"""Datos propios de la previa: se calculan con los números reales de ESPN (últimos 5 partidos,
historial entre ambos y tabla), así que son verificables. Claude solo elige los más curiosos y
los redacta; sin Claude se usan los de más peso con su texto de plantilla.
"""
from __future__ import annotations

import datetime as dt
import json

import ia


def team_numbers(games: list[dict]) -> dict:
    """Resumen de los últimos partidos de un equipo."""
    res = [g["result"] for g in games]
    streak, last = 0, res[-1] if res else None
    for r in reversed(res):
        if r != last:
            break
        streak += 1
    unbeaten = 0
    for r in reversed(res):
        if r == "P":
            break
        unbeaten += 1
    scoreless_against = 0
    for g in reversed(games):
        if g["ga"] > 0:
            break
        scoreless_against += 1
    return {
        "partidos": len(games), "victorias": res.count("G"), "empates": res.count("E"), "derrotas": res.count("P"),
        "goles_favor": sum(g["gf"] for g in games), "goles_contra": sum(g["ga"] for g in games),
        "vallas_invictas": sum(1 for g in games if g["ga"] == 0),
        "racha": {"tipo": last, "largo": streak}, "invicto": unbeaten, "sin_recibir": scoreless_against,
        "marco_en_todos": all(g["gf"] > 0 for g in games) and bool(games),
    }


def facts(m: dict, summary: dict) -> list[dict]:
    """Datos candidatos: {"numero", "texto", "peso"}. El peso sube cuanto más raro o llamativo es."""
    h, a = m["home"], m["away"]
    out = []
    nums = {}
    for team in (h, a):
        games = summary.get("form", {}).get(team["full_name"], [])
        if not games:
            continue
        n = nums[team["name"]] = team_numbers(games)
        name, k = team["name"], n["partidos"]
        r = n["racha"]
        if r["tipo"] == "G" and r["largo"] >= 3:
            out.append({"numero": str(r["largo"]), "texto": f"victorias seguidas lleva el {name}", "peso": 2 + r["largo"]})
        if r["tipo"] == "P" and r["largo"] >= 2:
            out.append({"numero": str(r["largo"]), "texto": f"derrotas seguidas arrastra el {name}", "peso": 3 + r["largo"]})
        if r["tipo"] != "G" and n["victorias"] == 0:
            out.append({"numero": "0", "texto": f"triunfos en los últimos {k} del {name}", "peso": 6})
        if n["goles_favor"] / k >= 2.4:
            out.append({"numero": str(n["goles_favor"]), "texto": f"goles del {name} en sus últimos {k} partidos",
                        "peso": 3 + n["goles_favor"] / k})
        if n["vallas_invictas"] >= 3:
            out.append({"numero": str(n["vallas_invictas"]), "texto": f"vallas invictas del {name} en sus últimos {k}",
                        "peso": 3 + n["vallas_invictas"]})
        if n["sin_recibir"] >= 3:
            out.append({"numero": str(n["sin_recibir"]), "texto": f"partidos seguidos sin recibir goles lleva el {name}",
                        "peso": 4 + n["sin_recibir"]})
        if k >= 4 and n["goles_contra"] <= 2:
            out.append({"numero": str(n["goles_contra"]), "texto": f"goles recibió el {name} en sus últimos {k}",
                        "peso": 4 + (2 - n["goles_contra"])})
        # rendimiento como local (el que juega en casa) o como visita (el que viaja)
        venue = [g for g in games if g["home"] == (team is h)]
        if len(venue) >= 2:
            w = sum(1 for g in venue if g["result"] == "G")
            if w == len(venue):
                out.append({"numero": f"{w}/{len(venue)}",
                            "texto": f"triunfos del {name} {'en casa' if team is h else 'de visita'} en sus últimos partidos",
                            "peso": 4 + w})
            elif w == 0:
                out.append({"numero": f"0/{len(venue)}",
                            "texto": f"triunfos del {name} {'en casa' if team is h else 'de visita'} en sus últimos partidos",
                            "peso": 5})
        if n["goles_contra"] / k >= 2:
            out.append({"numero": str(n["goles_contra"]), "texto": f"goles recibidos por el {name} en sus últimos {k}",
                        "peso": 4})
        if n["marco_en_todos"] and k >= 5:
            out.append({"numero": str(k), "texto": f"partidos seguidos marcando del {name}", "peso": 3})

    games = (summary.get("h2h") or {}).get("games", [])
    if games:
        g_total = sum(int(g["home_score"] or 0) + int(g["away_score"] or 0) for g in games)
        avg = g_total / len(games)
        if avg >= 3:
            out.append({"numero": f"{avg:.1f}".replace(".", ","),
                        "texto": f"goles por partido en los últimos {len(games)} cruces", "peso": 3 + avg})
        both = sum(1 for g in games if int(g["home_score"] or 0) > 0 and int(g["away_score"] or 0) > 0)
        if both >= max(3, len(games) - 1):
            out.append({"numero": f"{both}/{len(games)}", "texto": "cruces recientes con goles de ambos", "peso": 4})
        draws = sum(1 for g in games if g["home_score"] == g["away_score"])
        if draws >= 3:
            out.append({"numero": str(draws), "texto": f"empates en los últimos {len(games)} cruces", "peso": 5})
        # en esta misma cancha: ¿hace cuánto no gana el visitante?
        here = [g for g in games if g["home"] == h["full_name"]]
        if len(here) >= 2:
            away_wins = [g for g in here if int(g["away_score"] or 0) > int(g["home_score"] or 0)]
            if not away_wins:
                out.append({"numero": "0", "texto": f"victorias del {a['name']} en sus últimas {len(here)} visitas al {h['name']}",
                            "peso": 6 + len(here)})
        wins = {h["full_name"]: 0, a["full_name"]: 0}
        for g in games:
            hs, as_ = int(g["home_score"] or 0), int(g["away_score"] or 0)
            if hs != as_:
                winner = g["home"] if hs > as_ else g["away"]
                if winner in wins:
                    wins[winner] += 1
        for team in (h, a):
            if wins[team["full_name"]] == 0 and len(games) >= 3:
                out.append({"numero": "0", "texto": f"triunfos del {team['name']} en los últimos {len(games)} cruces",
                            "peso": 7})
        last = games[0]
        # ¿el último cruce fue hace poco y por el mismo torneo? entonces fue la ida de esta serie
        days = (m["kickoff"].date() - dt.date.fromisoformat(last["date"][:10])).days
        if 0 < days <= 45:
            hs, as_ = int(last["home_score"] or 0), int(last["away_score"] or 0)
            if hs != as_:
                winner, loser = (last["home"], last["away"]) if hs > as_ else (last["away"], last["home"])
                short = {h["full_name"]: h["name"], a["full_name"]: a["name"]}
                out.append({"numero": f"{last['home_score']}-{last['away_score']}",
                            "texto": f"terminó la ida: el {short.get(loser, loser)} necesita remontar ante el "
                                     f"{short.get(winner, winner)}", "peso": 12})
            else:
                out.append({"numero": f"{hs}-{as_}", "texto": "terminó la ida: la serie está abierta", "peso": 10})
        elif wins[h["full_name"]] != wins[a["full_name"]]:
            top = h if wins[h["full_name"]] > wins[a["full_name"]] else a
            out.append({"numero": f"{wins[top['full_name']]}/{len(games)}",
                        "texto": f"cruces recientes ganados por el {top['name']}", "peso": 3})
        if not 0 < days <= 45:
            out.append({"numero": f"{last['home_score']}-{last['away_score']}",
                        "texto": f"terminó el último cruce ({last['date'][:4]}, {last['home']} de local)", "peso": 2})

    for team in (h, a):
        row = summary.get("table", {}).get(team["full_name"])
        if row and row.get("puesto") and row["puesto"] in ("1", "2", "3"):
            out.append({"numero": f"{row['puesto']}°", "texto": f"puesto del {team['name']} en la tabla, con {row['puntos']} puntos",
                        "peso": 3})
    out.sort(key=lambda f: -f["peso"])
    return out


def numbers_table(m: dict, summary: dict) -> list[tuple[str, float, float, bool]]:
    """Filas del "Duelo en números": (etiqueta, local, visita, menor_es_mejor)."""
    h, a = m["home"], m["away"]
    nh = team_numbers(summary.get("form", {}).get(h["full_name"], []))
    na = team_numbers(summary.get("form", {}).get(a["full_name"], []))
    if not nh["partidos"] or not na["partidos"]:
        return []
    rows = [("Victorias", nh["victorias"], na["victorias"], False),
            ("Goles a favor", nh["goles_favor"], na["goles_favor"], False),
            ("Goles en contra", nh["goles_contra"], na["goles_contra"], True),
            ("Vallas invictas", nh["vallas_invictas"], na["vallas_invictas"], False)]
    th, ta = summary.get("table", {}).get(h["full_name"]), summary.get("table", {}).get(a["full_name"])
    if th and ta and th.get("puesto") and ta.get("puesto"):
        rows.append(("Puesto en la tabla", int(th["puesto"]), int(ta["puesto"]), True))
    return rows


SYSTEM = """Eres el editor de PASE FILTRADO, cuenta de fútbol en español para Latinoamérica y España.
Para la previa del partido del día eliges los 3 datos más curiosos y sorprendentes, los que casi nadie conoce,
y los redactas con gancho. Reglas:
- Usa SOLO los datos de la lista. El "numero" debe ser exactamente el de la lista. No inventes nada.
- "texto": lo que acompaña al número, de 5 a 12 palabras, natural y con chispa, sin repetir el número.
- Prefiere datos sorprendentes (rachas, maldiciones de cancha, empates en serie) a datos obvios.
- No elijas dos datos que digan casi lo mismo."""

SCHEMA = {
    "type": "object",
    "properties": {"datos": {"type": "array", "items": {
        "type": "object",
        "properties": {"numero": {"type": "string"}, "texto": {"type": "string"}},
        "required": ["numero", "texto"], "additionalProperties": False}}},
    "required": ["datos"], "additionalProperties": False,
}


def pick(m: dict, summary: dict, n: int = 3) -> list[dict]:
    cands = facts(m, summary)
    if len(cands) < 2:
        return []
    if ia.allowed("noticias"):
        out = ia.ask_json("noticias", SYSTEM, f"Partido: {m['home']['full_name']} vs {m['away']['full_name']} "
                          f"({m['competition']}).\nDatos calculados:\n{json.dumps(cands[:12], ensure_ascii=False)}",
                          SCHEMA, effort="low", max_tokens=3000)
        valid = {c["numero"] for c in cands}
        if out:
            chosen = [d for d in out["datos"] if d["numero"] in valid][:n]
            if len(chosen) >= 2:
                return chosen
    return cands[:n]
