"""Fail-closed P2 evidence gate before canonical WORKS Golden Mission acceptance.

STEWARD does not own durable MissionAcceptance. This module only proves that
the independently produced Runtime/WORKS execution evidence and the
post-effect Git/Sentinel evidence refer to one exact causal execution and one
current verification subject. A positive projection is therefore
ready_for_owner_acceptance -- never an acceptance record by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_ID_PATTERNS = {
    "work_id": re.compile(r"^wrk_[a-f0-9]{32}$"),
    "execution_context_id": re.compile(r"^ctx_[a-f0-9]{32}$"),
    "action_id": re.compile(r"^act_[a-f0-9]{32}$"),
    "authority_lease_id": re.compile(r"^auth_[a-f0-9]{32}$"),
    "execution_pdr_id": re.compile(r"^pdr_[a-f0-9]{32}$"),
}
_SHA40 = re.compile(r"^[a-f0-9]{40}$")
_RECEIPT64 = re.compile(r"^[a-f0-9]{64}$")


class P2AcceptanceEvidenceError(RuntimeError):
    """Evidence packets cannot safely feed canonical owner acceptance."""


@dataclass(frozen=True)
class P2ExecutionEvidence:
    work_id: str
    works_execution_id: str
    execution_context_id: str
    action_id: str
    authority_lease_id: str
    execution_pdr_id: str


@dataclass(frozen=True)
class P2EffectVerificationEvidence:
    work_id: str
    works_execution_id: str
    execution_context_id: str
    action_id: str
    authority_lease_id: str
    execution_pdr_id: str
    repository: str
    observed_sha: str
    bound_subject: str
    sentinel_head_sha: str
    sentinel_verdict: str
    sentinel_receipt_id: str
    remote_readback: bool
    credential_surrogation: bool
    action_time_revalidation: bool
    revocation_fail_closed: bool


@dataclass(frozen=True)
class P2OwnerAcceptanceReadiness:
    verification_subject: str
    sentinel_receipt_id: str
    ready_for_owner_acceptance: bool


def _validate_id(name: str, value: str) -> None:
    rx = _ID_PATTERNS[name]
    if not rx.fullmatch(value):
        raise P2AcceptanceEvidenceError(f"invalid {name}")


def _validate_execution(e: P2ExecutionEvidence) -> None:
    _validate_id("work_id", e.work_id)
    _validate_id("execution_context_id", e.execution_context_id)
    _validate_id("action_id", e.action_id)
    _validate_id("authority_lease_id", e.authority_lease_id)
    _validate_id("execution_pdr_id", e.execution_pdr_id)
    if not e.works_execution_id or len(e.works_execution_id) > 256:
        raise P2AcceptanceEvidenceError("invalid works_execution_id")


def project_owner_acceptance_readiness(
    execution: P2ExecutionEvidence,
    effect: P2EffectVerificationEvidence,
) -> P2OwnerAcceptanceReadiness:
    """Validate same-causal current-subject evidence for the WORKS owner gate."""

    _validate_execution(execution)
    _validate_id("work_id", effect.work_id)
    _validate_id("execution_context_id", effect.execution_context_id)
    _validate_id("action_id", effect.action_id)
    _validate_id("authority_lease_id", effect.authority_lease_id)
    _validate_id("execution_pdr_id", effect.execution_pdr_id)

    causal_fields = (
        "work_id",
        "works_execution_id",
        "execution_context_id",
        "action_id",
        "authority_lease_id",
        "execution_pdr_id",
    )
    for field in causal_fields:
        if getattr(execution, field) != getattr(effect, field):
            raise P2AcceptanceEvidenceError(f"causal mismatch: {field}")

    if not effect.repository or "/" not in effect.repository:
        raise P2AcceptanceEvidenceError("invalid repository")
    if not _SHA40.fullmatch(effect.observed_sha):
        raise P2AcceptanceEvidenceError("invalid observed_sha")
    if effect.sentinel_head_sha != effect.observed_sha:
        raise P2AcceptanceEvidenceError("Sentinel verified a different Git subject")

    exact_subject = f"git:{effect.repository}@{effect.observed_sha}"
    if effect.bound_subject != exact_subject:
        raise P2AcceptanceEvidenceError(
            "WORKS subject binding is not the observed exact subject"
        )

    if effect.sentinel_verdict != "SHIP":
        raise P2AcceptanceEvidenceError("current exact subject is not SHIP")
    if not _RECEIPT64.fullmatch(effect.sentinel_receipt_id):
        raise P2AcceptanceEvidenceError("invalid Sentinel receipt")

    required_truths = {
        "remote_readback": effect.remote_readback,
        "credential_surrogation": effect.credential_surrogation,
        "action_time_revalidation": effect.action_time_revalidation,
        "revocation_fail_closed": effect.revocation_fail_closed,
    }
    missing = [name for name, value in required_truths.items() if value is not True]
    if missing:
        raise P2AcceptanceEvidenceError(
            "required live evidence absent: " + ",".join(sorted(missing))
        )

    return P2OwnerAcceptanceReadiness(
        verification_subject=exact_subject,
        sentinel_receipt_id=effect.sentinel_receipt_id,
        ready_for_owner_acceptance=True,
    )
