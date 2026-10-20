"""Slides de carrusel: previa del partido del día y resumen de la jornada."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import brand as B
import horarios
import render as R
from render import case, chip, font, paint, s, tracked, tracked_len

W, H = B.POST_SIZE


def _title(d, text: str, highlight: list[str], y: float = 268, max_lines=2) -> float:
    f, lines, size = R.fit_text(case(text), "display", W - 124, max_lines, 104, 60)
    return R.draw_rich_lines(d, lines, f, 62, y, size * B.THEME["leading"], B.TEXTO, highlight) + size * 0.2


def _centered(d, text, f, y, fill, tracking=None):
    if tracking is None:
        paint(d, (s(W / 2) - f.getlength(text) / 2, s(y)), text, f, fill)
    else:
        tracked(d, (s(W / 2) - tracked_len(text, f, tracking) / 2, s(y)), text, f, fill, tracking)


def _swipe(d):
    """'DESLIZA' con una flecha dibujada (no todas las fuentes traen el carácter →)."""
    f = font("label", 22)
    txt = "DESLIZA"
    x = s(W - 62 - 34) - tracked_len(txt, f, 5)
    tracked(d, (x, s(H - 160)), txt, f, B.ACENTO, 5)
    _, top, _, bottom = f.getbbox("A")
    cy = (s(H - 160) + (top + bottom) / 2) / R.S
    ax = W - 62 - 22
    d.line([s(ax), s(cy), s(ax + 20), s(cy)], fill=B.ACENTO, width=s(3))
    d.polygon([(s(ax + 22), s(cy)), (s(ax + 12), s(cy - 7)), (s(ax + 12), s(cy + 7))], fill=B.ACENTO)


def _duel(d, home: dict, away: dict, cy: float, r: float, center_text: str | None = "VS"):
    """Dos escudos en anillos dorados con sus nombres debajo."""
    for team, cx in ((home, 228), (away, W - 228)):
        R.crest_badge(d, team, cx, cy, r)
        fn, lines, nsize = R.fit_text(case(team["name"]), "display", 340, 2, 56, 32)
        ny = cy + r + 30
        for line in lines:
            paint(d, (s(cx) - fn.getlength(line) / 2, s(ny)), line, fn, B.TEXTO)
            ny += nsize * 1.12
    if center_text:
        f = font("display", 84)
        _, top, _, bottom = f.getbbox(center_text)
        paint(d, (s(W / 2) - f.getlength(center_text) / 2, s(cy) - (top + bottom) / 2), center_text, f, B.DEGRADE)


# ---------------------------------------------------------------- previa del partido del día

def preview_cover(m: dict, out: Path, n: int) -> Path:
    img, d = R.base(right=f"1/{n}")
    cw = chip(d, 62, 196, "PARTIDO DEL DÍA", filled=True)
    tracked(d, (s(62 + cw + 20), s(209)), m["competition"].upper(), font("label", 22), B.SECUNDARIO, 3)
    _duel(d, m["home"], m["away"], 470, 150)
    fl = font("label", 22)
    sub = "HOY" + (f" · {m['venue'].upper()}" if m.get("venue") else "")
    _centered(d, sub, fl, 792, B.TEXTO, 5)
    time_grid(d, m["kickoff"], 852)
    _swipe(d)
    R.footer(d, "ESPN")
    return R.finish(img, out)


def time_grid(d, kickoff: dt.datetime, y: float):
    """Fila de horarios: la hora de cada grupo de países y sus banderas debajo."""
    groups = horarios.groups(kickoff)
    col_w = (W - 124) / len(groups)
    ft = font("score", 62)
    for i, g in enumerate(groups):
        cx = 62 + col_w * (i + 0.5)
        if i:
            d.line([s(62 + col_w * i), s(y + 10), s(62 + col_w * i), s(y + 170)], fill=B.LINEA, width=s(1.5))
        _, top, _, bottom = ft.getbbox(g["time"])
        paint(d, (s(cx) - ft.getlength(g["time"]) / 2, s(y + 40) - (top + bottom) / 2), g["time"], ft, B.NUMEROS)
        if g["plus_day"]:
            fp = font("label", 16)
            tracked(d, (s(cx) - tracked_len("+1 DÍA", fp, 2) / 2, s(y + 80)), "+1 DÍA", fp, B.SECUNDARIO, 2)
        codes = g["countries"]
        size = 40 if len(codes) <= 3 else 34
        rows = [codes[:4], codes[4:8]] if len(codes) > 4 else [codes]
        for k, row in enumerate(rows):
            R.flag_row(d, row, cx, y + 125 + k * (size + 8), size)


def _streak(results: list[str]) -> str:
    """Racha más reciente, ej. '5 victorias seguidas'."""
    if not results:
        return ""
    last = results[-1]
    k = 0
    for r in reversed(results):
        if r != last:
            break
        k += 1
    word = {"G": ("victoria", "victorias"), "E": ("empate", "empates"), "P": ("derrota", "derrotas")}.get(last)
    if not word or k < 2:
        return f"{results.count('G')} victorias en los últimos {len(results)}"
    return f"{k} {word[1]} seguidas"


def preview_form(m: dict, summary: dict, out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "PREVIA")
    y = _title(d, "Así llegan", ["llegan"])
    y += 30
    sq = 112
    for team in (m["home"], m["away"]):
        games = summary.get("form", {}).get(team["full_name"], [])[-5:]
        R.mini_crest(d, team, 62 + 30, y + 30, 60)
        paint(d, (s(62 + 76), s(y + 6)), case(team["name"]), font("display", 46), B.TEXTO)
        streak = _streak([g["result"] for g in games]).upper()
        fl = font("label", 20)
        tracked(d, (s(W - 62) - tracked_len(streak, fl, 3), s(y + 22)), streak, fl, B.ACENTO, 3)
        y += 84
        gap = (W - 124 - sq * 5) / 4
        for k, g in enumerate(games):
            x = 62 + k * (sq + gap)
            res = g["result"]
            if res == "G":
                d.rectangle([s(x), s(y), s(x + sq), s(y + sq)], fill=B.ACENTO)
                color = B.NEGRO
            else:
                d.rectangle([s(x), s(y), s(x + sq), s(y + sq)], outline=B.ROJO if res == "P" else B.SECUNDARIO, width=s(3))
                color = B.ROJO if res == "P" else B.SECUNDARIO
            fr = font("score", 54)
            _, top, _, bottom = fr.getbbox(res)
            paint(d, (s(x + sq / 2) - fr.getlength(res) / 2, s(y + sq / 2) - (top + bottom) / 2), res, fr, color)
            fs = font("strong", 24)
            lw = 34 + 8 + R.text_w(g["score"], fs)
            lx = x + sq / 2 - lw / 2
            R.mini_crest(d, g.get("opponent_team"), lx + 17, y + sq + 30, 34)
            paint(d, (s(lx + 42), s(y + sq + 14)), g["score"], fs, B.TEXTO)
        y += sq + 110
    fl = font("label", 18)
    tracked(d, (s(62), s(y - 10)), "G GANÓ · E EMPATÓ · P PERDIÓ · DEL MÁS ANTIGUO AL MÁS RECIENTE", fl, B.SECUNDARIO, 2)
    R.footer(d, "ESPN")
    return R.finish(img, out)


def preview_h2h(m: dict, summary: dict, out: Path, i: int, n: int) -> Path:
    import sources
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "HISTORIAL")
    y = _title(d, "Cara a cara", [])
    home, away = m["home"], m["away"]
    hw, dr, aw = sources.h2h_tally(summary.get("h2h"), home["full_name"], away["full_name"])
    cy = y + 130
    R.crest_badge(d, home, 170, cy, 100)
    R.crest_badge(d, away, W - 170, cy, 100)
    cols = ((hw, f"GANÓ {home['name']}"), (dr, "EMPATES"), (aw, f"GANÓ {away['name']}"))
    for k, (num, label) in enumerate(cols):
        cx = W / 2 + (k - 1) * 150
        f = font("score", 110)
        _, top, _, bottom = f.getbbox(str(num))
        best = num == max(hw, dr, aw) and num > 0
        paint(d, (s(cx) - f.getlength(str(num)) / 2, s(cy) - (top + bottom) / 2), str(num), f, B.DEGRADE if best else B.TEXTO)
    fl = font("label", 16)
    for k, (_, label) in enumerate(cols):
        cx = W / 2 + (k - 1) * 150
        words = label.upper().split(" ", 1)
        for j, wline in enumerate(words):
            tracked(d, (s(cx) - tracked_len(wline, fl, 2) / 2, s(cy + 80 + j * 24)), wline, fl, B.SECUNDARIO, 2)
    y = cy + 190
    tracked(d, (s(62), s(y)), "ÚLTIMOS PARTIDOS", font("label", 20), B.ACENTO, 4)
    y += 46
    fr = font("strong", 32)
    fs = font("score", 40)
    for g in (summary.get("h2h") or {}).get("games", [])[:5]:
        d.rectangle([s(62), s(y), s(W - 62), s(y + 74)], fill=B.GRAFITO)
        d.rectangle([s(62), s(y), s(66), s(y + 74)], fill=B.ACENTO)
        mid = s(y + 37)
        _, ft, _, fb = fr.getbbox("Ag")
        paint(d, (s(88), mid - (ft + fb) / 2), g["date"][:4], fr, B.SECUNDARIO)
        score = f"{g['home_score']} – {g['away_score']}"
        _, st, _, sb = fs.getbbox("0")
        cx = W / 2 + 40
        sw = fs.getlength(score)
        paint(d, (s(cx) - sw / 2, mid - (st + sb) / 2), score, fs, B.NUMEROS)
        hn, an = _short(g["home"], m), _short(g["away"], m)
        paint(d, (s(cx) - sw / 2 - s(22) - fr.getlength(hn), mid - (ft + fb) / 2), hn, fr, B.TEXTO)
        paint(d, (s(cx) + sw / 2 + s(22), mid - (ft + fb) / 2), an, fr, B.TEXTO)
        y += 86
    R.footer(d, "ESPN")
    return R.finish(img, out)


def _short(full: str, m: dict) -> str:
    for t in (m["home"], m["away"]):
        if full == t["full_name"]:
            return t["name"]
    return full


def preview_scorers(m: dict, summary: dict, out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    cw = chip(d, 62, 196, "LOS QUE DEFINEN")
    tracked(d, (s(62 + cw + 20), s(209)), f"EN {m['competition'].upper()}", font("label", 22), B.SECUNDARIO, 3)
    y = _title(d, "Sus goleadores", ["goleadores"])
    y += 40
    for team in (m["home"], m["away"]):
        lead = summary.get("leaders", {}).get(team["full_name"])
        R.crest_badge(d, team, 62 + 110, y + 110, 110)
        x = 62 + 250
        fl = font("label", 20)
        tracked(d, (s(x), s(y + 20)), team["name"].upper(), fl, B.SECUNDARIO, 3)
        if lead:
            fn, lines, nsize = R.fit_text(case(lead["player"]), "display", W - 62 - x, 2, 72, 40)
            ny = y + 52
            for line in lines:
                paint(d, (s(x), s(ny)), line, fn, B.TEXTO)
                ny += nsize * 1.1
            goals = lead["goals"]
            label = f"{goals} {'GOL' if goals == '1' else 'GOLES'}"
            paint(d, (s(x), s(ny + 8)), label, font("score", 54), B.NUMEROS)
        else:
            paint(d, (s(x), s(y + 60)), "SIN GOLES AÚN", font("display", 48), B.SECUNDARIO)
        y += 300
    R.footer(d, "ESPN")
    return R.finish(img, out)


def preview_poll(m: dict, out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "TU PRONÓSTICO", filled=True)
    _title(d, "¿Cómo termina?", ["termina?"], max_lines=1)
    cy = 640
    _duel(d, m["home"], m["away"], cy, 140, center_text=None)
    box = 120
    for k in (-1, 1):
        x = W / 2 + k * 90 - box / 2
        d.rectangle([s(x), s(cy - box / 2), s(x + box), s(cy + box / 2)], outline=B.ACENTO, width=s(3))
        f = font("score", 70)
        _, top, _, bottom = f.getbbox("?")
        paint(d, (s(x + box / 2) - f.getlength("?") / 2, s(cy) - (top + bottom) / 2), "?", f, B.SECUNDARIO)
    fl = font("label", 24)
    _centered(d, "DÉJALO EN LOS COMENTARIOS", fl, 930, B.TEXTO, 5)
    _centered(d, "Y ETIQUETA A QUIEN NO SABE PERDER", font("label", 20), 975, B.ACENTO, 4)
    R.footer(d, None)
    return R.finish(img, out)


def preview_carousel(m: dict, summary: dict, out_dir: Path) -> list[Path]:
    """Carrusel completo de previa: portada, forma, historial, goleadores y pronóstico."""
    slug = f"previa-{m['id']}"
    builders = [lambda p, i, n: preview_cover(m, p, n),
                lambda p, i, n: preview_form(m, summary, p, i, n)]
    if (summary.get("h2h") or {}).get("games"):
        builders.append(lambda p, i, n: preview_h2h(m, summary, p, i, n))
    if summary.get("leaders"):
        builders.append(lambda p, i, n: preview_scorers(m, summary, p, i, n))
    builders.append(lambda p, i, n: preview_poll(m, p, i, n))
    n = len(builders)
    return [b(out_dir / f"{slug}-{i}.jpg", i, n) for i, b in enumerate(builders, start=1)]


# ---------------------------------------------------------------- resumen de la jornada

def results_cover(featured: dict, matches: list[dict], out: Path, n: int, date: dt.date,
                  highlights: list[dict]) -> Path:
    img, d = R.base(right=f"1/{n}")
    chip(d, 62, 196, "RESULTADOS")
    y = _title(d, "La fecha en 1 minuto", ["minuto"])
    R.scoreboard(d, featured, y + 40, 130)
    leagues = len({m["competition"] for m in matches})
    fl = font("label", 22)
    _centered(d, f"{len(matches)} PARTIDOS · {leagues} {'LIGA' if leagues == 1 else 'LIGAS'}", fl, y + 210, B.SECUNDARIO, 4)

    # otros resultados destacados, de mayor a menor interés
    y += 270
    tracked(d, (s(62), s(y)), "TAMBIÉN PASÓ", font("label", 20), B.ACENTO, 4)
    y += 44
    fr, fs = font("strong", 30), font("score", 38)
    for m in [m for m in highlights if m["id"] != featured["id"]][:4]:
        d.rectangle([s(62), s(y), s(W - 62), s(y + 70)], fill=B.GRAFITO)
        mid = y + 35
        score = f"{m['home']['score']} – {m['away']['score']}"
        sw = R.text_w(score, fs)
        _, st, _, sb = fs.getbbox("0")
        _, ft, _, fb = fr.getbbox("Ag")
        paint(d, (s(W / 2 - sw / 2), s(mid) - (st + sb) / 2), score, fs, B.NUMEROS)
        R.mini_crest(d, m["home"], W / 2 - sw / 2 - 40, mid, 40)
        paint(d, (s(W / 2 - sw / 2 - 72) - fr.getlength(m["home"]["name"]), s(mid) - (ft + fb) / 2), m["home"]["name"], fr, B.TEXTO)
        R.mini_crest(d, m["away"], W / 2 + sw / 2 + 40, mid, 40)
        paint(d, (s(W / 2 + sw / 2 + 72), s(mid) - (ft + fb) / 2), m["away"]["name"], fr, B.TEXTO)
        y += 82
    _swipe(d)
    R.footer(d, "ESPN")
    return R.finish(img, out)


def results_carousel(featured: dict, matches: list[dict], out_dir: Path, date: dt.date,
                     highlights: list[dict]) -> list[Path]:
    """Portada + resultado destacado + una slide de resultados por competición (máx. 10)."""
    by_comp: dict[str, list[dict]] = {}
    for m in matches:
        by_comp.setdefault(m["competition"], []).append(m)
    comps = list(by_comp)[:8]
    n = 2 + len(comps)
    paths = [results_cover(featured, matches, out_dir / "fecha-1.jpg", n, date, highlights),
             R.render_result({**featured, "date": date}, out_dir / "fecha-2.jpg")]
    for k, comp in enumerate(comps, start=3):
        rows = [{"competition": comp, "home": m["home"]["name"], "away": m["away"]["name"],
                 "home_score": m["home"]["score"], "away_score": m["away"]["score"],
                 "home_team": m["home"], "away_team": m["away"]} for m in by_comp[comp][:9]]
        paths.append(R.render_list(comp, "Resultados", rows, out_dir / f"fecha-{k}.jpg", kind="results"))
    return paths
