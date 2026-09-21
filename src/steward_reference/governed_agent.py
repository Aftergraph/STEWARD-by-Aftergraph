"""A governed reference agent: Level 4 of the autonomy ladder.

The agent composes persona + delegated grant + fail-closed resolution into a
real effect chain. It never acts on its own selection: every effect attempt
passes through resolve_action, every decision lands in an immutable audit
trace, and acceptance of the resulting work still requires independent
exact-subject verification. An ALLOW receipt alone is not completion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import tempfile

from steward_reference.delegated_authority import grant_state, resolve_action


def _call(cwd: Path, *args: str) -> None:
    subprocess.check_call(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    at: str
    kind: str
    actor: str
    decision: str
    detail: str


class EffectBlockedError(RuntimeError):
    """Raised when an agent attempts a real effect without an ALLOW receipt."""


class GovernedAgent:
    """Executes governed git effects under a delegated-authority grant.

    The subject is a real temporary Git repository with a candidate branch.
    The agent may only merge when the resolver returns ALLOW for the
    pr:merge capability at the instant of the attempt. Every attempt —
    allowed or denied — becomes audit evidence.
    """

    def __init__(self, *, persona_id: str, grant: dict) -> None:
        self.persona_id = persona_id
        self.grant = grant
        self._trace: list[AuditEvent] = []
        self._seq = 0

    def _event(self, kind: str, decision: str, detail: str) -> None:
        self._seq += 1
        self._trace.append(
            AuditEvent(self._seq, _now_iso(), kind, self.persona_id, decision, detail)
        )

    def trace(self) -> tuple[AuditEvent, ...]:
        return tuple(self._trace)

    def attempt_merge(self, *, now: datetime | None = None) -> dict:
        """Attempt a real merge of the candidate branch into main.

        Returns a receipt: {'merged': bool, 'decision': dict, 'result_sha': str|None}.
        The merge is executed only on ALLOW; any DENY leaves main untouched.
        """
        receipt = resolve_action(
            grant=self.grant,
            requested_capability="pr:merge",
            now=now,
        )
        self._event("authority.resolve", receipt["decision"], json.dumps(receipt))

        if receipt["decision"] != "ALLOW":
            self._event("effect.blocked", "DENY", "no merge performed; main untouched")
            return {"merged": False, "decision": receipt, "result_sha": None}

        with tempfile.TemporaryDirectory(prefix="steward-agent-") as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            _call(repo, "git", "init", "-b", "main")
            _call(repo, "git", "config", "user.name", "Steward Governed Agent")
            _call(repo, "git", "config", "user.email", "agent@aftergraph.org")
            (repo / "feature.txt").write_text("seed\n", encoding="utf-8")
            _call(repo, "git", "add", ".")
            _call(repo, "git", "commit", "-m", "seed baseline")
            base_sha = _run(repo, "git", "rev-parse", "HEAD")

            _call(repo, "git", "checkout", "-b", "feat/candidate")
            (repo / "feature.txt").write_text("candidate change\n", encoding="utf-8")
            _call(repo, "git", "add", ".")
            _call(repo, "git", "commit", "-m", "feat: candidate change")
            candidate_sha = _run(repo, "git", "rev-parse", "HEAD")

            _call(repo, "git", "checkout", "main")
            _call(repo, "git", "merge", "--no-ff", "feat/candidate", "-m", "merge: governed agent effect")
            result_sha = _run(repo, "git", "rev-parse", "HEAD")

            self._event("git.merge", "ALLOW", f"base={base_sha[:12]} candidate={candidate_sha[:12]} -> {result_sha[:12]}")

            return {
                "merged": True,
                "decision": receipt,
                "result_sha": result_sha,
                "base_sha": base_sha,
                "candidate_sha": candidate_sha,
            }

    def verify_independently(self, *, result_sha: str, now: datetime | None = None) -> dict:
        """Claim verification only through the bound Sentinel source.

        The agent cannot self-verify: resolve_action gates verify:exact-subject
        on the Sentinel binding and the exact subject SHA. Without a bound
        grant the claim is DENY and no verdict is produced.
        """
        receipt = resolve_action(
            grant=self.grant,
            requested_capability="verify:exact-subject",
            requested_subject_sha=result_sha,
            now=now,
        )
        self._event(
            "verification.claim",
            receipt["decision"],
            f"subject={result_sha[:12]} via {self.grant.get('authority_source', {}).get('owner', 'unknown')}",
        )
        return receipt

    def accept_mission(self, *, merged: bool, verdict: dict) -> bool:
        """Acceptance requires both a completed governed effect and an external verdict."""
        verified = verdict.get("decision") == "ALLOW"
        accepted = bool(merged and verified)
        self._event(
            "mission.acceptance",
            "ACCEPTED" if accepted else "REJECTED",
            f"merged={merged} externally_verified={verified}",
        )
        return accepted

    def evidence_bundle(self) -> str:
        return json.dumps(
            {
                "agent_persona": self.persona_id,
                "grant_id": self.grant.get("grant_id", ""),
                "grant_state": None,
                "trace": [asdict(e) for e in self._trace],
            },
            indent=2,
        )


def governed_agent_run(*, persona_id: str, grant: dict, now: datetime | None = None) -> dict:
    """One full governed attempt: resolve -> effect -> verify -> accept, with trace."""
    agent = GovernedAgent(persona_id=persona_id, grant=grant)
    merge_receipt = agent.attempt_merge(now=now)
    verdict = (
        agent.verify_independently(result_sha=merge_receipt["result_sha"], now=now)
        if merge_receipt["merged"]
        else {"decision": "DENY", "reason": "no_effect_to_verify"}
    )
    accepted = agent.accept_mission(merged=merge_receipt["merged"], verdict=verdict)
    bundle = json.loads(agent.evidence_bundle())
    bundle["grant_state"] = grant_state(grant, now=now)
    bundle["outcome"] = {
        "merged": merge_receipt["merged"],
        "verdict_decision": verdict.get("decision"),
        "accepted": accepted,
    }
    return bundle
