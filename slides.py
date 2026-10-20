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


# ---------------------------------------------------------------- presentación de la cuenta (post fijado)

def _rows(d, items: list[tuple[str, str]], y: float, row_h: float = 178, numbered: bool = True) -> float:
    """Filas grandes: número, título y una línea de detalle."""
    for k, (head, sub) in enumerate(items, start=1):
        d.rectangle([s(62), s(y), s(W - 62), s(y + row_h - 16)], fill=B.GRAFITO)
        d.rectangle([s(62), s(y), s(68), s(y + row_h - 16)], fill=B.ACENTO)
        x = 92
        if numbered:
            fn = font("score", 84)
            num = f"{k:02d}"
            _, top, _, bottom = fn.getbbox(num)
            paint(d, (s(x), s(y + (row_h - 16) / 2) - (top + bottom) / 2), num, fn, B.ACENTO)
            x += R.text_w(num, fn) + 28
        fh, lines, hs = R.fit_text(case(head), "display", int(W - 62 - 28 - x), 1, 58, 34)
        paint(d, (s(x), s(y + 22)), lines[0], fh, B.TEXTO)
        fs, slines, ss = R.fit_text(sub, "body", int(W - 62 - 28 - x), 2, 28, 22)
        sy = y + 30 + hs * 1.12
        for line in slines:
            d.text((s(x), s(sy)), line, font=fs, fill=B.SECUNDARIO)
            sy += ss * 1.25
        y += row_h
    return y


