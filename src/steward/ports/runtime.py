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
import json
import os
import re
import subprocess
from typing import Any, Mapping, Protocol, Sequence


_CTX_RE = re.compile(r"^ctx_[a-f0-9]{32}$")
_TRACE_RE = re.compile(r"^trc_[a-f0-9]{32}$")
_ORG_RE = re.compile(r"^org_[a-f0-9]{32}$")
_TENANT_RE = re.compile(r"^ten_[a-f0-9]{32}$")
_PRINCIPAL_RE = re.compile(r"^prn_[a-f0-9]{32}$")
_AUTH_RE = re.compile(r"^auth_[a-f0-9]{32}$")
_WORK_RE = re.compile(r"^wrk_[a-f0-9]{32}$")
_WORKER_LEASE_RE = re.compile(r"^lse_[a-f0-9]{32}$")
_PDR_RE = re.compile(r"^pdr_[a-f0-9]{32}$")
_WORKER_RE = re.compile(r"^wrkr_[a-f0-9]{32}$")


class RuntimeErrorBase(RuntimeError):
    """Base class for Runtime port failures."""


class RuntimeUnavailableError(RuntimeErrorBase):
    """The canonical Runtime transport is unavailable."""


class RuntimeRejectedError(RuntimeErrorBase):
    """Canonical Runtime rejected the dispatch before effect execution."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Runtime rejected dispatch: {reason}")
        self.reason = reason


class RuntimeContractError(RuntimeErrorBase):
    """Runtime request/receipt violates the frozen composition contract."""


@dataclass(frozen=True)
class RuntimeDispatchRequest:
    """Inputs STEWARD may present to Runtime before Runtime mints dispatch ID.

    Correlation owned by WORKS is absent. Runtime's own baseline may derive its
    runtime dispatch identity deterministically from the idempotency key.
    """

    work_id: str
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
            "workId": self.work_id,
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


@dataclass(frozen=True)
class RuntimeDispatchV2Request:
    """P2/V2.1 Runtime request for WORKS dispatch.acceptance/2.0.

    No authority_epoch is present. Authority is represented by the canonical
    AuthorityLease + admission decision references, and is revalidated later at
    the consequential action boundary by Trust Gateway through AIE.
    """

    work_id: str
    organization_id: str
    tenant_id: str
    principal_id: str
    mission_id: str
    authority_lease_id: str
    worker_lease_id: str
    admission_decision_id: str
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
        patterns = {
            "work_id": (_WORK_RE, self.work_id),
            "organization_id": (_ORG_RE, self.organization_id),
            "tenant_id": (_TENANT_RE, self.tenant_id),
            "principal_id": (_PRINCIPAL_RE, self.principal_id),
            "authority_lease_id": (_AUTH_RE, self.authority_lease_id),
            "worker_lease_id": (_WORKER_LEASE_RE, self.worker_lease_id),
            "admission_decision_id": (_PDR_RE, self.admission_decision_id),
        }
        for name, (pattern, value) in patterns.items():
            if not isinstance(value, str) or not pattern.fullmatch(value):
                raise RuntimeContractError(f"{name} has invalid canonical format")
        if not isinstance(self.budget_ceiling, int) or self.budget_ceiling < 0:
            raise RuntimeContractError("budget_ceiling must be an integer >= 0")
        for name, value in (
            ("mission_id", self.mission_id),
            ("attempt_id", self.attempt_id),
            ("effect_id", self.effect_id),
            ("idempotency_key", self.idempotency_key),
            ("budget_ref", self.budget_ref),
            ("checkpoint_id", self.checkpoint_id),
            ("evidence_root", self.evidence_root),
            ("causal_id", self.causal_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeContractError(f"{name} is required")
        return {
            "workId": self.work_id,
            "organizationId": self.organization_id,
            "tenantId": self.tenant_id,
            "principalId": self.principal_id,
            "missionId": self.mission_id,
            "authorityLeaseId": self.authority_lease_id,
            "workerLeaseId": self.worker_lease_id,
            "admissionDecisionId": self.admission_decision_id,
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
class RuntimeDispatchV2Receipt:
    runtime_dispatch_id: str
    works_execution_id: str
    work_id: str
    execution_context_id: str
    trace_id: str
    worker_id: str

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "RuntimeDispatchV2Receipt":
        values = {
            "runtime_dispatch_id": payload.get("runtimeDispatchId"),
            "works_execution_id": payload.get("worksExecutionId"),
            "work_id": payload.get("workId"),
            "execution_context_id": payload.get("executionContextId"),
            "trace_id": payload.get("traceId"),
            "worker_id": payload.get("workerId"),
        }
        if not isinstance(values["runtime_dispatch_id"], str) or not values["runtime_dispatch_id"].strip():
            raise RuntimeContractError("Runtime V2 receipt missing runtimeDispatchId")
        if not isinstance(values["works_execution_id"], str) or not values["works_execution_id"].strip():
            raise RuntimeContractError("Runtime V2 receipt missing worksExecutionId")
        if not isinstance(values["work_id"], str) or not _WORK_RE.fullmatch(values["work_id"]):
            raise RuntimeContractError("Runtime V2 receipt carries malformed workId")
        if not isinstance(values["execution_context_id"], str) or not _CTX_RE.fullmatch(values["execution_context_id"]):
            raise RuntimeContractError("Runtime V2 receipt carries malformed executionContextId")
        if not isinstance(values["trace_id"], str) or not _TRACE_RE.fullmatch(values["trace_id"]):
            raise RuntimeContractError("Runtime V2 receipt carries malformed traceId")
        if not isinstance(values["worker_id"], str) or not _WORKER_RE.fullmatch(values["worker_id"]):
            raise RuntimeContractError("Runtime V2 receipt carries malformed workerId")
        return cls(
            runtime_dispatch_id=values["runtime_dispatch_id"],
            works_execution_id=values["works_execution_id"],
            work_id=values["work_id"],
            execution_context_id=values["execution_context_id"],
            trace_id=values["trace_id"],
            worker_id=values["worker_id"],
        )


class RuntimeTransport(Protocol):
    """Deployment-provided transport into canonical Runtime."""

    def dispatch(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class SubprocessRuntimeTransport:
    """Concrete STEWARD transport for Runtime's runtime-steward-dispatch bridge.

    The request body carries no credentials. WORKS connectivity and bearer
    material stay in the Runtime process environment.
    """

    def __init__(
        self,
        command: Sequence[str] = ("runtime-steward-dispatch",),
        *,
        timeout: float = 15.0,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("Runtime bridge command must be a non-empty argv sequence")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self._command = tuple(command)
        self._timeout = timeout
        self._environment = dict(environment) if environment is not None else None

    def dispatch(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        serialized = json.dumps(payload, separators=(",", ":"))
        env = None
        if self._environment is not None:
            env = os.environ.copy()
            env.update(self._environment)
        try:
            proc = subprocess.run(
                self._command,
                input=serialized,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=env,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeUnavailableError("canonical Runtime bridge unavailable") from exc

        stdout = proc.stdout.strip()
        try:
            decoded = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeContractError("Runtime bridge returned non-JSON output") from exc
        if not isinstance(decoded, Mapping):
            raise RuntimeContractError("Runtime bridge output must be a JSON object")

        if proc.returncode != 0:
            reason = decoded.get("reason")
            if isinstance(reason, str) and reason:
                raise RuntimeRejectedError(reason)
            raise RuntimeUnavailableError(
                f"Runtime bridge exited with status {proc.returncode}"
            )

        if decoded.get("ok") is not True:
            raise RuntimeContractError("Runtime bridge success response missing ok=true")
        receipt = decoded.get("receipt")
        if not isinstance(receipt, Mapping):
            raise RuntimeContractError("Runtime bridge success response missing receipt")
        return receipt


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


class RuntimeV2Port:
    """Fail-closed P2 port into Runtime's dispatch.acceptance/2.0 bridge."""

    def __init__(self, transport: RuntimeTransport) -> None:
        self._transport = transport

    def dispatch(self, request: RuntimeDispatchV2Request) -> RuntimeDispatchV2Receipt:
        try:
            payload = self._transport.dispatch(request.to_runtime_wire())
        except RuntimeErrorBase:
            raise
        except Exception as exc:
            raise RuntimeUnavailableError("canonical Runtime V2 transport failed") from exc
        if not isinstance(payload, Mapping):
            raise RuntimeContractError("Runtime V2 transport returned non-object receipt")
        receipt = RuntimeDispatchV2Receipt.from_wire(payload)
        if receipt.work_id != request.work_id:
            raise RuntimeContractError("Runtime V2 receipt rebound to another Work")
        return receipt
