"""Obtiene un token de larga duración (60 días) de Threads para la cuenta propia. Se corre una vez, local.

Uso: python threads_token.py
Te pide el ID y la clave secreta de la app de Threads (no se guardan), abre la ventana de autorización
y, cuando pegas la dirección a la que te redirige, imprime el token para guardarlo como secreto
THREADS_ACCESS_TOKEN en GitHub.
"""
from __future__ import annotations

import getpass
import urllib.parse
import webbrowser

import requests

REDIRECT = "https://localhost/"  # debe estar en "URI de redireccionamiento" de la app (con la misma barra final)


def main() -> None:
    app_id = input("ID de la app de Threads: ").strip()
    secret = getpass.getpass("Clave secreta de la app de Threads (no se muestra): ").strip()
    url = "https://threads.com/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id, "redirect_uri": REDIRECT, "scope": "threads_basic,threads_content_publish",
        "response_type": "code"})
    print(f"\nAbre esta dirección, acepta y copia la dirección completa a la que te lleva:\n{url}\n")
    webbrowser.open(url)
    back = input("Pega aquí la dirección (https://localhost/?code=...): ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query).get("code", [back])[0].split("#")[0]

    short = requests.post("https://graph.threads.com/oauth/access_token", timeout=30, data={
        "client_id": app_id, "client_secret": secret, "grant_type": "authorization_code",
        "redirect_uri": REDIRECT, "code": code}).json()
    if "access_token" not in short:
        raise SystemExit(f"No se pudo obtener el token: {short}")
    long = requests.get("https://graph.threads.com/access_token", timeout=30, params={
        "grant_type": "th_exchange_token", "client_secret": secret, "access_token": short["access_token"]}).json()
    if "access_token" not in long:
        raise SystemExit(f"No se pudo pasar a token de larga duración: {long}")
    print(f"\nListo (vence en {long.get('expires_in', 0) // 86400} días). Guarda esto como secreto THREADS_ACCESS_TOKEN:\n")
    print(long["access_token"])


if __name__ == "__main__":
    main()
