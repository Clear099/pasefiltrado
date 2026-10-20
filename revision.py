"""Revisión semanal autónoma: analiza las métricas, ajusta el bot y deja un reporte.

1. Resume el rendimiento de la semana por tipo de post y por hora (data/metricas.json).
2. Claude escribe el reporte y propone ajustes a parámetros de config.json.
3. Los ajustes se aplican solo dentro de rangos seguros (LIMITES) y si config.json lo permite
   (revision.auto_aplicar); si no, quedan como propuesta en el reporte.
4. El reporte queda en reportes/AAAA-MM-DD.md y, en GitHub Actions, se abre un issue para avisar.

Uso: python revision.py [--sin-aplicar]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from statistics import mean

import requests

import brand as B
import ia
from run import CFG, ROOT, TZ, load

# parámetro → (mínimo, máximo) o, para listas de horas, (cantidad máxima, hora mínima, hora máxima)
LIMITES = {
    "news_per_run": (0, 2),
    "instant_min_interest": (10, 20),
    "instant_max_per_day": (0, 6),
    "max_posts_per_day": (3, 8),
    "max_news_age_hours": (6, 24),
    "horas_noticias": (4, 8, 23),
}

SYSTEM = f"""Eres el responsable de crecimiento de {B.NAME} ({B.HANDLE}), una cuenta automatizada de noticias de
fútbol en Instagram para Latinoamérica y España (Champions, las 5 grandes de Europa, Libertadores).
Cada semana revisas los datos, decides ajustes concretos y explicas por qué, en español claro y breve.

Principios:
- Lo que más pesa en Instagram: envíos por DM (shares), guardados (saved), alcance a no seguidores y seguidores ganados.
- Pocas publicaciones buenas valen más que muchas mediocres.
- Con pocos datos (menos de ~10 posts de un tipo), sé prudente: ajustes pequeños o ninguno, y dilo.
- Solo puedes cambiar estos parámetros, dentro de estos rangos: {json.dumps(LIMITES)}.
  horas_noticias son horas de Chile (0-23) en que sale una noticia.
- Si un cambio no está claramente respaldado por los datos, no lo hagas: proponlo como idea."""

SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "3 a 5 frases: cómo fue la semana y qué se decidió"},
        "hallazgos": {"type": "array", "items": {"type": "string"}, "description": "lo que dicen los datos, con cifras"},
        "ajustes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "parametro": {"type": "string", "enum": list(LIMITES)},
                    "valor": {"type": "string", "description": "nuevo valor en JSON, ej. 2 o [12, 19]"},
                    "motivo": {"type": "string"},
                },
                "required": ["parametro", "valor", "motivo"],
                "additionalProperties": False,
            },
        },
        "ideas": {"type": "array", "items": {"type": "string"},
                  "description": "mejoras que requieren cambiar código o diseño, para revisarlas con el dueño"},
    },
    "required": ["resumen", "hallazgos", "ajustes", "ideas"],
    "additionalProperties": False,
}


def clamp(param: str, raw: str):
    """Valida y recorta el valor propuesto a su rango; None si no es válido."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    lim = LIMITES[param]
    if param == "horas_noticias":
        if not isinstance(value, list):
            return None
        hours = sorted({int(h) for h in value if isinstance(h, (int, float)) and lim[1] <= int(h) <= lim[2]})
        return hours[: lim[0]]
    if not isinstance(value, (int, float)):
        return None
    return int(min(max(value, lim[0]), lim[1]))


