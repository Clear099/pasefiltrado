"""Publica en Instagram los posts en cola (data/pending.json).

Usa la API de Instagram con inicio de sesión de Instagram (no requiere página de Facebook).
Variables de entorno:
    IG_ACCESS_TOKEN   token de larga duración (60 días, renovable con --refresh-token)
    IG_USER_ID        opcional: id de la cuenta de Instagram; si falta, se obtiene del token
    PUBLIC_BASE_URL   URL pública donde quedan las imágenes del repo, por ejemplo
                      https://raw.githubusercontent.com/USUARIO/pasefiltrado/main
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import requests

import threads
from run import CFG, TZ, load, save

API = f"https://graph.instagram.com/{os.environ.get('IG_API_VERSION', 'v24.0')}"


def ig(method: str, path: str, **params) -> dict:
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, f"{API}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram {path}: {data.get('error', data)}")
    return data


_USER: dict = {}


def account() -> dict:
    """Cuenta dueña del token: {"user_id": ..., "username": ..., "account_type": ...}."""
    if not _USER:
        _USER.update(ig("GET", "me", fields="user_id,username,account_type"))
    return _USER


def user_id() -> str:
    return os.environ.get("IG_USER_ID") or str(account()["user_id"])


def check() -> None:
    """Verifica el token sin publicar nada."""
    acc = account()
    print(f"Conectado a @{acc.get('username')} (id {acc.get('user_id')}, tipo {acc.get('account_type')})")
    if acc.get("account_type") not in ("BUSINESS", "MEDIA_CREATOR"):
        sys.exit("La cuenta no es profesional: cámbiala a Creador o Empresa en Instagram para poder publicar.")


def wait_ready(container: str, what: str, tries: int = 30) -> None:
    """Instagram descarga y procesa la imagen (o el video); hay que esperar a que quede FINISHED."""
    for _ in range(tries):
        status = ig("GET", container, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram no pudo procesar {what}")
        time.sleep(5)
    raise RuntimeError(f"Instagram tardó demasiado en procesar {what}")


def publish_entry(entry: dict, base: str) -> str:
    """Publica un post simple ("image") o un carrusel ("images", de 2 a 10)."""
    user = user_id()
    if entry.get("images"):
        children = []
        for path in entry["images"][:10]:
            child = ig("POST", f"{user}/media", image_url=f"{base}/{path}", is_carousel_item="true")["id"]
            wait_ready(child, path)
            children.append(child)
        container = ig("POST", f"{user}/media", media_type="CAROUSEL",
                       children=",".join(children), caption=entry["caption"])["id"]
    else:
        container = ig("POST", f"{user}/media", image_url=f"{base}/{entry['image']}", caption=entry["caption"])["id"]
    wait_ready(container, entry["key"])
    return ig("POST", f"{user}/media_publish", creation_id=container)["id"]


def refresh_token() -> None:
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_ACCESS_TOKEN"]},
                     timeout=30).json()
    if "access_token" not in r:
        sys.exit(f"No se pudo renovar: {r}")
    print(f"Nuevo token (vence en {r['expires_in'] // 86400} días):\n{r['access_token']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-token", action="store_true", help="renueva el token de larga duración")
    ap.add_argument("--check", action="store_true", help="verifica el token y la cuenta sin publicar")
    ap.add_argument("--max", type=int, default=3, help="máximo de posts a publicar en esta ejecución")
    args = ap.parse_args()
    if args.refresh_token:
        return refresh_token()
    if args.check:
        return check()

    base = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    # GitHub sirve los .mp4 como application/octet-stream; jsDelivr los sirve como video/mp4
    video_base = os.environ.get("VIDEO_BASE_URL", base).rstrip("/")
    # una noticia de hace horas ya no es noticia: lo que quedó atrasado en la cola se descarta
    limit = dt.datetime.now(TZ) - dt.timedelta(hours=CFG.get("pending_max_hours", 6))
    pending = []
    for entry in load("pending.json", []):
        if entry.get("created") and dt.datetime.fromisoformat(entry["created"]) < limit:
            print(f"[descartado por antiguo] {entry['key']}")
        else:
            pending.append(entry)
    history = load("history.json", [])
    failed = []
    for i, entry in enumerate(pending):
        if i >= args.max:
            failed.append(entry)  # queda para la próxima ejecución
            continue
        try:
            media_id = publish_entry(entry, base)
        except (RuntimeError, requests.RequestException) as e:
            print(f"[error] {entry['key']}: {e}")
            entry["attempts"] = entry.get("attempts", 0) + 1
            if entry["attempts"] < 3:
                failed.append(entry)
            continue
        print(f"[publicado] {entry['key']} → {media_id}")
        if entry.get("story"):
            try:
                story = ig("POST", f"{user_id()}/media", image_url=f"{base}/{entry['story']}", media_type="STORIES")["id"]
                wait_ready(story, entry["story"])
                ig("POST", f"{user_id()}/media_publish", creation_id=story)
                print(f"[historia] {entry['key']}")
            except (RuntimeError, requests.RequestException) as e:
                print(f"[historia] no se pudo publicar: {e}")  # la historia nunca bloquea el post
        if threads.available():
            try:
                print(f"[threads] {entry['key']} → {threads.publish_entry(entry, base)}")
            except (RuntimeError, requests.RequestException) as e:
                print(f"[threads] no se pudo publicar: {e}")  # Threads nunca bloquea Instagram
        if entry.get("reel"):
            try:
                feed = "true" if CFG.get("reels", {}).get("en_feed", False) else "false"
                reel = ig("POST", f"{user_id()}/media", media_type="REELS", video_url=f"{video_base}/{entry['reel']}",
                          caption=entry["caption"], share_to_feed=feed)["id"]
                wait_ready(reel, entry["reel"], tries=60)  # los videos tardan más en procesarse
                ig("POST", f"{user_id()}/media_publish", creation_id=reel)
                print(f"[reel] {entry['key']}")
            except (RuntimeError, requests.RequestException) as e:
                print(f"[reel] no se pudo publicar: {e}")
        history.append({"key": entry["key"], "title": entry["title"], "image": entry.get("image") or entry["images"][0],
                        "media_id": media_id, "date": dt.datetime.now(TZ).isoformat()})
        if i + 1 < min(len(pending), args.max):
            time.sleep(20)  # no publicar en ráfaga
    save("pending.json", failed)
    save("history.json", history[-500:])


if __name__ == "__main__":
    main()
