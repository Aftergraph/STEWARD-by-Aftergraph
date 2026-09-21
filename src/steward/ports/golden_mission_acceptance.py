"""Transport-neutral STEWARD port into WORKS Golden Mission acceptance.

WORKS remains the canonical Mission Acceptance owner.  STEWARD only composes
owner receipts into the JSON shape consumed by packages/goldenmission and
fails closed unless the acceptance transport echoes the exact action,
action-decision and verification subject it evaluated.

This module deliberately does not implement Mission acceptance semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol


_ID_PATTERNS = {
    "tenant_id": re.compile(r"^ten_[a-f0-9]{32}$"),
    "principal_id": re.compile(r"^prn_[a-f0-9]{32}$"),
    "authority_lease_id": re.compile(r"^auth_[a-f0-9]{32}$"),
    "execution_context_id": re.compile(r"^ctx_[a-f0-9]{32}$"),
    "work_id": re.compile(r"^wrk_[a-f0-9]{32}$"),
    "trace_id": re.compile(r"^trc_[a-f0-9]{32}$"),
    "action_id": re.compile(r"^act_[a-f0-9]{32}$"),
    "action_decision_id": re.compile(r"^pdr_[a-f0-9]{32}$"),
}
_SUBJECT_RE = re.compile(r"^git:[A-Za-z0-9._/-]+@[a-f0-9]{40}$")
_STAGE_ORDER = (
    "studio",
    "aie",
    "trust-gateway",
    "runtime",
    "works",
    "verification",
)


class GoldenMissionAcceptanceError(RuntimeError):
    """Base failure for the canonical WORKS Mission Acceptance port."""


class GoldenMissionAcceptanceUnavailable(GoldenMissionAcceptanceError):
    """The canonical WORKS Golden Mission acceptance transport is unavailable."""


class GoldenMissionAcceptanceContractError(GoldenMissionAcceptanceError):
    """Acceptance request/receipt violates the owner contract."""


@dataclass(frozen=True)
class GoldenMissionIdentity:
    tenant_id: str
    principal_id: str
    mission_id: str
    authority_lease_id: str
    execution_context_id: str
    work_id: str
    trace_id: str
    action_id: str
    action_decision_id: str

    def to_wire(self) -> dict[str, str]:
        values = {
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "authority_lease_id": self.authority_lease_id,
            "execution_context_id": self.execution_context_id,
            "work_id": self.work_id,
            "trace_id": self.trace_id,
            "action_id": self.action_id,
            "action_decision_id": self.action_decision_id,
        }
        for name, value in values.items():
            if not isinstance(value, str) or not _ID_PATTERNS[name].fullmatch(value):
                raise GoldenMissionAcceptanceContractError(
                    f"{name} has invalid canonical format"
                )
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise GoldenMissionAcceptanceContractError("mission_id is required")
        if len(self.mission_id) > 256:
            raise GoldenMissionAcceptanceContractError("mission_id exceeds owner limit")
        return {**values, "mission_id": self.mission_id}


@dataclass(frozen=True)
class GoldenMissionAcceptanceRequest:
    canonical: GoldenMissionIdentity
    verification_subject_ref: str
    verifier_principal: str
    verification_verdict: str
    stages: tuple[str, ...] = _STAGE_ORDER

    def to_wire(self) -> dict[str, Any]:
        canonical = self.canonical.to_wire()
        if not _SUBJECT_RE.fullmatch(self.verification_subject_ref):
            raise GoldenMissionAcceptanceContractError(
                "verification_subject_ref must be exact git:<repo>@<40hex>"
            )
        if not _ID_PATTERNS["principal_id"].fullmatch(self.verifier_principal):
            raise GoldenMissionAcceptanceContractError(
                "verifier_principal must be canonical prn_<32 hex>"
            )
        if self.verifier_principal == self.canonical.principal_id:
            raise GoldenMissionAcceptanceContractError(
                "verifier principal must be independent of mission principal"
            )
        if self.verification_verdict not in {"accept", "reject"}:
            raise GoldenMissionAcceptanceContractError(
                "verification_verdict must be accept or reject"
            )
        if tuple(self.stages) != _STAGE_ORDER:
            raise GoldenMissionAcceptanceContractError(
                "success acceptance requires exact studio..verification stage order"
            )

        # WORKS Golden Mission stage IDs are observed seam records.  STEWARD
        # carries the already-validated canonical identity through each seam;
        # WORKS remains responsible for deciding whether the chain accepts.
        stages = [{"name": name, "ids": dict(canonical)} for name in self.stages]
        return {
            "mission": {
                "branch": "success",
                "canonical": canonical,
                "stages": stages,
                "verification_subject_ref": self.verification_subject_ref,
            },
            "verification": {
                "verifier_principal": self.verifier_principal,
                "verdict": self.verification_verdict,
                "action_id": self.canonical.action_id,
                "action_decision_id": self.canonical.action_decision_id,
                "subject_ref": self.verification_subject_ref,
            },
        }


@dataclass(frozen=True)
class GoldenMissionAcceptanceReceipt:
    decision: str
    reason: str
    pin: str
    subject_ref: str
    action_id: str
    action_decision_id: str

    @property
    def accepted(self) -> bool:
        return self.decision == "accept"

    @classmethod
    def from_wire(
        cls,
        request: GoldenMissionAcceptanceRequest,
        payload: Mapping[str, Any],
    ) -> "GoldenMissionAcceptanceReceipt":
        decision = payload.get("decision")
        reason = payload.get("reason")
        pin = payload.get("pin")
        subject = payload.get("subject_ref")
        action_id = payload.get("action_id")
        action_decision_id = payload.get("action_decision_id")
        if decision not in {"accept", "reject"}:
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt has unsupported decision"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt missing reason"
            )
        if not isinstance(pin, str) or not pin.strip():
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt missing transcript pin"
            )
        if subject != request.verification_subject_ref:
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt rebound verification subject"
            )
        if action_id != request.canonical.action_id:
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt rebound action"
            )
        if action_decision_id != request.canonical.action_decision_id:
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance receipt rebound action decision"
            )
        return cls(
            decision=decision,
            reason=reason,
            pin=pin,
            subject_ref=subject,
            action_id=action_id,
            action_decision_id=action_decision_id,
        )


class GoldenMissionAcceptanceTransport(Protocol):
    def evaluate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class GoldenMissionAcceptancePort:
    """Fail-closed consumer of the canonical WORKS Golden Mission runner."""

    def __init__(
        self,
        transport: GoldenMissionAcceptanceTransport,
        *,
        verifier_principal: str,
    ) -> None:
        if not _ID_PATTERNS["principal_id"].fullmatch(verifier_principal):
            raise ValueError("verifier_principal must be canonical prn_<32 hex>")
        self._transport = transport
        self.verifier_principal = verifier_principal

    def evaluate(
        self,
        *,
        canonical: GoldenMissionIdentity,
        verification_subject_ref: str,
        sentinel_ship: bool,
    ) -> GoldenMissionAcceptanceReceipt:
        request = GoldenMissionAcceptanceRequest(
            canonical=canonical,
            verification_subject_ref=verification_subject_ref,
            verifier_principal=self.verifier_principal,
            verification_verdict="accept" if sentinel_ship else "reject",
        )
        payload = request.to_wire()
        try:
            receipt = self._transport.evaluate(payload)
        except GoldenMissionAcceptanceError:
            raise
        except Exception as exc:
            raise GoldenMissionAcceptanceUnavailable(
                "canonical WORKS Golden Mission transport failed"
            ) from exc
        if not isinstance(receipt, Mapping):
            raise GoldenMissionAcceptanceContractError(
                "WORKS acceptance transport returned non-object receipt"
            )
        return GoldenMissionAcceptanceReceipt.from_wire(request, receipt)
