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


def _dig(payload: Any, path: str):
    """Resolve a (possibly dotted) path against a nested dict.

    ``"data.order.order_id"`` -> payload["data"]["order"]["order_id"]. Returns
    ``None`` if any segment is missing or the value is empty.
    """
    cur = payload
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if cur not in (None, "") else None


def _deep_find_key(obj: Any, key: str, depth: int = 0):
    """Recursively search a nested dict/list for the first non-empty value whose
    key exactly matches ``key`` (depth-bounded). Used only as a last-resort
    identifier fallback so unusual provider nestings still resolve."""
    if depth > 6:
        return None
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
        for v in obj.values():
            r = _deep_find_key(v, key, depth + 1)
            if r not in (None, ""):
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _deep_find_key(v, key, depth + 1)
            if r not in (None, ""):
                return r
    return None


def _first(payload: Dict[str, Any], *keys: str):
    for k in keys:
        val = _dig(payload, k) if "." in k else (payload.get(k) if isinstance(payload, dict) else None)
        if val not in (None, ""):
            return val
    return None


def _to_minor_units(raw: Any) -> int:
    """Normalize a provider amount to the canonical smallest unit (cents).

    Providers report amounts inconsistently: some send major-unit decimals
    (Tazapay/Cashfree ``100.00`` == $100.00) while others already send the
    smallest unit as an integer (Stripe/Razorpay ``10000`` == $100.00). Any value
    carrying a fractional part (a float or a decimal string) is treated as MAJOR
    units and scaled to cents; bare integers are assumed to already be the
    smallest unit. Missing amounts default to 0 (non-financial events).
    """
    if raw in (None, ""):
        return 0
    if isinstance(raw, bool):
        raise AdapterError("amount must be a number")
    if isinstance(raw, float):
        return int(round(raw * 100))
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = raw.strip().replace(",", "")
        try:
            if "." in s:
                return int(round(float(s) * 100))
            return int(s)
        except ValueError:
            raise AdapterError("amount must be a valid number")
    raise AdapterError("amount must be a number")


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
    Field values may be referenced with **dotted paths** (e.g.
    ``data.order.order_id``) so nested provider payloads (Cashfree, etc.)
    normalize with no bespoke code — either via ``field_map`` or the built-in
    nested fallback aliases below.
    """
    name = "generic"

    _ALIASES = {
        "event_type": ("event_type", "type", "eventType", "action", "name"),
        "external_id": (
            "external_id", "id", "event_id", "eventId", "reference", "ref",
            # nested webhook identifiers (Cashfree PG order/payment ids, etc.)
            "data.order.order_id", "data.payment.cf_payment_id", "data.payment.payment_id",
            "order_id", "cf_payment_id", "payment_id", "orderId", "transaction_id",
        ),
        "occurred_at": (
            "occurred_at", "timestamp", "time", "created_at", "createdAt", "date",
            "event_time", "data.payment.payment_time", "data.order.order_time",
        ),
        "actor": ("actor", "actor_id", "user", "user_id", "userId", "source_id", "initiator",
                  "data.customer_details.customer_id"),
        "subject": ("subject", "subject_id", "resource", "target", "object",
                    "data.order.order_id"),
        "amount": (
            "amount", "value", "quantity",
            # nested webhook amounts (Tazapay/Cashfree send major-unit decimals)
            "data.amount", "data.order.amount", "data.order.order_amount",
            "data.payment.amount", "data.payment.payment_amount",
            "data.transaction_amount", "amount.value",
        ),
        "currency": (
            "currency", "ccy", "currency_code",
            "data.currency", "data.order.order_currency",
            "data.payment.currency", "data.currency_code",
        ),
        "idempotency_key": ("idempotency_key", "idempotencyKey", "dedupe_key"),
    }

    def _resolve(self, canonical: str, payload: Dict[str, Any], field_map: Dict[str, str]):
        if canonical in field_map:
            mapped = _dig(payload, field_map[canonical])
            if mapped not in (None, ""):
                return mapped
        return _first(payload, *self._ALIASES.get(canonical, (canonical,)))

    def normalize(self, payload: Dict[str, Any], integration: dict) -> CommonEvent:
        if not isinstance(payload, dict):
            raise AdapterError("event payload must be a JSON object")

        field_map = integration.get("field_map") or {}

        event_type = self._resolve("event_type", payload, field_map) or "event"
        external_id = self._resolve("external_id", payload, field_map)
        if not external_id:
            # Last-resort: recursively locate a common identifier anywhere in the
            # payload (priority-ordered), so unusual provider nestings still work.
            for k in ("order_id", "cf_payment_id", "payment_id", "transaction_id",
                      "reference", "event_id", "id"):
                external_id = _deep_find_key(payload, k)
                if external_id not in (None, ""):
                    break
        if not external_id:
            # Non-sensitive diagnostic: report the payload's key NAMES only (never
            # values) so operators can see the actual structure and map the id field.
            top = sorted(payload.keys())
            nested = sorted(payload["data"].keys()) if isinstance(payload.get("data"), dict) else None
            hint = f"top-level keys={top}" + (f"; data.* keys={nested}" if nested else "")
            raise AdapterError(
                "event must include an identifier (external_id/id/event_id, a nested "
                "id like data.order.order_id, or a mapped field). Payload structure: " + hint
            )
        occurred_at = self._resolve("occurred_at", payload, field_map) or _now_iso()

        amount_raw = self._resolve("amount", payload, field_map)
        if amount_raw is None:
            # Last-resort: recursively locate a common amount field anywhere in
            # the payload so unusual provider nestings still capture the value.
            for k in ("amount", "order_amount", "transaction_amount", "payment_amount"):
                amount_raw = _deep_find_key(payload, k)
                if amount_raw not in (None, ""):
                    break
        amount = _to_minor_units(amount_raw)
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
