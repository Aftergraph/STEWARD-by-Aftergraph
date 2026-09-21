"""Fail-closed reference builder for STEWARD presence projections.

Presentation is deliberately downstream of canonical owners. This module has no
authority, execution, or verification side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PRESENCE_STATES = {
    "idle", "thinking", "planning", "executing", "inspecting", "waiting",
    "blocked", "approval", "verifying", "approving", "succeeded", "failed",
}
SOURCE_OWNERS = {"steward", "aie", "trust-gateway", "works-execution", "runtime", "sentinel"}
SOURCE_KINDS = {"projection-local", "authority-state", "policy-state", "work-state", "runtime-state", "verification-verdict"}

class PresenceProjectionError(ValueError):
    """Raised when a visible state would overclaim its canonical source."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_presence_projection(*, projection_id: str, subject_kind: str, subject_id: str,
                              displayed_state: str, source_owner: str, source_kind: str,
                              source_id: str, generated_at: str | None = None,
                              exact_subject_sha: str | None = None, evidence_ref: str | None = None,
                              verification_verdict_id: str | None = None, observed_at: str | None = None,
                              stale_after: str | None = None, reduced_motion_state: str | None = None) -> dict[str, Any]:
    if not projection_id or not subject_id or not source_id:
        raise PresenceProjectionError("projection_id, subject_id and source_id are required")
    if displayed_state not in PRESENCE_STATES:
        raise PresenceProjectionError(f"unsupported displayed_state: {displayed_state}")
    if source_owner not in SOURCE_OWNERS:
        raise PresenceProjectionError(f"unsupported source_owner: {source_owner}")
    if source_kind not in SOURCE_KINDS:
        raise PresenceProjectionError(f"unsupported source_kind: {source_kind}")

    if displayed_state == "succeeded":
        if source_owner != "sentinel" or source_kind != "verification-verdict":
            raise PresenceProjectionError("succeeded requires a Sentinel verification-verdict source")
        if not verification_verdict_id:
            raise PresenceProjectionError("succeeded requires verification_verdict_id")

    if displayed_state == "verifying":
        if source_owner != "sentinel" or source_kind != "verification-verdict":
            raise PresenceProjectionError("verifying requires a Sentinel verification-verdict source")

    subject: dict[str, Any] = {"kind": subject_kind, "id": subject_id}
    if exact_subject_sha:
        subject["exact_subject_sha"] = exact_subject_sha

    semantic_source: dict[str, Any] = {"owner": source_owner, "kind": source_kind, "source_id": source_id}
    for key, value in (
        ("evidence_ref", evidence_ref),
        ("verification_verdict_id", verification_verdict_id),
        ("observed_at", observed_at),
    ):
        if value is not None:
            semantic_source[key] = value

    projection: dict[str, Any] = {
        "schema_version": "steward.presence-projection/1.0",
        "projection_id": projection_id,
        "subject": subject,
        "displayed_state": displayed_state,
        "semantic_source": semantic_source,
        "claim_class": "projection-only",
        "canonical_truth": False,
        "authority_effect": False,
        "verification_effect": False,
        "generated_at": generated_at or _utc_now(),
    }
    if stale_after is not None:
        projection["stale_after"] = stale_after
    if reduced_motion_state is not None:
        projection["reduced_motion_state"] = reduced_motion_state
    return projection
