"""Generic adapter — recursive deep-search identifier fallback.

Ensures unusual/deeply-nested provider payloads still resolve an identifier
(priority-ordered) after field_map + dotted aliases, and that the missing-id
error surfaces the payload structure (key names only).
"""
import pytest

from core.ingestion.adapters import GenericEventAdapter, AdapterError

ADAPTER = GenericEventAdapter()


def test_deeply_nested_order_id_resolves():
    payload = {"type": "PAYMENT_SUCCESS_WEBHOOK",
               "data": {"wrapper": {"order": {"order_id": "deep_ORDER_1"}}}}
    ev = ADAPTER.normalize(payload, {"slug": "cashfree"})
    assert ev.external_id == "deep_ORDER_1"


def test_priority_prefers_order_id_over_payment_id():
    payload = {"type": "x", "data": {"payment": {"cf_payment_id": 999}, "order": {"order_id": "ORD"}}}
    ev = ADAPTER.normalize(payload, {"slug": "cashfree"})
    assert ev.external_id == "ORD"


def test_missing_identifier_reports_structure():
    with pytest.raises(AdapterError) as ei:
        ADAPTER.normalize({"type": "PING", "data": {"meta": {}}}, {"slug": "x"})
    msg = str(ei.value)
    assert "Payload structure" in msg
    assert "top-level keys=" in msg and "data.* keys=" in msg
