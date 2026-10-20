"""Publica en Threads lo mismo que se publicó en Instagram (API oficial de Threads).

Variable de entorno: THREADS_ACCESS_TOKEN (token de larga duración, 60 días; se obtiene con
threads_token.py y se renueva solo con el workflow "Renovar token").
"""
from __future__ import annotations

import os
import time

import requests

API = "https://graph.threads.com/v1.0"
LIMIT_BYTES = 500  # Threads cuenta el límite de texto en bytes UTF-8 (los emojis pesan más)


def available() -> bool:
    return bool(os.environ.get("THREADS_ACCESS_TOKEN"))


def call(method: str, path: str, **params) -> dict:
    params["access_token"] = os.environ["THREADS_ACCESS_TOKEN"]
    r = requests.request(method, f"{API}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Threads {path}: {data.get('error', data)}")
    return data


def short_text(caption: str) -> str:
    """El caption de Instagram, recortado por párrafos hasta caber en 500 bytes (sin el bloque de hashtags)."""
    paragraphs = [p for p in caption.split("\n\n") if p.strip() and not p.lstrip().startswith("#")]
    out = ""
    for p in paragraphs:
        trial = f"{out}\n\n{p}" if out else p
        if len(trial.encode("utf-8")) > LIMIT_BYTES:
            break
        out = trial
    if not out:  # un primer párrafo demasiado largo: se corta por caracteres
        out = paragraphs[0] if paragraphs else ""
        while len(out.encode("utf-8")) > LIMIT_BYTES - 3:
            out = out[:-1]
        out = out.rstrip() + "…"
    return out


def wait_ready(container: str, tries: int = 24) -> None:
    for _ in range(tries):
        status = call("GET", container, fields="status,error_message")
        if status.get("status") in ("FINISHED", "PUBLISHED"):
            return
        if status.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads no pudo procesar el contenido: {status.get('error_message')}")
        time.sleep(5)
    raise RuntimeError("Threads tardó demasiado en procesar el contenido")


def publish_entry(entry: dict, base: str) -> str:
    """Publica la portada (o el carrusel completo) con el texto recortado. Devuelve el id del post."""
    text = short_text(entry["caption"])
    images = entry.get("images") or [entry["image"]]
    if len(images) >= 2:
        children = []
        for path in images[:20]:
            child = call("POST", "me/threads", media_type="IMAGE", image_url=f"{base}/{path}", is_carousel_item="true")["id"]
            children.append(child)
        for child in children:
            wait_ready(child)
        container = call("POST", "me/threads", media_type="CAROUSEL", children=",".join(children), text=text)["id"]
    else:
        container = call("POST", "me/threads", media_type="IMAGE", image_url=f"{base}/{images[0]}", text=text)["id"]
    wait_ready(container)
    return call("POST", "me/threads_publish", creation_id=container)["id"]
