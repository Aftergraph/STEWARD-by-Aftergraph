"""Canonical WORKS adapter for the STEWARD P2 vertical slice.

This module intentionally does *not* reimplement WORKS semantics.  It is a thin,
fail-closed client for the existing WORKS HTTP boundary frozen at the P2
baseline.  In particular, dispatch correlation identity is owned by WORKS:
STEWARD may send the required dispatch bindings, but it cannot choose
``execution_context_id`` or ``trace_id``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


_CTX_RE = re.compile(r"^ctx_[a-f0-9]{32}$")
_TRACE_RE = re.compile(r"^trc_[a-f0-9]{32}$")


class WorksError(RuntimeError):
    """Base class for WORKS adapter failures."""


class WorksHTTPError(WorksError):
    """WORKS returned a non-success HTTP response."""

    def __init__(self, status: int, code: str, detail: str = "") -> None:
        super().__init__(f"WORKS HTTP {status} {code}: {detail}".strip())
        self.status = status
        self.code = code
        self.detail = detail


class WorksUnavailableError(WorksHTTPError):
    """The canonical dispatch acceptance surface is unavailable."""


class WorksStaleAuthorityError(WorksHTTPError):
    """WORKS rejected a dispatch because the authority epoch is stale."""


class WorksContractError(WorksError):
    """A response violates the frozen STEWARD↔WORKS contract assumptions."""


@dataclass(frozen=True)
class DispatchAcceptanceRequest:
    """Runtime-built fields accepted by WORKS dispatch.acceptance/1.0.

    Deliberately absent: execution_context_id and trace_id.  WORKS owns those
    correlation identities and the canonical HTTP handler rejects client-side
    injection with DisallowUnknownFields.
    """

    mission_id: str
    authority_ref: str
    authority_epoch: int
    runtime_dispatch_id: str
    attempt_id: str
    effect_id: str
    idempotency_key: str
    budget_ref: str
    budget_ceiling: int
    checkpoint_id: str
    evidence_root: str
    verification_subject: str
    causal_id: str

    def to_wire(self) -> dict[str, Any]:
        if self.authority_epoch < 0:
            raise WorksContractError("authority_epoch must be >= 0")
        if self.budget_ceiling < 0:
            raise WorksContractError("budget_ceiling must be >= 0")
        wire = asdict(self)
        forbidden = {"execution_context_id", "trace_id"} & wire.keys()
        if forbidden:
            raise WorksContractError(f"client cannot mint WORKS correlation ids: {sorted(forbidden)}")
        return wire


@dataclass(frozen=True)
class DispatchAcceptanceResponse:
    works_execution_id: str
    mission_id: str
    authority_ref: str
    authority_epoch: int
    runtime_dispatch_id: str
    attempt_id: str
    effect_id: str
    idempotency_key: str
    budget_ref: str
    budget_ceiling: int
    checkpoint_id: str
    evidence_root: str
    verification_subject: str
    causal_id: str
    outcome: str
    verified: bool
    execution_context_id: str
    trace_id: str
    verifier_id: str | None = None
    verdict: Mapping[str, Any] | None = None

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "DispatchAcceptanceResponse":
        required = {
            "works_execution_id",
            "mission_id",
            "authority_ref",
            "authority_epoch",
            "runtime_dispatch_id",
            "attempt_id",
            "effect_id",
            "idempotency_key",
            "budget_ref",
            "budget_ceiling",
            "checkpoint_id",
            "evidence_root",
            "verification_subject",
            "causal_id",
            "outcome",
            "verified",
            "execution_context_id",
            "trace_id",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise WorksContractError(f"dispatch acceptance response missing fields: {missing}")

        ctx = payload["execution_context_id"]
        trace = payload["trace_id"]
        if not isinstance(ctx, str) or not _CTX_RE.fullmatch(ctx):
            raise WorksContractError("WORKS returned invalid execution_context_id")
        if not isinstance(trace, str) or not _TRACE_RE.fullmatch(trace):
            raise WorksContractError("WORKS returned invalid trace_id")
        if payload["outcome"] not in {"ACCEPTED", "SUCCEEDED", "FAILED", "INDETERMINATE"}:
            raise WorksContractError("WORKS returned invalid dispatch outcome")
        if not isinstance(payload["verified"], bool):
            raise WorksContractError("WORKS returned non-boolean verified")
        if payload["verified"] and payload["outcome"] != "SUCCEEDED":
            raise WorksContractError("verified dispatch must be SUCCEEDED")

        return cls(
            **{name: payload[name] for name in required},
            verifier_id=payload.get("verifier_id"),
            verdict=payload.get("verdict"),
        )


@dataclass(frozen=True)
class DispatchAcceptanceV2Request:
    """Runtime-built dispatch.acceptance/2.0 fields.

    WORKS owns execution_context_id and trace_id. Verification subject is
    intentionally absent from initial acceptance and is bound exactly once
    after the effect is observed.
    """

    organization_id: str
    tenant_id: str
    principal_id: str
    mission_id: str
    authority_lease_id: str
    worker_lease_id: str
    admission_decision_id: str
    runtime_dispatch_id: str
    attempt_id: str
    effect_id: str
    idempotency_key: str
    budget_ref: str
    budget_ceiling: int
    checkpoint_id: str
    evidence_root: str
    causal_id: str
    schema: str = "dispatch.acceptance/2.0"

    def to_wire(self) -> dict[str, Any]:
        if self.schema != "dispatch.acceptance/2.0":
            raise WorksContractError("unsupported dispatch.acceptance schema")
        if self.budget_ceiling < 0:
            raise WorksContractError("budget_ceiling must be >= 0")
        wire = asdict(self)
        required = (
            "organization_id", "tenant_id", "principal_id", "mission_id",
            "authority_lease_id", "worker_lease_id", "admission_decision_id",
            "runtime_dispatch_id", "attempt_id", "effect_id", "idempotency_key",
            "budget_ref", "checkpoint_id", "evidence_root", "causal_id",
        )
        missing = [name for name in required if not isinstance(wire[name], str) or not wire[name]]
        if missing:
            raise WorksContractError(f"dispatch.acceptance/2.0 missing fields: {missing}")
        forbidden = {
            "authority_epoch", "execution_context_id", "trace_id",
            "verification_subject", "works_execution_id",
        } & wire.keys()
        if forbidden:
            raise WorksContractError(
                f"dispatch.acceptance/2.0 client fields are forbidden: {sorted(forbidden)}"
            )
        return wire


@dataclass(frozen=True)
class DispatchAcceptanceV2Response:
    schema: str
    work_id: str
    works_execution_id: str
    request: Mapping[str, Any]
    execution_context: Mapping[str, Any]
    outcome: str
    verified: bool
    verifier_id: str | None = None
    verdict: Mapping[str, Any] | None = None

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "DispatchAcceptanceV2Response":
        required = {
            "schema", "work_id", "works_execution_id", "request",
            "execution_context", "outcome", "verified",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise WorksContractError(f"dispatch.acceptance/2.0 response missing fields: {missing}")
        if payload["schema"] != "dispatch.acceptance/2.0":
            raise WorksContractError("WORKS returned an unsupported dispatch.acceptance schema")
        if not isinstance(payload["work_id"], str) or not payload["work_id"]:
            raise WorksContractError("WORKS returned an invalid work_id")
        if not isinstance(payload["works_execution_id"], str) or not payload["works_execution_id"]:
            raise WorksContractError("WORKS returned an invalid works_execution_id")
        request = payload["request"]
        context = payload["execution_context"]
        if not isinstance(request, Mapping) or request.get("schema") != "dispatch.acceptance/2.0":
            raise WorksContractError("WORKS returned an invalid dispatch request echo")
        if not isinstance(context, Mapping):
            raise WorksContractError("WORKS returned a non-object execution context")
        context_required = {
            "schema", "execution_context_id", "organization_id", "tenant_id",
            "principal_id", "mission_id", "authority_lease_id", "work_id",
            "worker_id", "worker_lease_id", "admission_decision_id", "trace_id",
        }
        context_missing = sorted(context_required - context.keys())
        if context_missing:
            raise WorksContractError(
                f"WORKS returned an incomplete execution context: {context_missing}"
            )
        if context["schema"] != "execution-context/1.0":
            raise WorksContractError("WORKS returned an unsupported execution-context schema")
        if context["work_id"] != payload["work_id"]:
            raise WorksContractError("WORKS execution context is bound to another Work")
        if not isinstance(context["execution_context_id"], str) or not _CTX_RE.fullmatch(
            context["execution_context_id"]
        ):
            raise WorksContractError("WORKS returned invalid execution_context_id")
        if not isinstance(context["trace_id"], str) or not _TRACE_RE.fullmatch(context["trace_id"]):
            raise WorksContractError("WORKS returned invalid trace_id")
        forbidden_echo = {
            "authority_epoch", "execution_context_id", "trace_id", "verification_subject"
        } & request.keys()
        if forbidden_echo:
            raise WorksContractError(
                f"WORKS echoed forbidden V2 request fields: {sorted(forbidden_echo)}"
            )
        if payload["outcome"] not in {"ACCEPTED", "SUCCEEDED", "FAILED", "INDETERMINATE"}:
            raise WorksContractError("WORKS returned invalid dispatch outcome")
        if not isinstance(payload["verified"], bool):
            raise WorksContractError("WORKS returned non-boolean verified")
        if payload["verified"] and payload["outcome"] != "SUCCEEDED":
            raise WorksContractError("verified dispatch must be SUCCEEDED")
        return cls(
            schema=payload["schema"],
            work_id=payload["work_id"],
            works_execution_id=payload["works_execution_id"],
            request=request,
            execution_context=context,
            outcome=payload["outcome"],
            verified=payload["verified"],
            verifier_id=payload.get("verifier_id"),
            verdict=payload.get("verdict"),
        )


@dataclass(frozen=True)
class VerificationSubjectBindingRequest:
    """Post-effect exact-subject binding owned by WORKS."""

    attempt_id: str
    effect_id: str
    causal_id: str
    subject: str
    schema: str = "dispatch.verification-subject/1.0"

    def to_wire(self) -> dict[str, Any]:
        if self.schema != "dispatch.verification-subject/1.0":
            raise WorksContractError("unsupported verification-subject schema")
        values = {
            "attempt_id": self.attempt_id,
            "effect_id": self.effect_id,
            "causal_id": self.causal_id,
            "subject": self.subject,
        }
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise WorksContractError("verification-subject binding fields are required")
        return {"schema": self.schema, **values}


class WorksClient:
    """Small fail-closed HTTP client for canonical WORKS surfaces."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        timeout: float = 10.0,
        platform_token: str | None = None,
        bridge_secret: str | None = None,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        if not bearer_token:
            raise ValueError("bearer_token is required")
        if platform_token is not None and not platform_token:
            raise ValueError("platform_token cannot be empty")
        if bridge_secret is not None and not bridge_secret:
            raise ValueError("bridge_secret cannot be empty")
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token
        self._platform_token = platform_token
        self._bridge_secret = bridge_secret
        self._timeout = timeout

    def create_work(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._json("POST", "/v1/works", payload)

    def get_work(self, work_id: str) -> Mapping[str, Any]:
        return self._json("GET", f"/v1/works/{work_id}")

    def get_evidence(self, work_id: str) -> Mapping[str, Any]:
        payload = self._json("GET", f"/v1/works/{work_id}/evidence")
        if not isinstance(payload, Mapping):
            raise WorksContractError("WORKS evidence response must be a JSON object")
        return payload

    def list_events(self, work_id: str, *, after: int = 0, limit: int = 100) -> Any:
        if after < 0 or limit <= 0:
            raise ValueError("after must be >= 0 and limit must be > 0")
        query = urlencode({"after": after, "limit": limit})
        return self._json("GET", f"/v1/works/{work_id}/events?{query}")

    def accept_dispatch(
        self,
        work_id: str,
        request: DispatchAcceptanceRequest,
    ) -> DispatchAcceptanceResponse:
        payload = self._json("POST", f"/v1/works/{work_id}/accept", request.to_wire())
        if not isinstance(payload, Mapping):
            raise WorksContractError("dispatch acceptance response must be a JSON object")
        response = DispatchAcceptanceResponse.from_wire(payload)
        if response.mission_id != request.mission_id:
            raise WorksContractError("WORKS acceptance changed mission_id")
        if response.runtime_dispatch_id != request.runtime_dispatch_id:
            raise WorksContractError("WORKS acceptance changed runtime_dispatch_id")
        if response.idempotency_key != request.idempotency_key:
            raise WorksContractError("WORKS acceptance changed idempotency_key")
        if response.verification_subject != request.verification_subject:
            raise WorksContractError("WORKS acceptance changed verification_subject")
        return response

    def accept_dispatch_v2(
        self,
        work_id: str,
        request: DispatchAcceptanceV2Request,
    ) -> DispatchAcceptanceV2Response:
        if not self._platform_token or not self._bridge_secret:
            raise WorksContractError(
                "dispatch.acceptance/2.0 requires platform_token and bridge_secret"
            )
        payload = self._json(
            "POST",
            f"/v2/works/{work_id}/accept",
            request.to_wire(),
            extra_headers={
                "Authorization": f"Bearer {self._platform_token}",
                "X-Works-Platform-Bridge": self._bridge_secret,
            },
        )
        if not isinstance(payload, Mapping):
            raise WorksContractError("dispatch.acceptance/2.0 response must be a JSON object")
        response = DispatchAcceptanceV2Response.from_wire(payload)
        if response.work_id != work_id:
            raise WorksContractError("WORKS acceptance changed work_id")
        sent = request.to_wire()
        for field in (
            "organization_id", "tenant_id", "principal_id", "mission_id",
            "authority_lease_id", "worker_lease_id", "admission_decision_id",
            "runtime_dispatch_id", "attempt_id", "effect_id", "idempotency_key",
            "budget_ref", "budget_ceiling", "checkpoint_id", "evidence_root", "causal_id",
        ):
            if response.request.get(field) != sent[field]:
                raise WorksContractError(f"WORKS acceptance changed {field}")
        return response

    def bind_verification_subject(
        self,
        work_id: str,
        works_execution_id: str,
        request: VerificationSubjectBindingRequest,
    ) -> Mapping[str, Any]:
        if not self._platform_token or not self._bridge_secret:
            raise WorksContractError(
                "verification-subject binding requires platform_token and bridge_secret"
            )
        payload = self._json(
            "POST",
            (
                f"/v2/works/{work_id}/acceptances/"
                f"{quote(works_execution_id, safe='')}/verification-subject"
            ),
            request.to_wire(),
            extra_headers={
                "Authorization": f"Bearer {self._platform_token}",
                "X-Works-Platform-Bridge": self._bridge_secret,
            },
        )
        if not isinstance(payload, Mapping):
            raise WorksContractError("verification-subject response must be a JSON object")
        required = {
            "schema", "work_id", "works_execution_id", "attempt_id",
            "effect_id", "causal_id", "subject", "bound_at",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise WorksContractError(f"verification-subject response missing fields: {missing}")
        if payload["schema"] != "dispatch.verification-subject/1.0":
            raise WorksContractError("WORKS returned an unsupported subject-binding schema")
        if payload["work_id"] != work_id or payload["works_execution_id"] != works_execution_id:
            raise WorksContractError("WORKS subject binding changed its execution identity")
        sent = request.to_wire()
        for field in ("attempt_id", "effect_id", "causal_id", "subject"):
            if payload[field] != sent[field]:
                raise WorksContractError(f"WORKS subject binding changed {field}")
        return payload

    def _json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        if extra_headers:
            headers.update(extra_headers)
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(self._base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self._timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            code = "http_error"
            detail = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, Mapping):
                    code = str(parsed.get("error") or parsed.get("code") or code)
                    detail = str(parsed.get("detail") or parsed.get("message") or detail)
            except json.JSONDecodeError:
                pass
            error_cls: type[WorksHTTPError] = WorksHTTPError
            if exc.code == 503 and code == "dispatch_accept_unavailable":
                error_cls = WorksUnavailableError
            elif exc.code == 409 and code == "dispatch_stale_authority":
                error_cls = WorksStaleAuthorityError
            raise error_cls(exc.code, code, detail) from exc
        except URLError as exc:
            raise WorksUnavailableError(0, "transport_unavailable", str(exc.reason)) from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorksContractError("WORKS returned non-JSON response") from exc
