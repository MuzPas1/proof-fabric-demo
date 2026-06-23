"""Time-anchor service — attach & verify detached RFC-3161 / local time anchors.

DETACHED by design: anchoring reads the proof's existing ``fea_hash`` and writes
a ``time_anchor`` envelope onto the ``feas`` document WITHOUT touching the signed
payload, signature, or fea_id. Verification is additive to signature checks and,
when the signing key carries a ``not_after`` cutoff, enforces it against the
INDEPENDENTLY attested time (closing the leaked-but-retired backdating gap).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from core.config import settings
from core.time_anchor import get_time_anchor_provider, provider_for_anchor, ENVELOPE_VERSION, _now_iso


def _fea_hash_of(fea_doc: Dict) -> Optional[str]:
    payload = fea_doc.get("fea_payload") or {}
    return payload.get("fea_hash")


async def anchor_fea(db, fea_id: str, tenant_id: Optional[str] = None) -> Dict:
    """Produce and persist a detached time anchor for an existing proof.

    Idempotent: returns the existing envelope if already anchored.
    """
    if not settings.ENABLE_TIME_ANCHOR:
        raise PermissionError("Time attestation is not enabled")

    query = {"fea_id": fea_id}
    if tenant_id is not None:
        query["tenant_id"] = tenant_id
    fea_doc = await db.feas.find_one(query, {"_id": 0})
    if not fea_doc:
        raise LookupError(f"Proof not found: {fea_id}")

    if fea_doc.get("time_anchor"):
        return fea_doc["time_anchor"]

    digest = _fea_hash_of(fea_doc)
    if not digest:
        raise ValueError("Proof has no fea_hash to anchor")

    provider = get_time_anchor_provider()
    anchor = provider.anchor(digest)
    envelope = {
        "envelope_version": ENVELOPE_VERSION,
        "anchored_at": _now_iso(),
        "anchors": [anchor],
    }
    await db.feas.update_one({"fea_id": fea_id}, {"$set": {"time_anchor": envelope}})
    return envelope


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


async def verify_time_attestation(fea_doc: Dict) -> Optional[Dict]:
    """Additive verification of any time anchor on the proof.

    Returns None when no anchor is present (backward-compatible: callers simply
    omit time attestation). Never raises into the signature path.
    """
    envelope = fea_doc.get("time_anchor")
    if not envelope:
        return None

    digest = _fea_hash_of(fea_doc)
    results = []
    attested_times = []
    any_valid = False
    for anchor in envelope.get("anchors", []):
        try:
            res = provider_for_anchor(anchor).verify(anchor, digest)
        except Exception as e:  # noqa: BLE001
            res = {"valid": False, "error": f"provider error: {e}",
                   "gen_time": anchor.get("gen_time"), "tsa": anchor.get("tsa_name"),
                   "chain_verified": False}
        res["type"] = anchor.get("type")
        results.append(res)
        if res.get("valid"):
            any_valid = True
            gt = _parse_iso(res.get("gen_time"))
            if gt:
                attested_times.append(gt)

    attested_time = min(attested_times).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if attested_times else None

    # Key retirement cutoff enforcement against the INDEPENDENT attested time.
    key_cutoff_ok = True
    cutoff_reason = None
    if any_valid and attested_times:
        try:
            from services.key_service import get_key_by_id
            key_info = await get_key_by_id((fea_doc.get("fea_payload") or {}).get("public_key_id"))
            cutoff = getattr(key_info, "time_anchor_cutoff", None) if key_info else None
            if cutoff:
                na = _parse_iso(cutoff)
                if na and min(attested_times) > na:
                    key_cutoff_ok = False
                    cutoff_reason = (
                        f"signing key was retired effective {cutoff}; attested issuance "
                        f"time {attested_time} is AFTER the cutoff (possible backdated forgery)"
                    )
        except Exception:
            pass

    independent = any(r.get("valid") and (r.get("type") == "rfc3161") for r in results)
    if any_valid and key_cutoff_ok:
        tier = "signed+timestamped(independent)" if independent else "signed+timestamped(local)"
    else:
        tier = "signed"  # anchor present but not trustworthy -> no time-trust uplift

    return {
        "present": True,
        "valid": any_valid and key_cutoff_ok,
        "tier": tier,
        "attested_time": attested_time,
        "independent": independent,
        "key_cutoff_ok": key_cutoff_ok,
        "cutoff_reason": cutoff_reason,
        "anchors": results,
    }
