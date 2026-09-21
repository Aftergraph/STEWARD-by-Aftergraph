"""STEWARD port into the canonical Aftergraph Runtime plane.

The locked Runtime baseline exposes the dispatch-seal semantics as a TypeScript
library primitive. It does not expose a STEWARD-specific production HTTP API.
This module therefore defines a transport-neutral composition port rather than
inventing an endpoint or duplicating Runtime scheduling/execution truth.

A deployment must inject a transport that reaches the canonical Runtime owner.
There is deliberately no direct-to-WORKS fallback in this port.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping, Protocol


_CTX_RE = re.compile(r"^ctx_[a-f0-9]{32}$")
_TRACE_RE = re.compile(r"^trc_[a-f0-9]{32}$")


class RuntimeErrorBase(RuntimeError):
    """Base class for Runtime port failures."""


class RuntimeUnavailableError(RuntimeErrorBase):
    """The canonical Runtime transport is unavailable."""


class RuntimeContractError(RuntimeErrorBase):
    """Runtime request/receipt violates the frozen composition contract."""


@dataclass(frozen=True)
class RuntimeDispatchRequest:
    """Inputs STEWARD may present to Runtime before Runtime mints dispatch ID.

    Correlation owned by WORKS is absent. Runtime's own baseline may derive its
    runtime dispatch identity deterministically from the idempotency key.
    """

    mission_id: str
    authority_ref: str
    authority_epoch: int
    attempt_id: str
    effect_id: str
    idempotency_key: str
    budget_ref: str
    budget_ceiling: int
    checkpoint_id: str
    evidence_root: str
    verification_subject: str
    causal_id: str

    def to_runtime_wire(self) -> dict[str, Any]:
        if self.authority_epoch < 0 or self.budget_ceiling < 0:
            raise RuntimeContractError("authority_epoch and budget_ceiling must be >= 0")
        values = asdict(self)
        if any(
            not isinstance(v, str) or not v.strip()
            for k, v in values.items()
            if k not in {"authority_epoch", "budget_ceiling"}
        ):
            raise RuntimeContractError("all Runtime dispatch bindings must be non-empty")
        return {
            "schema": "runtime.dispatch-seal/0.1",
            "missionId": self.mission_id,
            "authorityRef": self.authority_ref,
            "authorityEpoch": self.authority_epoch,
            "attemptId": self.attempt_id,
            "effectId": self.effect_id,
            "idempotencyKey": self.idempotency_key,
            "budgetRef": self.budget_ref,
            "budgetCeiling": self.budget_ceiling,
            "checkpointId": self.checkpoint_id,
            "evidenceRoot": self.evidence_root,
            "verificationSubject": self.verification_subject,
            "causalId": self.causal_id,
        }


@dataclass(frozen=True)
class RuntimeDispatchReceipt:
    runtime_dispatch_id: str
    works_execution_id: str
    execution_context_id: str | None = None
    trace_id: str | None = None

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "RuntimeDispatchReceipt":
        runtime_dispatch_id = payload.get("runtimeDispatchId")
        works_execution_id = payload.get("worksExecutionId")
        if not isinstance(runtime_dispatch_id, str) or not runtime_dispatch_id.strip():
            raise RuntimeContractError("Runtime receipt missing runtimeDispatchId")
        if not isinstance(works_execution_id, str) or not works_execution_id.strip():
            raise RuntimeContractError("Runtime receipt missing worksExecutionId")
        ctx = payload.get("executionContextId")
        trace = payload.get("traceId")
        if ctx is not None and (not isinstance(ctx, str) or not _CTX_RE.fullmatch(ctx)):
            raise RuntimeContractError("Runtime receipt carries malformed executionContextId")
        if trace is not None and (not isinstance(trace, str) or not _TRACE_RE.fullmatch(trace)):
            raise RuntimeContractError("Runtime receipt carries malformed traceId")
        return cls(
            runtime_dispatch_id=runtime_dispatch_id,
            works_execution_id=works_execution_id,
            execution_context_id=ctx,
            trace_id=trace,
        )


class RuntimeTransport(Protocol):
    """Deployment-provided transport into canonical Runtime."""

    def dispatch(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class RuntimePort:
    """Fail-closed composition port; never bypasses Runtime on transport failure."""

    def __init__(self, transport: RuntimeTransport) -> None:
        self._transport = transport

    def dispatch(self, request: RuntimeDispatchRequest) -> RuntimeDispatchReceipt:
        try:
            payload = self._transport.dispatch(request.to_runtime_wire())
        except RuntimeErrorBase:
            raise
        except Exception as exc:
            raise RuntimeUnavailableError("canonical Runtime transport failed") from exc
        if not isinstance(payload, Mapping):
            raise RuntimeContractError("Runtime transport returned non-object receipt")
        return RuntimeDispatchReceipt.from_wire(payload)
