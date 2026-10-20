"""Responde y modera los comentarios de los posts recientes, con la voz de la marca.

Cada ejecución lee los comentarios nuevos de los posts de los últimos días, le pide a Claude
una decisión por comentario (responder, ocultar o ignorar) y la ejecuta con la API oficial.
Todo queda registrado en data/comentarios.json.

Requiere el permiso instagram_business_manage_comments en el token.
Uso: python comments.py            # responde de verdad
     python comments.py --dry      # solo muestra qué haría
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

import requests

import brand as B
import ia
from publish import account, ig, user_id
from run import CFG, TZ, due, load, save

SYSTEM = f"""Eres quien responde los comentarios de {B.NAME} ({B.HANDLE}), una cuenta de Instagram de noticias \
de fútbol en español para Latinoamérica y España. Lema: "{B.TAGLINE}"

Para cada comentario decide una acción:
- "responder": la mayoría de los comentarios genuinos (opiniones, pronósticos, preguntas, bromas futboleras, elogios).
- "ocultar": insultos, odio, racismo, acoso, contenido sexual, amenazas, spam, estafas, enlaces sospechosos,
  bots ("sígueme", "promo", "DM para colaborar"), o publicidad de apuestas.
- "ignorar": comentarios vacíos o repetidos a los que no vale la pena contestar, o discusiones donde
  responder solo echaría leña al fuego.

Cómo responder:
- Corto: máximo 180 caracteres. Tono cercano y futbolero, con chispa, sin burlarte de nadie ni de ningún club.
- Responde en el idioma del comentario (normalmente español neutro).
- Si dejan un pronóstico, reacciona a ese pronóstico en concreto. Si preguntan algo, responde solo con lo que
  dice el post; si no lo sabes, dilo con naturalidad. Nunca inventes datos.
- Invita a seguir la conversación con una pregunta corta cuando calce, sin forzarlo.
- Como máximo un emoji. Sin hashtags. Sin enlaces.
- Nada de política, religión, apuestas, sorteos ni promesas. No reveles cómo funciona la cuenta por dentro.
- No pidas que te sigan ni que activen notificaciones en cada respuesta; como mucho, de vez en cuando.
- Varía las respuestas: no repitas la misma frase a varias personas."""

SCHEMA = {
    "type": "object",
    "properties": {
        "acciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer"},
                    "accion": {"type": "string", "enum": ["responder", "ocultar", "ignorar"]},
                    "respuesta": {"type": "string", "description": "texto de la respuesta; vacío si no se responde"},
                    "motivo": {"type": "string", "description": "por qué, en pocas palabras"},
                },
                "required": ["idx", "accion", "respuesta", "motivo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["acciones"],
    "additionalProperties": False,
}

STATE = "comentarios.json"


def recent_media(days: int) -> list[dict]:
    data = ig("GET", f"{user_id()}/media", fields="id,caption,timestamp,permalink,comments_count", limit=25)
    limit = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for m in data.get("data", []):
        ts = dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts >= limit and m.get("comments_count", 0) > 0:
            out.append(m)
    return out


def new_comments(media: list[dict], seen: set[str], me: str) -> list[dict]:
    found = []
    for m in media:
        data = ig("GET", f"{m['id']}/comments", fields="id,text,username,timestamp,replies{id,username}", limit=50)
        context = (m.get("caption") or "").split("\n\n")[0][:300]
        for c in data.get("data", []):
            if c["id"] in seen or c.get("username") == me:
                continue
            replied = any(r.get("username") == me for r in c.get("replies", {}).get("data", []))
            found.append({"id": c["id"], "user": c.get("username", ""), "text": c.get("text", ""),
                          "time": c.get("timestamp", ""), "post": context, "replied": replied})
    found.sort(key=lambda c: c["time"])
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="no responde ni oculta, solo muestra las decisiones")
    args = ap.parse_args()
    if not args.dry and not due("comentarios", 55):
        print("[comentarios] ya se revisaron hace menos de una hora")
        return

    cfg = CFG.get("comentarios", {})
    state = load(STATE, {"vistos": [], "registro": []})
    seen = set(state["vistos"])
    try:
        me = account()["username"]
        comments = new_comments(recent_media(cfg.get("dias", 7)), seen, me)
    except (RuntimeError, requests.RequestException) as e:
        # típico: el token aún no tiene el permiso de comentarios
        print(f"[comentarios] no se pudieron leer: {e}")
        return

    pending = [c for c in comments if not c["replied"]]
    for c in comments:
        if c["replied"]:
            seen.add(c["id"])
    today = dt.datetime.now(TZ).date().isoformat()
    replies_today = sum(1 for r in state["registro"] if r["fecha"].startswith(today) and r["accion"] == "responder")
    room = min(cfg.get("max_por_ejecucion", 20), cfg.get("max_por_dia", 150) - replies_today)
    batch = pending[: max(room, 0) + 10]  # un poco más: algunos se ocultan o se ignoran
    print(f"[comentarios] {len(pending)} nuevos, se revisan {len(batch)} (respuestas hoy: {replies_today})")
    if not batch or room <= 0:
        state["vistos"] = list(seen)[-3000:]
        save(STATE, state)
        return

    listing = json.dumps([{"idx": i, "usuario": c["user"], "comentario": c["text"], "post": c["post"]}
                          for i, c in enumerate(batch)], ensure_ascii=False, indent=1)
    result = ia.ask_json("comentarios", SYSTEM, f"Comentarios nuevos (con el texto del post al que responden):\n{listing}",
                         SCHEMA, effort="low", max_tokens=8000)
    if result is None:
        return  # sin decisión no se marca nada como visto: se reintenta en la próxima ejecución

    done_replies, per_user = 0, {}
    for a in result["acciones"]:
        if not 0 <= a["idx"] < len(batch):
            continue
        c = batch[a["idx"]]
        action, text = a["accion"], a["respuesta"].strip()[:300]
        if action == "responder" and (not text or done_replies >= room or per_user.get(c["user"], 0) >= 2):
            action = "ignorar"
        if not args.dry:
            try:
                if action == "responder":
                    ig("POST", f"{c['id']}/replies", message=text)
                elif action == "ocultar":
                    ig("POST", c["id"], hide="true")
            except (RuntimeError, requests.RequestException) as e:
                print(f"[comentarios] error con {c['id']}: {e}")
                continue
        if action == "responder":
            done_replies += 1
            per_user[c["user"]] = per_user.get(c["user"], 0) + 1
        seen.add(c["id"])
        state["registro"].append({"fecha": dt.datetime.now(TZ).isoformat(), "usuario": c["user"],
                                  "comentario": c["text"], "accion": action, "respuesta": text if action == "responder" else "",
                                  "motivo": a["motivo"], "post": c["post"][:80]})
        print(f"[{action}] @{c['user']}: {c['text'][:60]!r}" + (f" → {text!r}" if action == "responder" else ""))

    if not args.dry:
        state["vistos"] = list(seen)[-3000:]
        state["registro"] = state["registro"][-500:]
        save(STATE, state)


if __name__ == "__main__":
    main()
