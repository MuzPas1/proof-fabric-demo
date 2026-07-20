"""Generic adapter — nested payload + dotted-path resolution (Cashfree, etc.).

Ensures the vendor-neutral generic adapter can extract an identifier from a
NESTED provider payload (Cashfree PG order/payment ids) without bespoke code,
and that dotted-path field_map overrides work. No core change.
"""
import pytest

from core.ingestion.adapters import GenericEventAdapter, AdapterError

ADAPTER = GenericEventAdapter()


def _cashfree_payload():
    return {
        "data": {
            "order": {"order_id": "order_ABC123", "order_amount": 1.00, "order_currency": "INR"},
            "payment": {"cf_payment_id": 987654321, "payment_status": "SUCCESS",
                        "payment_time": "2026-07-20T10:00:00+05:30"},
            "customer_details": {"customer_id": "cust_9"},
        },
        "event_time": "2026-07-20T10:00:01+05:30",
        "type": "PAYMENT_SUCCESS_WEBHOOK",
    }


def test_cashfree_nested_identifier_resolves_order_id():
    ev = ADAPTER.normalize(_cashfree_payload(), {"slug": "cashfree", "default_currency": "INR"})
    assert ev.external_id == "order_ABC123"
    assert ev.event_type == "PAYMENT_SUCCESS_WEBHOOK"
    assert ev.occurred_at.startswith("2026-07-20T10:00:01")
    # whole nested payload preserved as attributes (metadata)
    assert "data" in ev.attributes


def test_cashfree_falls_back_to_cf_payment_id_when_no_order():
    payload = {"data": {"payment": {"cf_payment_id": 555}}, "type": "PAYMENT_USER_DROPPED_WEBHOOK"}
    ev = ADAPTER.normalize(payload, {"slug": "cashfree"})
    assert ev.external_id == "555"
    assert ev.event_type == "PAYMENT_USER_DROPPED_WEBHOOK"


def test_dotted_field_map_override():
    payload = {"data": {"txn": {"ref": "TXN-1"}}, "kind": "settlement"}
    integ = {"slug": "x", "field_map": {"external_id": "data.txn.ref", "event_type": "kind"}}
    ev = ADAPTER.normalize(payload, integ)
    assert ev.external_id == "TXN-1"
    assert ev.event_type == "settlement"


def test_missing_identifier_still_raises():
    with pytest.raises(AdapterError):
        ADAPTER.normalize({"type": "noop", "data": {"order": {}}}, {"slug": "x"})


def test_flat_payload_backward_compatible():
    ev = ADAPTER.normalize(
        {"type": "invoice.created", "id": "INV-1", "amount": 25000, "currency": "USD"},
        {"slug": "erp"},
    )
    assert ev.external_id == "INV-1"
    assert ev.amount == 25000
    assert ev.currency == "USD"
