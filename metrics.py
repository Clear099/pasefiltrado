"""Junta las estadísticas de la cuenta y de cada post en data/metricas.json.

Requiere el permiso instagram_business_manage_insights en el token.
Uso: python metrics.py
"""
from __future__ import annotations

import datetime as dt

import requests

from publish import ig, user_id
from run import TZ, load, save

MEDIA_METRICS = ["reach", "views", "likes", "comments", "saved", "shares", "total_interactions", "follows",
                 "profile_visits"]
KINDS = {"preview": "previa", "match": "resultado", "results": "fecha_en_1_minuto", "news": "noticia",
         "intro": "presentacion", "agenda": "agenda"}


def media_insights(media_id: str) -> dict:
    """Pide todas las métricas juntas; si alguna no aplica a ese post, las pide de a una."""
    def parse(data):
        return {m["name"]: (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
                for m in data.get("data", [])}
    try:
        return parse(ig("GET", f"{media_id}/insights", metric=",".join(MEDIA_METRICS)))
    except RuntimeError:
        out = {}
        for metric in MEDIA_METRICS:
            try:
                out.update(parse(ig("GET", f"{media_id}/insights", metric=metric)))
            except RuntimeError:
                pass
        return out


def kind_of(key: str) -> str:
    return KINDS.get(key.split(":", 1)[0], "otro")


def main() -> None:
    data = load("metricas.json", {"seguidores": [], "posts": {}})
    try:
        acc = ig("GET", user_id(), fields="followers_count,media_count,username")
        media = ig("GET", f"{user_id()}/media", fields="id,caption,media_type,timestamp,permalink,like_count,comments_count",
                   limit=50).get("data", [])
    except (RuntimeError, requests.RequestException) as e:
        print(f"[métricas] no se pudieron leer: {e}")
        return

    today = dt.datetime.now(TZ).date().isoformat()
    data["seguidores"] = [s for s in data["seguidores"] if s["fecha"] != today]
    data["seguidores"].append({"fecha": today, "valor": acc.get("followers_count", 0)})

    by_media = {h.get("media_id"): h for h in load("history.json", []) if h.get("media_id")}
    limit = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    for m in media:
        ts = dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts < limit:
            continue
        hist = by_media.get(m["id"], {})
        entry = data["posts"].setdefault(m["id"], {})
        entry.update({
            "key": hist.get("key", ""),
            "tipo": kind_of(hist.get("key", "")) if hist else "manual",
            "titulo": hist.get("title") or (m.get("caption") or "")[:80],
            "fecha": ts.astimezone(TZ).isoformat(),
            "formato": m.get("media_type"),
            "permalink": m.get("permalink"),
            "metricas": {"likes": m.get("like_count"), "comments": m.get("comments_count"), **media_insights(m["id"])},
            "actualizado": dt.datetime.now(TZ).isoformat(),
        })
    save("metricas.json", data)
    print(f"[métricas] {acc.get('followers_count', 0)} seguidores, {len(data['posts'])} posts con datos")


if __name__ == "__main__":
    main()
