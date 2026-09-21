"""Fail-closed resolution of delegated agent authority.

An agent persona is never authorized by its own selection. Authorization is
the positive outcome of a resolvable chain: a grant that exists, is active,
is not expired or revoked, attenuates the parent capability set, and — for
verification capabilities — is bound to an external Sentinel verifier.
Anything less resolves to DENY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VERIFY_CAPABILITIES = frozenset({"verify:exact-subject", "verify:projection"})


class DelegatedAuthorityError(ValueError):
    """Raised when a grant is structurally invalid."""


def _parse_instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_grant(grant: dict[str, Any]) -> None:
    """Structural validation beyond JSON Schema: temporal and binding sanity."""
    if not grant.get("grant_id") or not grant.get("grantee_persona_id"):
        raise DelegatedAuthorityError("grant_id and grantee_persona_id are required")
    granted_at = _parse_instant(grant["granted_at"])
    expires_at = _parse_instant(grant["expires_at"])
    if expires_at <= granted_at:
        raise DelegatedAuthorityError("expires_at must be after granted_at")
    revoked_at = grant.get("revoked_at")
    if revoked_at is not None and _parse_instant(revoked_at) <= granted_at:
        raise DelegatedAuthorityError("revoked_at must be after granted_at")
    if grant.get("verification_binding") is not None:
        if grant["verification_binding"].get("verifier_owner") != "sentinel":
            raise DelegatedAuthorityError("verification binding must point at Sentinel")


def is_attenuated(grant: dict[str, Any]) -> bool:
    """Child capability set must be a subset of the parent capability set."""
    return set(grant["capabilities"]) <= set(grant["parent_capabilities"])


def grant_state(grant: dict[str, Any], *, now: datetime | None = None) -> str:
    """Resolve grant state at an instant: 'active', 'revoked', or 'expired'."""
    validate_grant(grant)
    moment = now or _utc_now()
    if grant.get("revoked_at") is not None or grant.get("status") == "revoked":
        return "revoked"
    if moment >= _parse_instant(grant["expires_at"]) or grant.get("status") == "expired":
        return "expired"
    return "active"


def resolve_action(
    *,
    grant: dict[str, Any],
    requested_capability: str,
    requested_subject_sha: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Decide whether an agent may perform a capability on a subject.

    Returns a typed decision receipt. The decision is DENY unless every
    condition passes. DENY receipts carry a reason so refusals are auditable.
    """
    def deny(reason: str) -> dict[str, Any]:
        return {
            "decision": "DENY",
            "reason": reason,
            "capability": requested_capability,
            "grant_id": grant.get("grant_id", ""),
            "subject_sha": requested_subject_sha,
        }

    try:
        validate_grant(grant)
    except DelegatedAuthorityError as exc:
        return deny(f"invalid_grant: {exc}")

    if not is_attenuated(grant):
        return deny(
            f"escalation: capability set exceeds parent set "
            f"{sorted(set(grant['capabilities']) - set(grant['parent_capabilities']))}"
        )

    if requested_capability not in grant["capabilities"]:
        return deny(f"capability_not_granted: {requested_capability}")

    state = grant_state(grant, now=now)
    if state != "active":
        return deny(f"grant_{state}")

    if requested_capability in VERIFY_CAPABILITIES:
        binding = grant.get("verification_binding")
        if binding is None or binding.get("verifier_owner") != "sentinel":
            return deny("verification_requires_sentinel_binding")
        if requested_capability == "verify:exact-subject":
            if not requested_subject_sha:
                return deny("exact_subject_verification_requires_subject_sha")
            bound_sha = binding.get("subject_sha")
            if bound_sha is not None and bound_sha != requested_subject_sha:
                return deny(f"subject_mismatch: grant bound to {bound_sha}")

    return {
        "decision": "ALLOW",
        "capability": requested_capability,
        "grant_id": grant["grant_id"],
        "authority_source": grant["authority_source"]["owner"],
        "subject_sha": requested_subject_sha,
    }