def intro_cover(out: Path, n: int) -> Path:
    import logos
    img, d = R.base(right=f"1/{n}")
    logo = logos._insignia(s(560))
    d.canvas.paste(logo, (s(W / 2) - logo.width // 2, s(200)), logo)
    chip_text = "BIENVENIDO"
    fl = font("label", 26)
    cw = R.tracked_len(chip_text, fl, 2) / R.S + 40 + 46 * R.SLANT
    chip(d, W / 2 - cw / 2, 790, chip_text, filled=True)
    lines = [case("Filtramos el ruido."), case("Te pasamos el fútbol.")]
    size = 84
    f = font("display", size)
    y = 868
    for line in lines:
        R.draw_rich_lines(d, [line], f, W / 2 - R.text_w(line, f) / 2, y, size, B.TEXTO, ["fútbol."])
        y += size * B.THEME["leading"]
    _swipe(d)
    R.footer(d, None)
    return R.finish(img, out)


def intro_coverage(out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "COBERTURA")
    y = _title(d, "Lo que cubrimos", ["cubrimos"]) + 30
    _rows(d, [
        ("Champions League", "Cada jornada, de la fase de liga a la final"),
        ("Las 5 grandes de Europa", "LaLiga · Premier League · Serie A · Bundesliga · Ligue 1"),
        ("Copa Libertadores", "La gloria eterna, partido a partido"),
        ("Lo grande de Sudamérica", "Clásicos, Eliminatorias, Copa América y los grandes de cada liga"),
    ], y)
    R.footer(d, None)
    return R.finish(img, out)


def intro_formats(out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "LO QUE VAS A VER")
    y = _title(d, "Así trabajamos", ["trabajamos"]) + 30
    _rows(d, [
        ("Partido del día", "Previa con forma, historial, goleadores y tu pronóstico"),
        ("Resultado al instante", "Minutos después del pitazo final, con los goles"),
        ("La fecha en 1 minuto", "Todos los resultados de la jornada en un carrusel"),
        ("Noticias filtradas", "Solo lo importante, siempre con su fuente"),
    ], y)
    R.footer(d, None)
    return R.finish(img, out)


def intro_traffic_light(out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "FICHAJES")
    y = _title(d, "El semáforo de fichajes", ["fichajes"]) + 40
    items = [
        ("CONFIRMADO", "Firmado y anunciado. Si lo ves, es oficial."),
        ("AVANZADO", "Acuerdo cerca, faltan los últimos detalles."),
        ("RUMOR", "Hay interés o sondeos. Todavía nada cerrado."),
    ]
    for status, text in items:
        d.rectangle([s(62), s(y), s(W - 62), s(y + 190)], fill=B.GRAFITO)
        R.status_badge(d, status, W - 92, y + 62)
        fs, lines, size = R.fit_text(text, "strong", 560, 2, 34, 26)
        ty = y + 40
        for line in lines:
            d.text((s(92), s(ty)), line, font=fs, fill=B.TEXTO)
            ty += size * 1.3
        y += 214
    fl = font("label", 22)
    _centered(d, "NUNCA MARCAMOS COMO CONFIRMADO LO QUE NO LO ESTÁ", fl, y + 18, B.SECUNDARIO, 2)
    R.footer(d, None)
    return R.finish(img, out)


def intro_times(out: Path, i: int, n: int) -> Path:
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "HORARIOS")
    y = _title(d, "Tu hora, tu bandera", ["bandera"]) + 40
    fs, lines, size = R.fit_text("Cada partido con la hora de tu país, de México a España.", "body", W - 124, 2, 36, 28)
    for line in lines:
        d.text((s(62), s(y)), line, font=fs, fill=B.TEXTO)
        y += size * 1.35
    y += 50
    d.rectangle([s(62), s(y), s(W - 62), s(y + 250)], fill=B.GRAFITO)
    fl = font("label", 22)
    _centered(d, "EJEMPLO · NOCHE DE CHAMPIONS EN EUROPA", fl, y + 24, B.SECUNDARIO, 3)
    time_grid(d, dt.datetime(2026, 10, 20, 19, 0, tzinfo=dt.timezone.utc), y + 58)
    y += 330
    codes = list(horarios.PAISES)
    R.flag_row(d, codes[:6], W / 2, y + 40, 74, 18)
    R.flag_row(d, codes[6:], W / 2, y + 132, 74, 18)
    fl = font("label", 26)
    _centered(d, f"{len(codes)} PAÍSES, UNA SOLA CUENTA", fl, y + 200, B.TEXTO, 4)
    R.footer(d, None)
    return R.finish(img, out)


def intro_follow(out: Path, i: int, n: int) -> Path:
    import logos
    img, d = R.base(right=f"{i}/{n}")
    logo = logos._insignia(s(380))
    d.canvas.paste(logo, (s(W / 2) - logo.width // 2, s(190)), logo)
    f, lines, size = R.fit_text(case("Síguenos y activa las notificaciones"), "display", W - 124, 2, 90, 56)
    y = 620
    for line in lines:
        R.draw_rich_lines(d, [line], f, W / 2 - R.text_w(line, f) / 2, y, size, B.TEXTO, ["notificaciones"])
        y += size * B.THEME["leading"]
    fh = font("display", 64)
    paint(d, (s(W / 2) - R.klen(B.HANDLE, fh) / 2, s(y + 30)), B.HANDLE, fh, B.ACENTO)
    fl = font("label", 24)
    _centered(d, "COMPÁRTELO CON TU GRUPO DEL FÚTBOL", fl, y + 150, B.SECUNDARIO, 3)
    R.footer(d, None)
    return R.finish(img, out)


def intro_carousel(out_dir: Path) -> list[Path]:
    """Carrusel de presentación de la cuenta, para fijar en el perfil."""
    builders = [intro_coverage, intro_formats, intro_traffic_light, intro_times, intro_follow]
    n = len(builders) + 1
    paths = [intro_cover(out_dir / "presentacion-1.jpg", n)]
    for i, b in enumerate(builders, start=2):
        paths.append(b(out_dir / f"presentacion-{i}.jpg", i, n))
    return paths


# ---------------------------------------------------------------- resultado: así fue

def result_timeline(m: dict, st: dict, stats: dict, out: Path, i: int = 2, n: int = 2) -> Path:
    """Segundo slide del resultado: cada gol con su minuto y el marcador parcial, y las estadísticas."""
    img, d = R.base(right=f"{i}/{n}")
    chip(d, 62, 196, "ASÍ FUE")
    h, a = m["home"], m["away"]
    # marcador compacto arriba
    R.mini_crest(d, h, 90, 300, 64)
    R.mini_crest(d, a, W - 90, 300, 64)
    fs = font("score", 84)
    score = f"{h['score']} – {a['score']}"
    _, top, _, bottom = fs.getbbox("0")
    paint(d, (s(W / 2) - fs.getlength(score) / 2, s(300) - (top + bottom) / 2), score, fs, B.TEXTO)
    fn = font("display", 40)
    for team, x, right in ((h, 136, False), (a, W - 136, True)):
        name = case(team["name"])
        _, nt, _, nb = fn.getbbox(name)
        px = s(x) - (R.klen(name, fn) if right else 0)
        paint(d, (px, s(300) - (nt + nb) / 2), name, fn, B.TEXTO)

    # línea de tiempo: goles del local a la izquierda, de la visita a la derecha
    timeline = st["linea"][:9]
    y = 390
    # espacio hasta el pie (H - 130), descontando el bloque de estadísticas (título + 4 filas)
    stats_h = (40 + 50 + 4 * 76) if stats else 0
    row = min(70, (H - 130 - stats_h - y) / max(len(timeline), 1))
    d.line([s(W / 2), s(y), s(W / 2), s(y + row * len(timeline))], fill=B.LINEA, width=s(3))
    fm, fp, fsc = font("score", 30), font("strong", int(min(30, row * 0.45))), font("score", 30)
    for t in timeline:
        cy = y + row / 2
        mark = t["score"].replace("-", " – ")
        bw = R.text_w(mark, fsc) + 28
        d.rectangle([s(W / 2 - bw / 2), s(cy - 22), s(W / 2 + bw / 2), s(cy + 22)],
                    fill=B.ACENTO if t is st.get("decisivo") else B.GRAFITO)
        _, top, _, bottom = fsc.getbbox("0")
        paint(d, (s(W / 2) - fsc.getlength(mark) / 2, s(cy) - (top + bottom) / 2), mark, fsc, B.TEXTO)
        who = t["player"]
        minute = t["minute"]
        _, pt, _, pb = fp.getbbox("Ag")
        if t["side"] == "home":
            txt = f"{who}  {minute}"
            while R.text_w(txt, fp) > W / 2 - bw / 2 - 90 and len(who) > 4:
                who = who[:-2].rstrip() + "…"
                txt = f"{who}  {minute}"
            d.text((s(W / 2 - bw / 2 - 24) - fp.getlength(txt), s(cy) - (pt + pb) / 2), txt, font=fp, fill=B.TEXTO)
        else:
            txt = f"{minute}  {who}"
            while R.text_w(txt, fp) > W / 2 - bw / 2 - 90 and len(who) > 4:
                who = who[:-2].rstrip() + "…"
                txt = f"{minute}  {who}"
            d.text((s(W / 2 + bw / 2 + 24), s(cy) - (pt + pb) / 2), txt, font=fp, fill=B.TEXTO)
        y += row

    # estadísticas en barras enfrentadas
    if stats:
        y += 40
        tracked(d, (s(W / 2) - R.tracked_len("ESTADÍSTICAS", font("label", 22), 4) / 2, s(y)), "ESTADÍSTICAS",
                font("label", 22), B.ACENTO, 4)
        y += 50
        fv, fl = font("score", 34), font("label", 20)
        for label in ("Posesión", "Remates", "Al arco", "Córners"):
            hv, av = stats["home"].get(label), stats["away"].get(label)
            if hv is None or av is None:
                continue
            fmt = (lambda v: f"{v:.0f}%") if label == "Posesión" else (lambda v: f"{v:.0f}")
            total = (hv + av) or 1
            bar_w = W - 124 - 2 * 110
            x0 = 62 + 110
            d.rectangle([s(x0), s(y + 34), s(x0 + bar_w), s(y + 46)], fill=B.GRAFITO)
            split = x0 + bar_w * hv / total
            d.rectangle([s(x0), s(y + 34), s(split), s(y + 46)], fill=B.ACENTO if hv >= av else B.SECUNDARIO)
            d.rectangle([s(split + 4), s(y + 34), s(x0 + bar_w), s(y + 46)], fill=B.ACENTO if av > hv else B.SECUNDARIO)
            tracked(d, (s(W / 2) - R.tracked_len(label.upper(), fl, 3) / 2, s(y)), label.upper(), fl, B.SECUNDARIO, 3)
            paint(d, (s(62), s(y + 20)), fmt(hv), fv, B.TEXTO)
            paint(d, (s(W - 62) - fv.getlength(fmt(av)), s(y + 20)), fmt(av), fv, B.TEXTO)
            y += 76
    R.footer(d, "ESPN")
    return R.finish(img, out)
