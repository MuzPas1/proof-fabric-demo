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
        actor_ref = user.get("accountId") or user.get("name") or user.get("displayName")
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
        if actor_ref:
            attributes["actor_hash"] = _hash(actor_ref)
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


_ADAPTERS: Dict[str, EventAdapter] = {
    "generic": GenericEventAdapter(),
    "jira": JiraEventAdapter(),
}


def get_adapter(name: str) -> EventAdapter:
    adapter = _ADAPTERS.get((name or "generic").lower())
    if adapter is None:
        raise AdapterError(f"unknown adapter: {name}")
    return adapter


def register_adapter(adapter: EventAdapter) -> None:
    """Extension hook: register a new adapter (lightweight integration path)."""
    _ADAPTERS[adapter.name] = adapter
