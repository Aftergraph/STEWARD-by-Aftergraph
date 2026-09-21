"""Post-effect exact-subject binding through canonical Runtime.

The final verification subject cannot be supplied at dispatch-accept time
because the candidate Git SHA does not exist until after the governed effect.
STEWARD therefore sends the observed immutable subject back through Runtime,
which binds it durably in WORKS. STEWARD never writes WORKS execution truth
directly.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .runtime import (
    RuntimeContractError,
    RuntimeErrorBase,
    RuntimeTransport,
    RuntimeUnavailableError,
)


_WORK_RE = re.compile(r"^wrk_[a-f0-9]{32}$")
_GIT_SUBJECT_RE = re.compile(
    r"^git:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+@[a-f0-9]{40}$"
)


@dataclass(frozen=True)
class RuntimeSubjectBindingRequest:
    work_id: str
    works_execution_id: str
    attempt_id: str
    effect_id: str
    causal_id: str
    subject: str

    def to_runtime_wire(self) -> dict[str, Any]:
        if not isinstance(self.work_id, str) or not _WORK_RE.fullmatch(self.work_id):
            raise RuntimeContractError("work_id has invalid canonical format")
        for name, value in (
            ("works_execution_id", self.works_execution_id),
            ("attempt_id", self.attempt_id),
            ("effect_id", self.effect_id),
            ("causal_id", self.causal_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeContractError(f"{name} is required")
        if not isinstance(self.subject, str) or not _GIT_SUBJECT_RE.fullmatch(self.subject):
            raise RuntimeContractError(
                "subject must be observed exact git:<owner>/<repo>@<40hex>"
            )
        return {
            "workId": self.work_id,
            "worksExecutionId": self.works_execution_id,
            "attemptId": self.attempt_id,
            "effectId": self.effect_id,
            "causalId": self.causal_id,
            "subject": self.subject,
        }


@dataclass(frozen=True)
class RuntimeSubjectBindingReceipt:
    work_id: str
    works_execution_id: str
    attempt_id: str
    effect_id: str
    causal_id: str
    subject: str
    bound_at: str

    @classmethod
    def from_wire(
        cls,
        request: RuntimeSubjectBindingRequest,
        payload: Mapping[str, Any],
    ) -> "RuntimeSubjectBindingReceipt":
        wire = {
            "work_id": payload.get("workId"),
            "works_execution_id": payload.get("worksExecutionId"),
            "attempt_id": payload.get("attemptId"),
            "effect_id": payload.get("effectId"),
            "causal_id": payload.get("causalId"),
            "subject": payload.get("subject"),
            "bound_at": payload.get("boundAt"),
        }
        expected = {
            "work_id": request.work_id,
            "works_execution_id": request.works_execution_id,
            "attempt_id": request.attempt_id,
            "effect_id": request.effect_id,
            "causal_id": request.causal_id,
            "subject": request.subject,
        }
        for name, value in expected.items():
            if wire[name] != value:
                raise RuntimeContractError(
                    f"Runtime subject receipt changed {name}"
                )
        if not isinstance(wire["bound_at"], str) or not wire["bound_at"].strip():
            raise RuntimeContractError("Runtime subject receipt missing boundAt")
        return cls(
            work_id=request.work_id,
            works_execution_id=request.works_execution_id,
            attempt_id=request.attempt_id,
            effect_id=request.effect_id,
            causal_id=request.causal_id,
            subject=request.subject,
            bound_at=wire["bound_at"],
        )


class RuntimeSubjectBindingPort:
    """Fail-closed post-effect exact-subject binder through Runtime."""

    def __init__(self, transport: RuntimeTransport) -> None:
        self._transport = transport

    def bind(
        self,
        request: RuntimeSubjectBindingRequest,
    ) -> RuntimeSubjectBindingReceipt:
        try:
            payload = self._transport.dispatch(request.to_runtime_wire())
        except RuntimeErrorBase:
            raise
        except Exception as exc:
            raise RuntimeUnavailableError(
                "canonical Runtime subject-binding transport failed"
            ) from exc
        if not isinstance(payload, Mapping):
            raise RuntimeContractError(
                "Runtime subject-binding transport returned non-object receipt"
            )
        return RuntimeSubjectBindingReceipt.from_wire(request, payload)
