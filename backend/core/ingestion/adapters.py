"""Modular event adapters — normalize provider-specific payloads to CommonEvent.

An adapter's single job is to turn an external system's raw JSON into the
vendor-neutral ``CommonEvent`` shape. New integrations plug in by registering a
new adapter here; the core platform and proof engine are never touched.

The ``generic`` adapter is field-mapping driven, so many integrations need no
new code at all — only an ``field_map`` on the integration configuration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from models.ingestion import CommonEvent


class AdapterError(ValueError):
    """Raised when an inbound payload cannot be normalized."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _first(payload: Dict[str, Any], *keys: str):
    for k in keys:
        if k in payload and payload[k] not in (None, ""):
            return payload[k]
    return None


class EventAdapter:
    """Base adapter. Subclasses implement ``normalize``."""
    name = "base"

    def normalize(self, payload: Dict[str, Any], integration: dict) -> CommonEvent:  # pragma: no cover
        raise NotImplementedError


class GenericEventAdapter(EventAdapter):
    """Configurable, application/industry-agnostic adapter.

    Resolution order for each canonical field:
      1. the integration's ``field_map`` (canonical -> source key), then
      2. a set of common fallback aliases, then
      3. safe defaults.
    """
    name = "generic"

    _ALIASES = {
        "event_type": ("event_type", "type", "eventType", "action", "name"),
        "external_id": ("external_id", "id", "event_id", "eventId", "reference", "ref"),
        "occurred_at": ("occurred_at", "timestamp", "time", "created_at", "createdAt", "date"),
        "actor": ("actor", "actor_id", "user", "user_id", "userId", "source_id", "initiator"),
        "subject": ("subject", "subject_id", "resource", "target", "object"),
        "amount": ("amount", "value", "quantity"),
        "currency": ("currency", "ccy"),
        "idempotency_key": ("idempotency_key", "idempotencyKey", "dedupe_key"),
    }

    def _resolve(self, canonical: str, payload: Dict[str, Any], field_map: Dict[str, str]):
        if canonical in field_map:
            mapped = field_map[canonical]
            if mapped in payload:
                return payload[mapped]
        return _first(payload, *self._ALIASES.get(canonical, (canonical,)))

    def normalize(self, payload: Dict[str, Any], integration: dict) -> CommonEvent:
        if not isinstance(payload, dict):
            raise AdapterError("event payload must be a JSON object")

        field_map = integration.get("field_map") or {}

        event_type = self._resolve("event_type", payload, field_map) or "event"
        external_id = self._resolve("external_id", payload, field_map)
        if not external_id:
            raise AdapterError("event must include an identifier (external_id/id/event_id or a mapped field)")
        occurred_at = self._resolve("occurred_at", payload, field_map) or _now_iso()

        amount_raw = self._resolve("amount", payload, field_map)
        try:
            amount = int(amount_raw) if amount_raw is not None else 0
        except (TypeError, ValueError):
            raise AdapterError("amount must be an integer in the smallest unit")
        if amount < 0:
            raise AdapterError("amount must be >= 0")

        currency = self._resolve("currency", payload, field_map) or integration.get("default_currency") or "USD"

        # Everything not consumed above is preserved as attributes (metadata).
        consumed = set()
        for canonical in self._ALIASES:
            consumed.add(field_map.get(canonical, ""))
            consumed.update(self._ALIASES[canonical])
        attributes = {k: v for k, v in payload.items() if k not in consumed}

        return CommonEvent(
            event_type=str(event_type)[:128],
            external_id=str(external_id)[:256],
            occurred_at=str(occurred_at),
            source=integration.get("slug"),
            actor=(str(self._resolve("actor", payload, field_map))[:256]
                   if self._resolve("actor", payload, field_map) is not None else None),
            subject=(str(self._resolve("subject", payload, field_map))[:256]
                     if self._resolve("subject", payload, field_map) is not None else None),
            amount=amount,
            currency=str(currency)[:3],
            attributes=attributes,
            idempotency_key=(str(self._resolve("idempotency_key", payload, field_map))[:256]
                             if self._resolve("idempotency_key", payload, field_map) is not None else None),
        )


_ADAPTERS: Dict[str, EventAdapter] = {
    "generic": GenericEventAdapter(),
}


def get_adapter(name: str) -> EventAdapter:
    adapter = _ADAPTERS.get((name or "generic").lower())
    if adapter is None:
        raise AdapterError(f"unknown adapter: {name}")
    return adapter


def register_adapter(adapter: EventAdapter) -> None:
    """Extension hook: register a new adapter (lightweight integration path)."""
    _ADAPTERS[adapter.name] = adapter
