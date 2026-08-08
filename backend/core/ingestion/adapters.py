"""Modular event adapters — normalize provider-specific payloads to CommonEvent.

An adapter's single job is to turn an external system's raw JSON into the
vendor-neutral ``CommonEvent`` shape. New integrations plug in by registering a
new adapter here; the core platform and proof engine are never touched.

The ``generic`` adapter is field-mapping driven, so many integrations need no
new code at all — only an ``field_map`` on the integration configuration.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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
            # DocuSign Connect envelope identifiers
            "envelopeId", "data.envelopeId", "envelope_id", "data.envelope_id",
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


def _hash(value) -> str:
    """One-way commitment for sensitive values (emails, names, comment/attachment content)."""
    raw = value if value not in (None, "") else "n/a"
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _epoch_ms_to_iso(ms) -> Optional[str]:
    try:
        ts = float(ms)
    except (TypeError, ValueError):
        return None
    if ts > 1e12:      # epoch milliseconds
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except (OverflowError, OSError, ValueError):
        return None


class JiraEventAdapter(EventAdapter):
    """Normalize Jira Cloud webhook events into the vendor-neutral CommonEvent.

    Reference adapter for enterprise workflow / issue-tracking platforms. Only
    non-sensitive workflow metadata (project, issue key, type, summary, status,
    priority, labels, team, due date, timestamps, workflow transition) is
    surfaced for display and cryptographically committed. Personal / sensitive
    data (user emails, display names, comment bodies, attachment contents) is
    reduced to one-way hashes so it never enters the descriptor or signed
    payload in the clear. The Proof Engine is untouched.
    """
    name = "jira"

    @staticmethod
    def _changelog_fields(changelog) -> set:
        fields = set()
        if isinstance(changelog, dict):
            for item in changelog.get("items") or []:
                if isinstance(item, dict):
                    f = (item.get("field") or item.get("fieldId") or "").lower()
                    if f:
                        fields.add(f)
        return fields

    def _map_event_type(self, webhook_event, issue_event_type, changelog) -> str:
        we = (webhook_event or "").lower()
        iet = (issue_event_type or "").lower()
        if "comment" in we or iet in ("issue_commented", "issue_comment_edited"):
            if "delet" in we:
                return "comment_deleted"
            if "updat" in we or "edit" in iet:
                return "comment_updated"
            return "comment_added"
        if "attachment" in we:
            return "attachment_added"
        if "worklog" in we:
            return "worklog_updated"
        if we == "jira:issue_created" or iet == "issue_created":
            return "issue_created"
        if we == "jira:issue_deleted":
            return "issue_deleted"
        fields = self._changelog_fields(changelog)
        if iet == "issue_assigned" or "assignee" in fields:
            return "assignee_changed"
        if iet in ("issue_resolved", "issue_closed") or "resolution" in fields:
            return "issue_resolved"
        if "attachment" in fields:
            return "attachment_added"
        if "status" in fields:
            return "status_changed"
        if we == "jira:issue_updated" or "updat" in we:
            return "issue_updated"
        return (we.replace("jira:", "").replace(":", "_") or "issue_event")[:64]

    @staticmethod
    def _status_transition(changelog):
        if isinstance(changelog, dict):
            for item in changelog.get("items") or []:
                if isinstance(item, dict) and (item.get("field") or "").lower() == "status":
                    return (item.get("fromString") or item.get("from"),
                            item.get("toString") or item.get("to"))
        return None

    @staticmethod
    def _attachment_refs(changelog):
        refs = []
        if isinstance(changelog, dict):
            for item in changelog.get("items") or []:
                if isinstance(item, dict) and (item.get("field") or "").lower() == "attachment":
                    refs.append(str(item.get("toString") or item.get("to") or "attachment"))
        return refs

    @staticmethod
    def _extract_team(fields: Dict[str, Any], integration: dict) -> Optional[str]:
        cfg = integration.get("auth_config") or {}
        candidates = [cfg.get("team_field"), "team", "customfield_10001"]
        for key in candidates:
            if not key:
                continue
            v = fields.get(key)
            if isinstance(v, dict):
                name = v.get("name") or v.get("value") or v.get("title")
                if name:
                    return str(name)
            elif isinstance(v, str) and v.strip():
                return v
        return None

    def normalize(self, payload: Dict[str, Any], integration: dict) -> CommonEvent:
        if not isinstance(payload, dict):
            raise AdapterError("Jira event payload must be a JSON object")

        issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
        fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
        webhook_event = payload.get("webhookEvent") or payload.get("webhook_event")
        issue_event_type = payload.get("issue_event_type_name")
        changelog = payload.get("changelog")
        comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else {}

        issue_key = issue.get("key") or _deep_find_key(payload, "key")
        if not issue_key:
            top = sorted(payload.keys())
            raise AdapterError(
                "Jira event must include issue.key (an issue-scoped webhook payload). "
                f"Top-level keys={top}"
            )

        event_type = self._map_event_type(webhook_event, issue_event_type, changelog)
        occurred_at = _epoch_ms_to_iso(payload.get("timestamp")) or fields.get("updated") or _now_iso()

        project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
        issuetype = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
        status_obj = fields.get("status") if isinstance(fields.get("status"), dict) else {}
        priority_obj = fields.get("priority") if isinstance(fields.get("priority"), dict) else {}
        labels = fields.get("labels") if isinstance(fields.get("labels"), list) else []

        project_key = project.get("key")
        project_name = project.get("name")
        project_label = (f"{project_name} ({project_key})" if project_name and project_key
                         else (project_name or project_key))
        status_name = status_obj.get("name")
        priority_name = priority_obj.get("name")
        issue_type_name = issuetype.get("name")
        summary = fields.get("summary")
        labels_str = ", ".join(str(l) for l in labels) if labels else None
        team = self._extract_team(fields, integration)
        due_date = fields.get("duedate")
        created = fields.get("created")
        updated = fields.get("updated")
        transition = self._status_transition(changelog)

        event_id = (str(changelog.get("id")) if isinstance(changelog, dict) and changelog.get("id") else None) \
            or (str(comment.get("id")) if comment.get("id") else None) \
            or f"{issue_key}-{payload.get('timestamp') or occurred_at}"

        user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        # Privacy: use only stable, non-PII identifiers for the actor. A raw
        # display name (PII) is never assigned here; it is committed hash-only
        # via ``actor_hash`` below in every code path.
        actor_ref = user.get("accountId") or user.get("name")
        actor_hash_ref = actor_ref or user.get("displayName") or user.get("emailAddress")
        assignee = fields.get("assignee") if isinstance(fields.get("assignee"), dict) else {}
        assignee_ref = assignee.get("accountId") or assignee.get("displayName")

        # Signed metadata (committed via metadata_hash). Non-sensitive values in
        # the clear + one-way hashes for everything sensitive.
        attributes: Dict[str, Any] = {
            "provider": "Jira",
            "provider_category": "Issue Tracking",
            "event_source": "Webhook",
            "event_id": event_id,
            "webhook_event": webhook_event,
            "issue_event_type": issue_event_type,
            "project_key": project_key,
            "project_name": project_name,
            "issue_key": issue_key,
            "issue_type": issue_type_name,
            "summary": summary,
            "status": status_name,
            "priority": priority_name,
            "labels": labels_str,
            "team": team,
            "due_date": due_date,
            "created_at": created,
            "updated_at": updated,
            "event_timestamp": occurred_at,
        }
        if transition:
            attributes["status_from"], attributes["status_to"] = transition
        if actor_hash_ref:
            attributes["actor_hash"] = _hash(actor_hash_ref)
        if assignee_ref:
            attributes["assignee_hash"] = _hash(assignee_ref)
        if comment.get("body"):
            attributes["comment_hash"] = _hash(comment.get("body"))
        att_refs = self._attachment_refs(changelog)
        if att_refs:
            attributes["attachment_hash"] = _hash("|".join(att_refs))
        attributes = {k: v for k, v in attributes.items() if v not in (None, "")}

        # Display attributes (Provider Summary; non-sensitive, never PII).
        display = {
            "Project": project_label,
            "Issue Key": issue_key,
            "Issue Type": issue_type_name,
            "Summary": summary,
            "Priority": priority_name,
            "Labels": labels_str,
            "Team": team,
            "Due Date": due_date,
        }
        if transition:
            display["Status Change"] = f"{transition[0]} → {transition[1]}"
        display = {k: str(v)[:256] for k, v in display.items() if v not in (None, "")}

        return CommonEvent(
            event_type=event_type,
            external_id=str(issue_key)[:256],
            occurred_at=str(occurred_at),
            source=integration.get("slug"),
            actor=(str(actor_ref)[:256] if actor_ref else None),
            subject=str(issue_key)[:256],
            amount=0,
            currency=(integration.get("default_currency") or "USD"),
            attributes=attributes,
            idempotency_key=f"{issue_key}:{event_type}:{event_id}"[:256],
            provider="Jira",
            provider_category="Issue Tracking",
            event_source="Webhook",
            status=(str(status_name)[:64] if status_name else None),
            display_attributes=display,
        )


class TarabutEventAdapter(EventAdapter):
    """Normalize Tarabut Gateway (Open Banking) events into the vendor-neutral
    CommonEvent. Reference adapter for Open Banking / account-information +
    payment-initiation platforms.

    Handles three input shapes:
      1. **Service envelope** — emitted by ``services.tarabut_service`` for
         outbound OAuth2 API events. Carries ``tarabutEventType``/``externalId``/
         ``occurredAt`` plus display-safe ``attributes`` and a ``sensitive`` map
         that is committed hash-only.
      2. **Payment status webhook** — Tarabut's signed payment notification
         (``paymentId``/``status``/``amount``/``payerToken``…).
      3. **Consent / account / transaction objects** — raw Open Banking resources
         detected by their identifiers.

    Privacy: personal / account-identifying data (IBAN, masked PAN, account
    holder name, payer token, customer id, email, names, destination account) is
    reduced to one-way hashes so it never enters the descriptor or the signed
    payload in the clear. Only non-personal workflow metadata (event type,
    status, provider/bank, amount, currency, reference ids, timestamps) is
    surfaced for display. The Proof Engine is untouched.
    """

    name = "tarabut"

    # Keys whose VALUES are personal / account-identifying and must be hashed.
    _SENSITIVE_KEYS = (
        "payerToken", "destinationAccount", "iban", "IBAN", "pan", "maskedPAN",
        "accountNumber", "accountId", "accountHolderName", "email", "firstName",
        "lastName", "customerUserId", "userIdentifier",
    )

    _STATUS_EVENT = {
        "ACTIVE": "consent_granted",
        "REVOKED": "consent_revoked",
        "EXPIRED": "consent_expired",
    }

    def _region(self, integration: dict) -> str:
        return ((integration.get("auth_config") or {}).get("tarabut_region") or "bahrain")

    def _currency(self, payload: dict, integration: dict) -> str:
        cur = payload.get("currency") or (payload.get("amount") or {}).get("currency") \
            if isinstance(payload.get("amount"), dict) else payload.get("currency")
        return str(cur or integration.get("default_currency") or "BHD")[:3]

    def normalize(self, payload: Dict[str, Any], integration: dict) -> CommonEvent:
        if not isinstance(payload, dict):
            raise AdapterError("Tarabut event payload must be a JSON object")

        if payload.get("tarabutEventType") or payload.get("tarabut_event_type"):
            return self._from_envelope(payload, integration)
        if payload.get("paymentId") or str(payload.get("type") or "").upper() == "PAYMENT_STATUS_CHANGE":
            return self._from_payment(payload, integration)
        if payload.get("consentId") or (payload.get("id") and payload.get("providerId") and payload.get("status")):
            return self._from_consent(payload, integration)
        return self._from_generic_resource(payload, integration)

    # -- shape 1: outbound service envelope ---------------------------------
    def _from_envelope(self, payload: dict, integration: dict) -> CommonEvent:
        event_type = str(payload.get("tarabutEventType") or payload.get("tarabut_event_type") or "tarabut_event")[:128]
        external_id = payload.get("externalId") or payload.get("external_id")
        if not external_id:
            raise AdapterError("Tarabut envelope must include externalId")
        occurred_at = payload.get("occurredAt") or payload.get("occurred_at") or _now_iso()
        status = payload.get("status")
        amount = _to_minor_units(payload.get("amount"))
        currency = str(payload.get("currency") or integration.get("default_currency") or "BHD")[:3]
        event_source = str(payload.get("eventSource") or "API")[:32]

        display = {str(k)[:64]: str(v)[:256] for k, v in (payload.get("attributes") or {}).items() if v not in (None, "")}
        attributes: Dict[str, Any] = {
            "provider": "Tarabut", "provider_category": "Open Banking",
            "event_source": event_source, "event_type": event_type,
            "provider_id": payload.get("providerId"), "status": status,
        }
        attributes.update(display)
        for k, v in (payload.get("sensitive") or {}).items():
            if v not in (None, ""):
                attributes[f"{k}_hash"] = _hash(v)
        attributes = {k: v for k, v in attributes.items() if v not in (None, "")}

        return CommonEvent(
            event_type=event_type, external_id=str(external_id)[:256], occurred_at=str(occurred_at),
            source=integration.get("slug"),
            actor=(str(payload.get("providerId"))[:256] if payload.get("providerId") else None),
            subject=str(external_id)[:256], amount=amount, currency=currency,
            attributes=attributes,
            idempotency_key=f"{event_type}:{external_id}:{occurred_at}"[:256],
            provider="Tarabut", provider_category="Open Banking", event_source=event_source,
            status=(str(status)[:64] if status else None), display_attributes=display,
        )

    # -- shape 2: payment status webhook ------------------------------------
    def _from_payment(self, payload: dict, integration: dict) -> CommonEvent:
        payment_id = payload.get("paymentId") or payload.get("id")
        if not payment_id:
            raise AdapterError("Tarabut payment event must include paymentId")
        status = payload.get("status")
        event_type = (f"payment_{str(status).lower()}" if status else "payment_status_change")[:128]
        amt_raw = payload.get("amount")
        if isinstance(amt_raw, dict):
            amt_raw = amt_raw.get("value")
        amount = _to_minor_units(amt_raw)
        currency = str(payload.get("currency") or integration.get("default_currency") or "BHD")[:3]
        occurred_at = (_epoch_ms_to_iso(payload.get("timestamp"))
                       or payload.get("creationTimestamp") or _now_iso())

        display = {
            "Payment ID": payment_id, "Status": status,
            "Amount": (f"{amt_raw} {currency}" if amt_raw not in (None, "") else None),
            "Bank": payload.get("bankName") or payload.get("bank"),
            "Merchant Reference": payload.get("merchantReference"),
            "Customer Reference": payload.get("customerReference"),
        }
        if payload.get("merchant"):
            display["Merchant"] = payload.get("merchant")
        display = {k: str(v)[:256] for k, v in display.items() if v not in (None, "")}

        attributes: Dict[str, Any] = {
            "provider": "Tarabut", "provider_category": "Open Banking",
            "event_source": "Webhook", "event_type": event_type, "status": status,
            "bank": payload.get("bankName") or payload.get("bank"),
            "merchant_reference": payload.get("merchantReference"),
            "customer_reference": payload.get("customerReference"),
            "event_timestamp": occurred_at,
        }
        for k in ("payerToken", "destinationAccount"):
            if payload.get(k):
                attributes[f"{k}_hash"] = _hash(payload.get(k))
        attributes = {k: v for k, v in attributes.items() if v not in (None, "")}

        return CommonEvent(
            event_type=event_type, external_id=str(payment_id)[:256], occurred_at=str(occurred_at),
            source=integration.get("slug"),
            actor=(str(payload.get("merchant"))[:256] if payload.get("merchant") else None),
            subject=str(payment_id)[:256], amount=amount, currency=currency,
            attributes=attributes,
            idempotency_key=f"payment:{payment_id}:{status or occurred_at}"[:256],
            provider="Tarabut", provider_category="Open Banking", event_source="Webhook",
            status=(str(status)[:64] if status else None), display_attributes=display,
        )

    # -- shape 3a: consent object -------------------------------------------
    def _from_consent(self, payload: dict, integration: dict) -> CommonEvent:
        consent_id = payload.get("consentId") or payload.get("id")
        status = str(payload.get("status") or "").upper()
        event_type = self._STATUS_EVENT.get(status, "consent_updated")
        provider_id = payload.get("providerId")
        occurred_at = (payload.get("revokeDate") or payload.get("startDate")
                       or payload.get("expiryDate") or _now_iso())
        connected = payload.get("connectedAccounts") or []
        display = {
            "Consent ID": consent_id, "Status": payload.get("status"),
            "Provider": provider_id, "Start Date": payload.get("startDate"),
            "Expiry Date": payload.get("expiryDate"),
        }
        if connected:
            display["Connected Accounts"] = str(len(connected))
        display = {k: str(v)[:256] for k, v in display.items() if v not in (None, "")}

        attributes: Dict[str, Any] = {
            "provider": "Tarabut", "provider_category": "Open Banking",
            "event_source": "API", "event_type": event_type, "status": payload.get("status"),
            "provider_id": provider_id, "start_date": payload.get("startDate"),
            "expiry_date": payload.get("expiryDate"),
        }
        # Hash every connected-account identifier so no IBAN/PAN is stored clear.
        acct_ids = _deep_collect_ids(connected)
        if acct_ids:
            attributes["accounts_hash"] = _hash("|".join(acct_ids))
        attributes = {k: v for k, v in attributes.items() if v not in (None, "")}

        return CommonEvent(
            event_type=event_type, external_id=str(consent_id)[:256], occurred_at=str(occurred_at),
            source=integration.get("slug"),
            actor=(str(provider_id)[:256] if provider_id else None),
            subject=str(consent_id)[:256], amount=0,
            currency=str(integration.get("default_currency") or "BHD")[:3],
            attributes=attributes,
            idempotency_key=f"consent:{consent_id}:{status or occurred_at}"[:256],
            provider="Tarabut", provider_category="Open Banking", event_source="API",
            status=(str(payload.get("status"))[:64] if payload.get("status") else None),
            display_attributes=display,
        )

    # -- shape 3b: generic Open Banking resource (intent/account/transaction) --
    def _from_generic_resource(self, payload: dict, integration: dict) -> CommonEvent:
        mapping = [
            ("intentId", "intent_created", "Intent ID"),
            ("transactionId", "transaction_retrieved", "Transaction ID"),
            ("accountId", "account_retrieved", "Account ID"),
        ]
        external_id = None
        event_type = "tarabut_event"
        id_label = "Reference"
        for key, et, label in mapping:
            v = payload.get(key) or _deep_find_key(payload, key)
            if v not in (None, ""):
                external_id, event_type, id_label = v, et, label
                break
        if not external_id:
            top = sorted(payload.keys())
            raise AdapterError(
                "Tarabut event must include a recognizable identifier "
                "(tarabutEventType, paymentId, consent id, intentId, accountId or transactionId). "
                f"Top-level keys={top}"
            )
        occurred_at = (payload.get("occurredAt") or payload.get("expiry")
                       or payload.get("bookingDateTime") or _now_iso())
        provider_id = payload.get("providerId")
        display = {id_label: external_id, "Provider": provider_id, "Status": payload.get("status")}
        display = {k: str(v)[:256] for k, v in display.items() if v not in (None, "")}
        attributes: Dict[str, Any] = {
            "provider": "Tarabut", "provider_category": "Open Banking",
            "event_source": "API", "event_type": event_type,
            "provider_id": provider_id, "status": payload.get("status"),
        }
        ids = _deep_collect_ids(payload)
        if ids:
            attributes["identifiers_hash"] = _hash("|".join(ids))
        attributes = {k: v for k, v in attributes.items() if v not in (None, "")}
        return CommonEvent(
            event_type=str(event_type)[:128], external_id=str(external_id)[:256],
            occurred_at=str(occurred_at), source=integration.get("slug"),
            actor=(str(provider_id)[:256] if provider_id else None),
            subject=str(external_id)[:256], amount=0,
            currency=str(integration.get("default_currency") or "BHD")[:3],
            attributes=attributes,
            idempotency_key=f"{event_type}:{external_id}:{occurred_at}"[:256],
            provider="Tarabut", provider_category="Open Banking", event_source="API",
            status=(str(payload.get("status"))[:64] if payload.get("status") else None),
            display_attributes=display,
        )


def _deep_collect_ids(obj: Any, depth: int = 0) -> list:
    """Collect account-identifying values (IBAN/PAN/account ids) from a nested
    Open Banking structure so they can be committed hash-only (never in clear)."""
    out: list = []
    if depth > 6:
        return out
    if isinstance(obj, dict):
        if obj.get("type") in ("IBAN", "maskedPAN", "PAN") and obj.get("value"):
            out.append(f"{obj.get('type')}:{obj.get('value')}")
        for k, v in obj.items():
            if k in ("id", "accountId") and isinstance(v, str):
                out.append(str(v))
            else:
                out.extend(_deep_collect_ids(v, depth + 1))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_deep_collect_ids(v, depth + 1))
    return [x for x in dict.fromkeys(out) if x]


_ADAPTERS: Dict[str, EventAdapter] = {
    "generic": GenericEventAdapter(),
    "jira": JiraEventAdapter(),
    "tarabut": TarabutEventAdapter(),
}


def get_adapter(name: str) -> EventAdapter:
    adapter = _ADAPTERS.get((name or "generic").lower())
    if adapter is None:
        raise AdapterError(f"unknown adapter: {name}")
    return adapter


def register_adapter(adapter: EventAdapter) -> None:
    """Extension hook: register a new adapter (lightweight integration path)."""
    _ADAPTERS[adapter.name] = adapter
