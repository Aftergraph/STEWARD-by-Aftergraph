"""The governed mission workflow: the autonomous Level 4+5 chain as one run.

This module composes the full ladder into a single self-driving mission:

    mission -> governed git effect (Level 4)
            -> Sentinel delegation + verdict (Level 5)
            -> acceptance (greenlight)
            -> evidence bundle with external WORKS correlation

The workflow never mints owner identity. WORKS execution context and trace
IDs (`ctx_`/`trc_`) arrive from the deployment plane and are validated, not
created. Without external correlation the mission refuses to start: fail
closed, exactly like the P2 adapter contract requires.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from steward_reference.governed_agent import AuditEvent, GovernedAgent
from steward_reference.sentinel_delegation import (
    AieMint,
    SentinelVerdict,
    accept_mission_with_delegated_verdict,
    request_sentinel_delegation,
)

_CTX_RE = re.compile(r"^ctx_[a-f0-9]{32}$")
_TRACE_RE = re.compile(r"^trc_[a-f0-9]{32}$")


class MissionCorrelationError(ValueError):
    """Raised when external WORKS correlation is absent or malformed."""


@dataclass(frozen=True)
class WorksCorrelation:
    execution_context_id: str
    trace_id: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WorksCorrelation":
        ctx = data.get("execution_context_id", "")
        trace = data.get("trace_id", "")
        if not _CTX_RE.match(ctx or ""):
            raise MissionCorrelationError(
                "execution_context_id must be a WORKS-minted ctx_[a-f0-9]{32}; STEWARD never mints it"
            )
        if not _TRACE_RE.match(trace or ""):
            raise MissionCorrelationError(
                "trace_id must be a WORKS/Runtime-minted trc_[a-f0-9]{32}; STEWARD never mints it"
            )
        return cls(execution_context_id=ctx, trace_id=trace)


class GovernedMissionWorkflow:
    """Runs one autonomous governed mission end to end.

    The deployment hands over: the agent persona, its delegated grant, an
    AIE mint instance, and externally minted WORKS correlation. The workflow
    then drives itself: effect -> delegation -> verdict -> acceptance, and
    returns an evidence bundle fit for the P2 causal chain.
    """

    def __init__(
        self,
        *,
        mission_id: str,
        persona_id: str,
        grant: dict[str, Any],
        correlation: WorksCorrelation,
        mint: AieMint,
    ) -> None:
        self.mission_id = mission_id
        self.correlation = correlation
        self.mint = mint
        self.agent = GovernedAgent(persona_id=persona_id, grant=grant)
        self._steps: list[dict[str, Any]] = []

    def _step(self, kind: str, decision: str, detail: str) -> None:
        self._steps.append(
            {
                "step": len(self._steps) + 1,
                "kind": kind,
                "decision": decision,
                "detail": detail,
            }
        )

    def run(self, *, now: datetime | None = None) -> dict[str, Any]:
        moment = now or datetime.now(timezone.utc)

        self._step("mission.start", "BEGIN", f"mission={self.mission_id} correlation={self.correlation.execution_context_id}")

        merge_receipt = self.agent.attempt_merge(now=moment)
        if not merge_receipt["merged"]:
            self._step("effect.blocked", "DENY", merge_receipt["decision"]["reason"])
            return self._bundle(accepted=False, verdict=None, result_sha=None)

        result_sha = merge_receipt["result_sha"]
        self._step("effect.complete", "ALLOW", f"governed merge produced result_sha={result_sha}")

        try:
            spawn = request_sentinel_delegation(
                agent_grant=self.agent.grant,
                subject_sha=result_sha,
                now=moment,
                mint=self.mint,
            )
        except Exception as exc:
            self._step("delegation.denied", "DENY", str(exc))
            return self._bundle(accepted=False, verdict=None, result_sha=result_sha)

        child = spawn.child_grant
        self._step(
            "delegation.spawned",
            "ALLOW",
            f"child_grant={child['grant_id']} delegated_by={child['delegated_by']} bound_sha={result_sha}",
        )

        try:
            verdict = spawn.issue_verdict(subject_sha=result_sha, now=moment)
        except Exception as exc:
            self._step("verdict.denied", "DENY", str(exc))
            return self._bundle(accepted=False, verdict=None, result_sha=result_sha)

        self._step("verdict.received", "PASS", f"verdict_id={verdict.verdict_id} subject={result_sha}")

        accepted = accept_mission_with_delegated_verdict(
            merged=True, verdict=verdict, result_sha=result_sha
        )
        self._step(
            "mission.acceptance",
            "ACCEPTED" if accepted else "REJECTED",
            "merged=True externally_verified=True subject_match=True",
        )
        return self._bundle(accepted=accepted, verdict=verdict, result_sha=result_sha)

    def _bundle(
        self,
        *,
        accepted: bool,
        verdict: SentinelVerdict | None,
        result_sha: str | None,
    ) -> dict[str, Any]:
        trace = [asdict_safe(e) for e in self.agent.trace()]
        return {
            "schema_version": "steward.mission-workflow/1.0",
            "mission_id": self.mission_id,
            "works_correlation": {
                "execution_context_id": self.correlation.execution_context_id,
                "trace_id": self.correlation.trace_id,
                "minted_by": "works-execution",
            },
            "outcome": {
                "accepted": accepted,
                "result_sha": result_sha,
                "verdict_id": verdict.verdict_id if verdict else None,
                "verifier_persona": verdict.verifier_persona_id if verdict else None,
                "delegated_by": verdict.delegated_by if verdict else None,
            },
            "workflow_steps": self._steps,
            "audit_trace": trace,
        }


def asdict_safe(event: AuditEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "at": event.at,
        "kind": event.kind,
        "actor": event.actor,
        "decision": event.decision,
        "detail": event.detail,
    }


def load_correlation(path: Path) -> WorksCorrelation:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return WorksCorrelation.from_mapping(data)
