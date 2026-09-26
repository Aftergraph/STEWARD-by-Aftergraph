"""Read-only MissionAcceptance projection over canonical WORKS evidence.

STEWARD composes owner receipts; it does not verify its own execution. A mission
is accepted only when WORKS projects an independently verified outcome with the
exact identity chain expected from Runtime and Trust Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class MissionAcceptanceContractError(RuntimeError):
    """WORKS projection cannot be bound to the composed mission identity."""


class WorksEvidenceReader(Protocol):
    def get_evidence(self, work_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class MissionAcceptanceRequest:
    mission_id: str
    work_id: str
    execution_context_id: str
    execution_policy_decision_id: str


@dataclass(frozen=True)
class MissionAcceptanceProjection:
    accepted: bool
    status: str
    outcome_status: str | None
    bundle_id: str | None


class MissionAcceptancePort:
    """Consume WORKS truth; never manufacture verification."""

    def __init__(self, works: WorksEvidenceReader) -> None:
        self._works = works

    def project(self, request: MissionAcceptanceRequest) -> MissionAcceptanceProjection:
        payload = self._works.get_evidence(request.work_id)
        if payload.get("work_id") != request.work_id:
            raise MissionAcceptanceContractError("WORKS evidence rebound to another Work")

        chain = payload.get("identity_chain")
        if not isinstance(chain, Mapping):
            return MissionAcceptanceProjection(
                accepted=False,
                status="provenance_gap",
                outcome_status=None,
                bundle_id=_text(payload.get("bundle_id")),
            )

        expected = {
            "mission_id": request.mission_id,
            "work_id": request.work_id,
            "execution_context_id": request.execution_context_id,
            "execution_policy_decision_id": request.execution_policy_decision_id,
        }
        for field, value in expected.items():
            if chain.get(field) != value:
                raise MissionAcceptanceContractError(
                    f"WORKS identity chain changed {field}"
                )

        projection = payload.get("platform_outcome_verification")
        if not isinstance(projection, Mapping):
            return MissionAcceptanceProjection(
                accepted=False,
                status="pending",
                outcome_status=None,
                bundle_id=_text(payload.get("bundle_id")),
            )

        status = _text(projection.get("status")) or "pending"
        outcome_status = _text(projection.get("outcome_status"))
        accepted = status == "verified" and outcome_status == "passed"
        return MissionAcceptanceProjection(
            accepted=accepted,
            status=status,
            outcome_status=outcome_status,
            bundle_id=_text(payload.get("bundle_id")),
        )


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
