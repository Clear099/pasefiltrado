"""Redacción de los posts: Claude elige las noticias y escribe titular, bajada y caption.

Sin ANTHROPIC_API_KEY funciona en modo básico: usa el titular original de la fuente.
"""
from __future__ import annotations

import json
import os

import anthropic

MODEL = os.environ.get("PF_MODEL", "claude-opus-5-5")

CATEGORIES = ["ÚLTIMA HORA", "FICHAJES", "NOTICIA", "DATO", "SELECCIÓN", "POLÉMICA"]

SYSTEM = """Eres el editor de PASE FILTRADO, una cuenta de Instagram de noticias de fútbol en español \
para todo el público hispanohablante: Latinoamérica (México, Colombia, Argentina, Chile, Perú y el resto) y España.
Voz de marca: directa, rápida, con chispa futbolera pero sin clickbait ni sensacionalismo. \
"Filtramos el ruido. Te pasamos el fútbol."

Reglas editoriales:
- Usa solo hechos que estén en el material de la fuente. Nunca inventes cifras, fechas, montos, citas ni nombres.
- Si una noticia es rumor, dilo ("según X", "apunta a").
- Escribe el titular con tus propias palabras; no copies el titular original.
- Español neutro, que se entienda igual en México, Buenos Aires o Madrid. Traduce al español las fuentes en inglés.
- Enfoque de la cuenta, en este orden: Champions League; las 5 grandes ligas de Europa (LaLiga, Premier League, \
Serie A, Bundesliga, Ligue 1); Copa Libertadores; y solo lo importante del fútbol sudamericano (clásicos y \
grandes de Argentina, Brasil, Uruguay, Chile y Colombia, Eliminatorias, selecciones). Dentro de eso: fichajes, \
lesiones de figuras, despidos de entrenadores, récords y latinoamericanos que brillan en Europa.
- Descarta ligas menores y partidos sin peso, aunque sean noticia local.
- Descarta notas de opinión, previas genéricas, apuestas, publicidad, otros deportes, y temas ya publicados.

Semáforo de fichajes (campo status):
- CONFIRMADO: el club o el jugador lo anunció oficialmente, o la fuente dice que está cerrado/firmado.
- AVANZADO: negociación avanzada, acuerdo verbal, "a falta de detalles".
- RUMOR: interés, sondeo, "según X", "apunta a".
- NO APLICA: noticias que no son fichajes.
Si dudas entre dos niveles, elige el más bajo. Nunca marques CONFIRMADO sin que la fuente lo diga.

Caption (el texto del post):
- Primera línea: un gancho corto que haga querer leer más; es lo único que se ve sin tocar "más".
- 2 a 4 líneas de contexto con los datos clave.
- Cierra con una pregunta concreta y debatible (no "¿qué opinas?"), por ejemplo "¿Es el mejor fichaje del verano?".
- Cuando calce de forma natural, invita a enviarlo: "Mándaselo a tu amigo culé" (enviar por DM es lo que más ayuda al alcance).
- Si hay un ángulo latinoamericano o español (un jugador, una selección, un club), destácalo.
- Máximo 2 emojis. Sin hashtags dentro del caption (van aparte)."""

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer", "description": "índice de la noticia elegida"},
                    "template": {"type": "string", "enum": ["news", "stat"]},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "status": {"type": "string", "enum": ["CONFIRMADO", "AVANZADO", "RUMOR", "NO APLICA"]},
                    "competition": {"type": "string", "description": "liga o torneo, vacío si no aplica"},
                    "headline": {"type": "string", "description": "titular de 6 a 12 palabras"},
                    "highlight": {"type": "array", "items": {"type": "string"},
                                  "description": "1 o 2 palabras del titular a destacar en color (club o jugador)"},
                    "number": {"type": "string", "description": "solo para template stat: la cifra protagonista, ej. '7' o '100M'"},
                    "summary": {"type": "string", "description": "bajada de 1 o 2 frases, máximo 200 caracteres"},
                    "caption": {"type": "string", "description": "texto del post: gancho en la primera línea, 2-4 líneas de contexto, una pregunta para comentar. Máximo 2 emojis."},
                    "hashtags": {"type": "array", "items": {"type": "string"}, "description": "4 a 7 hashtags específicos sin #"},
                },
                "required": ["candidate", "template", "category", "status", "competition", "headline", "highlight",
                             "number", "summary", "caption", "hashtags"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}


def has_ai() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def pick_and_write(candidates: list[dict], recent_titles: list[str], n: int,
                   focus: str | None = None, only_important: bool = False) -> list[dict]:
    """Elige hasta n noticias y redacta sus posts.

    focus: el partido del día; sus noticias tienen prioridad.
    only_important: modo monitor; devuelve [] si no hay nada que justifique publicar ya.
    """
    if not candidates:
        return []
    if not has_ai():
        return [] if only_important else _basic(candidates, n)

    listing = "\n".join(
        f"[{i}] ({c['source']}, hace {c['age_hours']} h, {c['lang']}) {c['title']}"
        + (f"\n    {c['summary']}" if c["summary"] else "")
        for i, c in enumerate(candidates[:80])
    )
    recent = "\n".join(f"- {t}" for t in recent_titles[-40:]) or "(nada todavía)"
    focus_txt = (f"Hoy el partido del día es {focus}. Si hay noticias relevantes de ese partido "
                 "(alineaciones, bajas, declaraciones, polémicas, resultado), dales prioridad.\n") if focus else ""
    if only_important:
        rule = ("Publica SOLO si hay algo que no puede esperar: un hecho de ÚLTIMA HORA confirmado y de impacto, "
                "un fichaje CONFIRMADO de un club grande o algo importante del partido del día. "
                "Si no hay nada así, devuelve posts vacío; publicar relleno daña la cuenta.\n")
    else:
        rule = "Si las candidatas son flojas, devuelve menos posts: mejor no publicar que publicar relleno.\n"
    prompt = f"""Elige hasta {n} noticias para publicar ahora y redacta cada post.
{focus_txt}{rule}
Usa template "stat" solo si la noticia gira en torno a una cifra llamativa; si no, "news".
Usa "ÚLTIMA HORA" solo para hechos confirmados y de impacto ocurridos en las últimas horas.
No elijas dos posts sobre el mismo tema, ni temas parecidos a los ya publicados.

Ya publicados recientemente:
{recent}

Noticias candidatas:
{listing}"""

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": POST_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        print("[redactor] Claude rechazó la solicitud, uso modo básico")
        return _basic(candidates, n)
    text = next(b.text for b in response.content if b.type == "text")
    posts = json.loads(text)["posts"][:n]
    for p in posts:
        src = candidates[p["candidate"]]
        p["source"] = src["source"]
        p["link"] = src["link"]
        p["original_title"] = src["title"]
    return posts


def _basic(candidates: list[dict], n: int) -> list[dict]:
    """Sin IA: primeras noticias en español, con el titular de la fuente."""
    posts = []
    for c in candidates:
        if c["lang"] != "es":
            continue
        posts.append({
            "template": "news",
            "category": "NOTICIA",
            "status": "NO APLICA",
            "competition": "",
            "headline": c["title"],
            "highlight": [],
            "number": "",
            "summary": c["summary"][:200],
            "caption": f"{c['title']}\n\n¿Qué opinas? Te leemos en los comentarios 👇",
            "hashtags": [],
            "source": c["source"],
            "link": c["link"],
            "original_title": c["title"],
        })
        if len(posts) == n:
            break
    return posts
