"""Llamadas a Claude con salida JSON y control de gasto mensual.

Cada llamada anota su costo en data/gasto.json. Si el mes se acerca al presupuesto
(config.json → presupuesto_mensual_usd), primero se corta lo menos importante:
la revisión de última hora se detiene al 70 % del presupuesto y el resto al 100 %.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import anthropic

import brand as B

MODEL = os.environ.get("PF_MODEL", "claude-opus-5-5")
# USD por millón de tokens (entrada, salida). El razonamiento se cobra como salida.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
LEDGER = B.ROOT / "data" / "gasto.json"
CFG = json.loads((B.ROOT / "config.json").read_text(encoding="utf-8"))
# fracción del presupuesto a partir de la cual cada tarea deja de llamar a Claude
CUTOFF = {"ultima_hora": 0.7, "comentarios": 0.9, "noticias": 1.0, "revision": 1.0}


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _month() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}


def spent(month: str | None = None) -> float:
    return _ledger().get(month or _month(), {}).get("total", 0.0)


def budget() -> float:
    return float(CFG.get("presupuesto_mensual_usd", 30))


def allowed(task: str) -> bool:
    if not available():
        return False
    return spent() < budget() * CUTOFF.get(task, 1.0)


def _record(task: str, usage, model: str) -> float:
    pin, pout = PRICES.get(model, PRICES.get(MODEL, (4.0, 20.0)))
    tokens_in = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    tokens_cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = (tokens_in * pin + tokens_cached * pin * 0.1 + (usage.output_tokens or 0) * pout) / 1e6
    data = _ledger()
    month = data.setdefault(_month(), {"total": 0.0, "llamadas": 0, "por_tarea": {}})
    month["total"] = round(month["total"] + cost, 4)
    month["llamadas"] += 1
    month["por_tarea"][task] = round(month["por_tarea"].get(task, 0.0) + cost, 4)
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return cost


def ask_json(task: str, system: str, prompt: str, schema: dict, effort: str = "medium",
             max_tokens: int = 16000) -> dict | None:
    """Pide a Claude una respuesta que cumple `schema`. None si no hay presupuesto o falla."""
    if not allowed(task):
        print(f"[ia] {task}: sin clave o presupuesto agotado ({spent():.2f} de {budget():.0f} USD este mes)")
        return None
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        print(f"[ia] {task}: límite de uso, se reintenta en la próxima ejecución ({e})")
        return None
    except anthropic.APIStatusError as e:
        print(f"[ia] {task}: error de la API {e.status_code}: {e.message}")
        return None
    except anthropic.APIConnectionError as e:
        print(f"[ia] {task}: sin conexión con la API ({e})")
        return None
    cost = _record(task, response.usage, response.model)
    print(f"[ia] {task}: {cost:.4f} USD (mes: {spent():.2f} de {budget():.0f})")
    if response.stop_reason in ("refusal", "max_tokens"):
        print(f"[ia] {task}: respuesta incompleta ({response.stop_reason})")
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    return json.loads(text) if text else None
