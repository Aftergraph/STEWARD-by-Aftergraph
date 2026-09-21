"""STEWARD client for Trust Gateway's canonical Platform V2.1 action path.

The locked Trust Gateway baseline exposes POST /v1/actions.  Supplying a
canonical execution_context_id selects the V2.1 path:

    current platform identity
      -> immutable WORKS execution context
      -> AIE live revalidation(action_id)
      -> execution-phase PDR
      -> durable WORKS PDR correlation
      -> dispatch

STEWARD never invokes the legacy action path: execution_context_id and action_id
are mandatory here, and the client validates that the successful response echoes
the same execution context and carries an execution PDR reference.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_ACTION_RE = re.compile(r"^act_[a-f0-9]{32}$")
_CTX_RE = re.compile(r"^ctx_[a-f0-9]{32}$")
_PDR_RE = re.compile(r"^pdr_[a-f0-9]{32}$")


class TrustGatewayError(RuntimeError):
    """Base class for Trust Gateway composition failures."""


class TrustGatewayContractError(TrustGatewayError):
    """Request/response violates the STEWARD V2.1 integration contract."""


class TrustGatewayUnavailableError(TrustGatewayError):
    """Trust Gateway or its required execution-time dependency is unavailable."""


class TrustGatewayDeniedError(TrustGatewayError):
    """Trust Gateway denied the proposed action."""

    def __init__(self, status: int, code: str, *, error_code: str | None = None) -> None:
        super().__init__(f"Trust Gateway denied action: HTTP {status} {code}")
        self.status = status
        self.code = code
        self.error_code = error_code


@dataclass(frozen=True)
class TrustGatewayActionRequest:
    action_id: str
    execution_context_id: str
    mission_id: str
    tool: str
    args: Any = None

    def to_wire(self) -> dict[str, Any]:
        if not _ACTION_RE.fullmatch(self.action_id):
            raise TrustGatewayContractError("action_id must be canonical act_<32 hex>")
        if not _CTX_RE.fullmatch(self.execution_context_id):
            raise TrustGatewayContractError(
                "execution_context_id is mandatory; STEWARD cannot use the legacy TG path"
            )
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise TrustGatewayContractError("mission_id is required")
        if not isinstance(self.tool, str) or not self.tool.strip():
            raise TrustGatewayContractError("tool is required")
        return {
            "action_id": self.action_id,
            "execution_context_id": self.execution_context_id,
            "mission_id": self.mission_id,
            "tool": self.tool,
            "args": self.args,
        }


@dataclass(frozen=True)
class TrustGatewayApprovalRequired:
    approval_id: str
    reason: str | None = None


@dataclass(frozen=True)
class TrustGatewayActionReceipt:
    admission_decision_id: str
    execution_context_id: str
    execution_pdr_id: str
    result: Any

    @classmethod
    def from_wire(
        cls,
        request: TrustGatewayActionRequest,
        payload: Mapping[str, Any],
    ) -> "TrustGatewayActionReceipt":
        if payload.get("decision") != "allow":
            raise TrustGatewayContractError("successful TG response did not say allow")
        ctx = payload.get("execution_context_id")
        pdr = payload.get("execution_pdr_id")
        admission = payload.get("admission_decision_id")
        if ctx != request.execution_context_id or not isinstance(ctx, str) or not _CTX_RE.fullmatch(ctx):
            raise TrustGatewayContractError("TG response changed or omitted execution_context_id")
        if not isinstance(pdr, str) or not pdr.strip():
            raise TrustGatewayContractError("TG response missing execution_pdr_id")
        # Current baseline uses canonical pdr_ ids. Keep an explicit format gate
        # when the identifier uses the frozen canonical shape.
        if pdr.startswith("pdr_") and not _PDR_RE.fullmatch(pdr):
            raise TrustGatewayContractError("TG returned malformed execution_pdr_id")
        if not isinstance(admission, str) or not admission.strip():
            raise TrustGatewayContractError("TG response missing admission_decision_id")
        return cls(
            admission_decision_id=admission,
            execution_context_id=ctx,
            execution_pdr_id=pdr,
            result=payload.get("result"),
        )


class TrustGatewayClient:
    """HTTP client that only exposes the governed V2.1 execution path."""

    def __init__(self, base_url: str, bearer_token: str, *, timeout: float = 10.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        if not bearer_token:
            raise ValueError("bearer_token is required")
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token
        self._timeout = timeout

    def execute(
        self,
        request: TrustGatewayActionRequest,
    ) -> TrustGatewayActionReceipt | TrustGatewayApprovalRequired:
        body = json.dumps(request.to_wire(), separators=(",", ":")).encode("utf-8")
        req = Request(
            self._base_url + "/v1/actions",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
            method="POST",
        )
        status: int
        raw: bytes
        try:
            with urlopen(req, timeout=self._timeout) as response:
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
            payload = self._decode(raw)
            code = str(payload.get("error") or payload.get("decision") or "denied")
            error_code = payload.get("error_code")
            # AIE / WORKS execution-correlation failures are not retried or
            # bypassed locally. Infrastructure unavailability remains explicit.
            if status in {500, 502, 503, 504}:
                raise TrustGatewayUnavailableError(
                    f"Trust Gateway execution path unavailable: HTTP {status} {code}"
                ) from exc
            raise TrustGatewayDeniedError(
                status,
                code,
                error_code=str(error_code) if error_code is not None else None,
            ) from exc
        except URLError as exc:
            raise TrustGatewayUnavailableError(
                f"Trust Gateway transport unavailable: {exc.reason}"
            ) from exc

        payload = self._decode(raw)
        if status == 202:
            if payload.get("decision") != "needs_approval":
                raise TrustGatewayContractError("TG 202 response was not needs_approval")
            approval_id = payload.get("approvalId")
            if not isinstance(approval_id, str) or not approval_id.strip():
                raise TrustGatewayContractError("TG approval response missing approvalId")
            return TrustGatewayApprovalRequired(
                approval_id=approval_id,
                reason=payload.get("reason") if isinstance(payload.get("reason"), str) else None,
            )
        if status != 200:
            raise TrustGatewayContractError(f"unexpected TG success status {status}")
        return TrustGatewayActionReceipt.from_wire(request, payload)

    @staticmethod
    def _decode(raw: bytes) -> Mapping[str, Any]:
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise TrustGatewayContractError("TG returned non-JSON response") from exc
        if not isinstance(payload, Mapping):
            raise TrustGatewayContractError("TG response must be a JSON object")
        return payload
