"""Read-only STEWARD projection port for Sentinel exact-subject verdicts.

Sentinel remains the verdict authority.  This module cannot mint SHIP and does
not translate builder completion into verification.  It validates that the
returned verdict is bound to the exact 40-hex Git subject requested.

The locked Sentinel baseline states:
- verdicts are bound to exact HEAD;
- HEAD movement makes prior verdicts STALE;
- models cannot issue SHIP;
- GitHub check runs are keyed by repo + PR + exact headSha.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol


_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_VERDICTS = {"SHIP", "DO_NOT_SHIP", "BLOCKED", "STALE"}


class SentinelError(RuntimeError):
    """Base class for Sentinel integration failures."""


class SentinelUnavailableError(SentinelError):
    """The independent verifier could not be reached."""


class SentinelContractError(SentinelError):
    """A Sentinel response is malformed or bound to another subject."""


@dataclass(frozen=True)
class SentinelVerificationRequest:
    repository: str
    head_sha: str
    pull_request: int | None = None

    def to_wire(self) -> dict[str, Any]:
        if not isinstance(self.repository, str) or "/" not in self.repository:
            raise SentinelContractError("repository must be owner/name")
        if not isinstance(self.head_sha, str) or not _SHA_RE.fullmatch(self.head_sha):
            raise SentinelContractError("head_sha must be an exact 40-hex Git commit")
        if self.pull_request is not None and self.pull_request <= 0:
            raise SentinelContractError("pull_request must be positive when supplied")
        return {
            "repository": self.repository,
            "headSha": self.head_sha.lower(),
            **({"prNumber": self.pull_request} if self.pull_request is not None else {}),
        }


@dataclass(frozen=True)
class SentinelVerificationProjection:
    repository: str
    head_sha: str
    verdict: str
    verdict_ref: str
    evidence_refs: tuple[str, ...]

    @classmethod
    def from_wire(
        cls,
        request: SentinelVerificationRequest,
        payload: Mapping[str, Any],
    ) -> "SentinelVerificationProjection":
        repository = payload.get("repository", payload.get("repo"))
        head_sha = payload.get("headSha", payload.get("head_sha"))
        verdict = payload.get("verdict")
        verdict_ref = payload.get("verdictRef", payload.get("receipt_id", payload.get("checkRunId")))
        evidence = payload.get("evidenceRefs", payload.get("evidence", []))

        if repository != request.repository:
            raise SentinelContractError("Sentinel response changed repository subject")
        if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
            raise SentinelContractError("Sentinel response missing exact head SHA")
        if head_sha.lower() != request.head_sha.lower():
            raise SentinelContractError(
                "Sentinel verdict is bound to a different Git subject"
            )
        if verdict not in _VERDICTS:
            raise SentinelContractError(f"unsupported Sentinel verdict: {verdict!r}")
        if verdict_ref is None or str(verdict_ref).strip() == "":
            raise SentinelContractError("Sentinel response missing verdict reference")
        if not isinstance(evidence, (list, tuple)) or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise SentinelContractError("Sentinel evidence refs must be non-empty strings")
        return cls(
            repository=repository,
            head_sha=head_sha.lower(),
            verdict=verdict,
            verdict_ref=str(verdict_ref),
            evidence_refs=tuple(evidence),
        )

    def satisfies(self, current_head_sha: str) -> bool:
        """Only a current exact-subject SHIP can satisfy coding verification."""
        return (
            isinstance(current_head_sha, str)
            and bool(_SHA_RE.fullmatch(current_head_sha))
            and self.head_sha == current_head_sha.lower()
            and self.verdict == "SHIP"
        )


class SentinelTransport(Protocol):
    """Deployment-owned transport into Sentinel; no endpoint is invented here."""

    def verify_exact_head(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class SentinelPort:
    """Fail-closed consumer of independent Sentinel verdicts."""

    def __init__(self, transport: SentinelTransport) -> None:
        self._transport = transport

    def verify(
        self,
        request: SentinelVerificationRequest,
    ) -> SentinelVerificationProjection:
        try:
            payload = self._transport.verify_exact_head(request.to_wire())
        except SentinelError:
            raise
        except Exception as exc:
            raise SentinelUnavailableError("Sentinel verification transport failed") from exc
        if not isinstance(payload, Mapping):
            raise SentinelContractError("Sentinel transport returned non-object verdict")
        return SentinelVerificationProjection.from_wire(request, payload)
