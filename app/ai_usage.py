"""OpenAI usage telemetry. No prompts, answers, secrets or database writes.

HTTP hooks observe each SDK retry and usage before structured-output parsing.
The in-memory summary is per process; structured logs can be aggregated offline.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import threading
import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

logger = logging.getLogger("uvicorn.error")
PRICE_VERSION = "openai-standard-usd-2026-10-17"
# USD per million tokens: input, cached input, output. Exact model names only.
PRICES = {
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("0.10"), Decimal("1.60")),
    "gpt-4.1-mini-2025-04-14": (Decimal("0.40"), Decimal("0.10"), Decimal("1.60")),
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0.02"), Decimal("0")),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def token_usage(payload: dict) -> dict:
    usage = payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    embedding = "prompt_tokens" in usage and "input_tokens" not in usage
    details = usage.get("input_tokens_details") or {}
    details = details if isinstance(details, dict) else {}
    return {
        "input_tokens": _integer(usage.get("prompt_tokens" if embedding else "input_tokens")),
        "output_tokens": 0 if embedding else _integer(usage.get("output_tokens")),
        "cached_input_tokens": 0 if embedding else _integer(details.get("cached_tokens", 0)),
        "total_tokens": _integer(usage.get("total_tokens")),
    }


def estimated_cost(model: str, tokens: dict, tier: str | None = None) -> float | None:
    rates = PRICES.get(model)
    i, c, o = (tokens.get(k) for k in ("input_tokens", "cached_input_tokens", "output_tokens"))
    if rates is None or tier not in (None, "default", "standard") or any(v is None for v in (i, c, o)) or c > i:
        return None
    return float(((i-c)*rates[0] + c*rates[1] + o*rates[2]) / Decimal(1_000_000))


class UsageMeter:
    """Bounded counters, no per-voting/request history retained in RAM."""
    def __init__(self):
        self.started_at = utc_now()
        self.process_instance = str(uuid4())
        self._lock = threading.Lock()
        self._groups: dict[tuple, dict] = {}

    def record(self, event: dict) -> None:
        key = (event["feature"], event["model"])
        with self._lock:
            if key not in self._groups and len(self._groups) >= 128:
                key = ("other", "other")
            group = self._groups.setdefault(key, {
                "feature": key[0], "model": key[1], "attempts": 0, "retries": 0,
                "http_errors": 0, "transport_unknown": 0, "usage_unknown": 0,
                "cost_unknown": 0, "input_tokens": 0, "output_tokens": 0,
                "cached_input_tokens": 0, "known_estimated_usd": 0.0,
            })
            group["attempts"] += 1
            group["retries"] += int(event["attempt"] > 1)
            group["http_errors"] += int((event.get("http_status") or 0) >= 400)
            group["transport_unknown"] += int(event.get("http_status") is None)
            group["usage_unknown"] += int(event.get("input_tokens") is None or event.get("output_tokens") is None)
            for k in ("input_tokens", "output_tokens", "cached_input_tokens"):
                group[k] += event.get(k) or 0
            if event.get("estimated_usd") is None:
                group["cost_unknown"] += 1
            else:
                group["known_estimated_usd"] += event["estimated_usd"]

    def snapshot(self) -> dict:
        with self._lock:
            groups = [dict(g, known_estimated_usd=round(g["known_estimated_usd"], 10)) for g in self._groups.values()]
        return {
            "scope": "current_process_only", "process_instance": self.process_instance,
            "since": self.started_at, "as_of": utc_now(), "currency": "USD",
            "pricing_version": PRICE_VERSION, "billing_authoritative": False,
            "known_estimated_usd": round(sum(g["known_estimated_usd"] for g in groups), 10),
            "cost_unknown_attempts": sum(g["cost_unknown"] for g in groups),
            "groups": sorted(groups, key=lambda g: (-g["known_estimated_usd"], g["feature"], g["model"])),
        }


meter = UsageMeter()


@dataclass
class CallContext:
    feature: str
    model: str
    reference: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    attempt: int = 0
    pending: bool = False
    started: float = 0


current_call: ContextVar[CallContext | None] = ContextVar("ai_usage_call", default=None)


def _emit_attempt(ctx: CallContext, payload: dict | None, status: int | None, request_id: str | None = None) -> None:
    """Telemetry must never turn a successful generation into a failed one."""
    ctx.pending = False
    try:
        payload = payload or {}
        tokens = token_usage(payload)
        actual_model = payload.get("model")
        model = actual_model if isinstance(actual_model, str) and len(actual_model) < 128 else ctx.model
        event = {
            "event": "ai_usage", "schema_version": 1, "event_id": str(uuid4()),
            "at": utc_now(), "call_id": ctx.id, "feature": ctx.feature, "model": model,
            "reference": ctx.reference, "attempt": ctx.attempt, "http_status": status,
            "request_id": request_id, "latency_ms": round((time.monotonic()-ctx.started)*1000),
            **tokens, "estimated_usd": estimated_cost(model, tokens, payload.get("service_tier")),
            "pricing_version": PRICE_VERSION, "billing_authoritative": False,
        }
        meter.record(event)
        logger.info("AI_USAGE %s", json.dumps(event, ensure_ascii=True, separators=(",", ":")))
    except Exception:
        logger.warning("AI_TELEMETRY_UNAVAILABLE")


async def _on_request(request: httpx.Request) -> None:
    ctx = current_call.get()
    if ctx is not None:
        if ctx.pending:
            # SDK started another attempt after a transport failure with no response.
            _emit_attempt(ctx, None, None)
        ctx.attempt += 1
        ctx.pending = True
        ctx.started = time.monotonic()


async def _on_response(response: httpx.Response) -> None:
    ctx = current_call.get()
    if ctx is None:
        return
    try:
        await response.aread()  # Existing flows use non-streaming JSON only.
    except Exception:
        _emit_attempt(ctx, None, response.status_code, response.headers.get("x-request-id"))
        raise
    try:
        payload = response.json()
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        payload = {}
    _emit_attempt(ctx, payload, response.status_code, response.headers.get("x-request-id"))


def create_observed_client(*, transport: httpx.AsyncBaseTransport | None = None, **kwargs) -> AsyncOpenAI:
    return AsyncOpenAI(**kwargs, http_client=DefaultAsyncHttpxClient(
        event_hooks={"request": [_on_request], "response": [_on_response]},
        transport=transport,
    ))


async def observed_call(feature: str, tracked_model: str, operation: Callable[..., Awaitable], *, reference: dict | None = None, **kwargs):
    ctx = CallContext(feature, tracked_model, reference or {})
    token = current_call.set(ctx)
    outcome = "failed"
    try:
        response = await operation(**kwargs)
        outcome = "completed"
        return response
    finally:
        if ctx.pending:
            _emit_attempt(ctx, None, None)
        current_call.reset(token)
        try:
            logger.info("AI_OPERATION %s", json.dumps({
                "event": "ai_operation", "at": utc_now(), "call_id": ctx.id,
                "feature": feature, "outcome": outcome, "attempts": ctx.attempt,
            }, separators=(",", ":")))
        except Exception:
            pass
