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
from urllib.parse import urlencode
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


class WorksClient:
    """Small fail-closed HTTP client for canonical WORKS surfaces."""

    def __init__(self, base_url: str, bearer_token: str, *, timeout: float = 10.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        if not bearer_token:
            raise ValueError("bearer_token is required")
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token
        self._timeout = timeout

    def create_work(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._json("POST", "/v1/works", payload)

    def get_work(self, work_id: str) -> Mapping[str, Any]:
        return self._json("GET", f"/v1/works/{work_id}")

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

    def _json(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
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