def summary(days: int = 7) -> dict:
    data = load("metricas.json", {"seguidores": [], "posts": {}})
    since = dt.datetime.now(TZ) - dt.timedelta(days=days)
    posts = [p for p in data["posts"].values() if dt.datetime.fromisoformat(p["fecha"]) >= since]

    def stats(group):
        keys = ["reach", "views", "saved", "shares", "follows", "total_interactions", "comments", "likes"]
        return {"posts": len(group), **{k: round(mean([p["metricas"].get(k) or 0 for p in group]), 1) for k in keys}}

    by_kind, by_hour = {}, {}
    for p in posts:
        by_kind.setdefault(p["tipo"], []).append(p)
        by_hour.setdefault(dt.datetime.fromisoformat(p["fecha"]).hour, []).append(p)
    followers = data["seguidores"]
    week = [f for f in followers if f["fecha"] >= since.date().isoformat()]
    comments = [c for c in load("comentarios.json", {"registro": []})["registro"] if c["fecha"] >= since.isoformat()]
    ranked = sorted(posts, key=lambda p: (p["metricas"].get("shares") or 0) * 3 + (p["metricas"].get("saved") or 0) * 2
                    + (p["metricas"].get("reach") or 0) / 100, reverse=True)
    return {
        "periodo_dias": days,
        "seguidores": {"inicio": week[0]["valor"] if week else None, "fin": week[-1]["valor"] if week else None},
        "por_tipo": {k: stats(v) for k, v in by_kind.items()},
        "por_hora_chile": {h: stats(v) for h, v in sorted(by_hour.items())},
        "mejores": [{"titulo": p["titulo"], "tipo": p["tipo"], "metricas": p["metricas"]} for p in ranked[:3]],
        "peores": [{"titulo": p["titulo"], "tipo": p["tipo"], "metricas": p["metricas"]} for p in ranked[-3:]],
        "comentarios": {k: sum(1 for c in comments if c["accion"] == k) for k in ("responder", "ocultar", "ignorar")},
        "gasto_mes_usd": round(ia.spent(), 2),
        "presupuesto_mes_usd": ia.budget(),
        "config_actual": {k: CFG.get(k) for k in LIMITES},
    }


def open_issue(title: str, body: str) -> None:
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                      json={"title": title, "body": body[:60000], "labels": ["reporte"]})
    print(f"[revisión] issue: {r.status_code}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-aplicar", action="store_true", help="solo propone, no cambia config.json")
    args = ap.parse_args()

    data = summary()
    total_posts = sum(v["posts"] for v in data["por_tipo"].values())
    print(f"[revisión] {total_posts} posts en la semana")
    result = ia.ask_json("revision", SYSTEM, "Datos de la semana:\n" + json.dumps(data, ensure_ascii=False, indent=1),
                         SCHEMA, effort="high", max_tokens=16000)
    if result is None:
        return

    auto = CFG.get("revision", {}).get("auto_aplicar", True) and not args.sin_aplicar
    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    applied, proposed = [], []
    for a in result["ajustes"]:
        value = clamp(a["parametro"], a["valor"])
        if value is None or value == cfg.get(a["parametro"]):
            continue
        line = f"- `{a['parametro']}`: {cfg.get(a['parametro'])} → {value}. {a['motivo']}"
        if auto:
            cfg[a["parametro"]] = value
            applied.append(line)
        else:
            proposed.append(line)
    if applied:
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    today = dt.datetime.now(TZ).date().isoformat()
    report = "\n".join([
        f"# Reporte semanal · {today}", "", result["resumen"], "",
        "## Lo que dicen los datos", *[f"- {h}" for h in result["hallazgos"]], "",
        "## Ajustes aplicados", *(applied or ["- Ninguno esta semana."]), "",
        *(["## Ajustes propuestos (sin aplicar)", *proposed, ""] if proposed else []),
        "## Ideas para revisar juntos", *([f"- {i}" for i in result["ideas"]] or ["- Ninguna."]), "",
        f"Seguidores: {data['seguidores']['inicio']} → {data['seguidores']['fin']} · "
        f"Gasto en Claude este mes: {data['gasto_mes_usd']} de {data['presupuesto_mes_usd']} USD",
    ])
    out = ROOT / "reportes" / f"{today}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report + "\n", encoding="utf-8")
    print(report)
    open_issue(f"Reporte semanal {today}", report)


if __name__ == "__main__":
    main()
