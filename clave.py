"""La clave del partido: las cifras que explican el resultado, calculadas con los datos de ESPN.

Cada dato trae la cifra grande para la lámina, el texto que la acompaña, una frase completa para
el caption y un peso (mayor = más llamativo). Todo sale de los números; nada se inventa.
"""
from __future__ import annotations


def _minute(text: str) -> int:
    digits = "".join(ch for ch in text.split("+")[0] if ch.isdigit())
    return int(digits) if digits else 0


def streak(form: list[dict], today: str, ok: tuple[str, ...]) -> int:
    """Partidos seguidos con resultado en `ok` hasta hoy (sin contar hoy), del más reciente hacia atrás."""
    n = 0
    for g in sorted((g for g in form if g.get("date", "") < today), key=lambda g: g["date"], reverse=True):
        if g["result"] not in ok:
            break
        n += 1
    return n


def facts(m: dict, st: dict, stats: dict, serie: dict | None = None, form: dict | None = None) -> list[dict]:
    h, a = m["home"], m["away"]
    hs, as_ = int(h["score"]), int(a["score"])
    out = []

    def add(peso, numero, texto, frase, tipo=""):
        out.append({"peso": peso, "numero": numero, "texto": texto, "frase": frase, "tipo": tipo})

    if serie and serie["terminada"]:
        win = h if serie["avanza"] == "home" else a
        g = serie["global"]
        gl = f"{max(g.values())}-{min(g.values())}"
        if serie["ronda"] == "Final":
            add(12, gl, f"global: {win['name']} es campeón", f"{win['name']} es campeón con un {gl} global", "serie")
        elif serie["penales"]:
            add(11, "PEN", f"{win['name']} avanza a {serie['siguiente']} desde los penales",
                f"{win['name']} avanza a {serie['siguiente']} por penales", "serie")
        else:
            add(11, gl, f"global: {win['name']} jugará {serie['siguiente']}",
                f"{win['name']} se impuso {gl} en el global y jugará {serie['siguiente']}", "serie")

    if hs != as_:
        ws, ls = ("home", "away") if hs > as_ else ("away", "home")
        W, L = m[ws], m[ls]
        wg = max(hs, as_)
        sw, sl = (stats or {}).get(ws, {}), (stats or {}).get(ls, {})
        sot = sw.get("Remates al arco")
        if sot and wg >= 2 and wg / sot >= 0.75:
            if wg >= sot:
                add(10, f"{wg}/{sot:.0f}", f"{W['name']} convirtió todos sus remates al arco",
                    f"{W['name']} hizo {wg} goles con {sot:.0f} remates al arco: efectividad total")
            else:
                add(9, f"{wg}/{sot:.0f}", f"goles de {W['name']} por remates al arco",
                    f"{W['name']} hizo {wg} goles con solo {sot:.0f} remates al arco")
        pos = sw.get("Posesión")
        if pos is not None and pos <= 45:
            add(9, f"{pos:.0f}%", f"de posesión le bastó a {W['name']} para ganar",
                f"{W['name']} ganó con apenas {pos:.0f}% de la pelota")
        shw, shl = sw.get("Remates"), sl.get("Remates")
        if shw is not None and shl and shl >= 8 and shl >= shw * 1.5:
            add(8, f"{shl:.0f}", f"remates de {L['name']} no alcanzaron ante un {W['name']} que remató {shw:.0f}",
                f"{L['name']} remató {shl:.0f} veces contra {shw:.0f}, pero el partido fue de {W['name']}")
        if min(hs, as_) == 0 and (sl.get("Remates al arco") or 0) >= 4:
            add(7, f"{sl['Remates al arco']:.0f}", f"remates al arco de {L['name']} y el arco de {W['name']} quedó en cero",
                f"{L['name']} pateó {sl['Remates al arco']:.0f} veces al arco y no pudo con la defensa de {W['name']}")
        dec = st.get("decisivo")
        if dec and _minute(dec["minute"]) >= 85:
            add(7, dec["minute"], f"{dec['player']} definió el partido",
                f"{dec['player']} lo definió al {dec['minute']}")
        if form:
            games, today = form.get(W["full_name"], []), str(m["kickoff"].date())
            wins, unbeaten = streak(games, today, ("G",)) + 1, streak(games, today, ("G", "E")) + 1
            if wins >= 4:
                add(6 + min(wins, 12) / 3, str(wins), f"victorias seguidas de {W['name']}",
                    f"{W['name']} suma {wins} victorias seguidas")
            elif unbeaten >= 5:
                add(6 + min(unbeaten, 12) / 4, str(unbeaten), f"partidos seguidos sin perder de {W['name']}",
                    f"{W['name']} suma {unbeaten} partidos seguidos sin perder")

    if st["linea"]:
        first = st["linea"][0]
        mn = _minute(first["minute"])
        scored_by_winner = (first["side"] == "home") == (hs > as_) and hs != as_
        if mn <= 5 and scored_by_winner:
            team = h if first["side"] == "home" else a
            add(6, first["minute"], f"tardó {team['name']} en abrir el marcador",
                f"{team['name']} pegó primero al {first['minute']}")

    out.sort(key=lambda f: -f["peso"])
    return out[:3]
