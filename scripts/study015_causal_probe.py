#!/usr/bin/env python3
"""STUDY-015 causal composition probe for STEWARD Golden Mission.

Local-only composition contract probe. It executes the real STEWARD ports and
GoldenMissionCoordinator against deterministic transports, binds the proof to
the exact component-probe bundle, and exercises hostile seam mutations.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.p2_golden_mission import (  # noqa: E402
    GoldenMissionCoordinator,
    GoldenMissionNeedsApproval,
    GoldenMissionRequest,
)
from steward.ports import (  # noqa: E402
    GitSubjectPort,
    RuntimeDispatchV2Request,
    RuntimeSubjectBindingPort,
    RuntimeV2Port,
    SentinelPort,
    TrustGatewayClient,
)

COMPONENT_PROBE_ROOT = "e9b5e00ca523a5c294406bf2c871630e75d150f65953561092ccb8ef52fd55d7"
COMPONENT_HEADS = {
    "aie": "c340d7a3fcf23a84b03ba493ca8fc938ea581db6",
    "trust-gateway": "0b4030751d04f1b31bc2cc8d4a5e584729e9be02",
    "works-execution": "be0295155ac3ba357e4a60ece15eee1387847def",
    "runtime": "7dc0a336e06e7528f471bbd5676ddb50df6e9046",
    "sentinel": "4125f66b0c6d476966feb017ec7ddf3e22ec9459",
}

WORK = "wrk_" + "1" * 32
ORG = "org_" + "2" * 32
TENANT = "ten_" + "3" * 32
PRINCIPAL = "prn_" + "4" * 32
AUTH = "auth_" + "5" * 32
LEASE = "lse_" + "6" * 32
PDR = "pdr_" + "7" * 32
CTX = "ctx_" + "8" * 32
TRACE = "trc_" + "9" * 32
WORKER = "wrkr_" + "a" * 32
ACTION = "act_" + "b" * 32
BASE = "c" * 40
CANDIDATE = "d" * 40
MISSION = "mis_study015_causal"
ATTEMPT = "attempt/study015/1"
EFFECT = "effect/study015/1"
CAUSAL = "causal/study015/1"
WEXEC = "wexec/study015/1"
RDISP = "rdisp/study015/1"


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


class RuntimeTransport:
    def dispatch(self, payload):
        return {
            "runtimeDispatchId": RDISP,
            "worksExecutionId": WEXEC,
            "workId": WORK,
            "executionContextId": CTX,
            "traceId": TRACE,
            "workerId": WORKER,
        }


class SubjectTransport:
    def __init__(self, *, causal_override=None):
        self.calls = []
        self.causal_override = causal_override

    def dispatch(self, payload):
        self.calls.append(payload)
        return {
            **payload,
            **(
                {"causalId": self.causal_override}
                if self.causal_override is not None
                else {}
            ),
            "boundAt": "2026-09-25T01:30:00Z",
        }


class GitTransport:
    def __init__(self):
        self.capture_calls = 0

    def prepare_worktree(self, payload):
        return {
            **payload,
            "worktreeRef": "wt/study015/1",
            "isolated": True,
            "clean": True,
        }

    def capture_candidate(self, worktree_ref):
        self.capture_calls += 1
        return {
            "repository": "Aftergraph/STEWARD-by-Aftergraph",
            "workId": WORK,
            "attemptId": ATTEMPT,
            "worktreeRef": worktree_ref,
            "baseSha": BASE,
            "candidateSha": CANDIDATE,
            "branchRef": "research/study015-causal-composition-v1",
        }


class SentinelTransport:
    def __init__(self, *, head=CANDIDATE, verdict="SHIP"):
        self.head = head
        self.verdict = verdict

    def verify_exact_head(self, payload):
        return {
            "repository": payload["repository"],
            "headSha": self.head,
            "verdict": self.verdict,
            "verdictRef": "sentinel:study015/1",
            "evidenceRefs": ["evidence:study015/sentinel/1"],
        }


def dispatch_request():
    return RuntimeDispatchV2Request(
        work_id=WORK,
        organization_id=ORG,
        tenant_id=TENANT,
        principal_id=PRINCIPAL,
        mission_id=MISSION,
        authority_lease_id=AUTH,
        worker_lease_id=LEASE,
        admission_decision_id=PDR,
        attempt_id=ATTEMPT,
        effect_id=EFFECT,
        idempotency_key="idem/study015/1",
        budget_ref="budget/study015/1",
        budget_ceiling=100,
        checkpoint_id="checkpoint/study015/1",
        evidence_root="evidence/study015/root",
        causal_id=CAUSAL,
    )


def mission_request():
    return GoldenMissionRequest(
        dispatch=dispatch_request(),
        repository="Aftergraph/STEWARD-by-Aftergraph",
        base_sha=BASE,
        action_id=ACTION,
        tool="git.apply_patch",
        tool_args={"bounded": True},
        branch_ref="research/study015-causal-composition-v1",
        pull_request=0 if False else None,
    )


def response(payload, status=200):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(payload).encode()

    out = Response()
    out.status = status
    return out


def coordinator(*, git=None, sentinel=None, subject=None):
    git = git or GitTransport()
    subject = subject or SubjectTransport()
    return (
        GoldenMissionCoordinator(
            RuntimeV2Port(RuntimeTransport()),
            TrustGatewayClient("https://tg.invalid", "local-probe-token"),
            GitSubjectPort(git),
            RuntimeSubjectBindingPort(subject),
            SentinelPort(sentinel or SentinelTransport()),
        ),
        git,
        subject,
    )


def allowed_tg(*, admission=PDR):
    return {
        "decision": "allow",
        "execution_context_id": CTX,
        "execution_pdr_id": "pdr_" + "e" * 32,
        "admission_decision_id": admission,
        "result": {"effect": "applied"},
    }


def run_probe():
    coord, git, subject = coordinator()
    with patch(
        "steward.ports.trust_gateway.urlopen",
        return_value=response(allowed_tg()),
    ):
        outcome = coord.execute(mission_request())

    if not outcome.accepted:
        raise RuntimeError("happy causal chain was not accepted")
    exact_subject = f"git:Aftergraph/STEWARD-by-Aftergraph@{CANDIDATE}"
    if outcome.action.execution_context_id != outcome.runtime.execution_context_id:
        raise RuntimeError("TG execution_context_id diverged from Runtime")
    if outcome.action.admission_decision_id != PDR:
        raise RuntimeError("TG admission_decision_id diverged from Mission")
    if outcome.subject_binding.causal_id != CAUSAL:
        raise RuntimeError("post-effect subject binding changed causal_id")
    if outcome.subject_binding.works_execution_id != WEXEC:
        raise RuntimeError("post-effect subject binding changed works_execution_id")
    if outcome.subject_binding.effect_id != EFFECT:
        raise RuntimeError("post-effect subject binding changed effect_id")
    if outcome.subject_binding.subject != exact_subject:
        raise RuntimeError("post-effect exact subject diverged")
    if outcome.verification.head_sha != CANDIDATE:
        raise RuntimeError("Sentinel verification rebound exact head")

    rebound_admission_rejected = False
    coord2, _, _ = coordinator()
    with patch(
        "steward.ports.trust_gateway.urlopen",
        return_value=response(allowed_tg(admission="pdr_" + "f" * 32)),
    ):
        try:
            coord2.execute(mission_request())
        except RuntimeError as exc:
            rebound_admission_rejected = "rebound admission_decision_id" in str(exc)
    if not rebound_admission_rejected:
        raise RuntimeError("admission decision rebound was not rejected")

    stale_verification_rejected = False
    coord3, _, _ = coordinator(sentinel=SentinelTransport(head="f" * 40))
    with patch(
        "steward.ports.trust_gateway.urlopen",
        return_value=response(allowed_tg()),
    ):
        try:
            coord3.execute(mission_request())
        except RuntimeError as exc:
            stale_verification_rejected = "different Git subject" in str(exc)
    if not stale_verification_rejected:
        raise RuntimeError("stale verifier subject was not rejected")

    approval_git = GitTransport()
    coord4, approval_git, approval_subject = coordinator(git=approval_git)
    approval_payload = {
        "decision": "needs_approval",
        "approvalId": "approval/study015/1",
        "reason": "operator required",
    }
    with patch(
        "steward.ports.trust_gateway.urlopen",
        return_value=response(approval_payload, 202),
    ):
        waiting = coord4.execute(mission_request())
    approval_stops_before_capture = (
        isinstance(waiting, GoldenMissionNeedsApproval)
        and approval_git.capture_calls == 0
        and approval_subject.calls == []
    )
    if not approval_stops_before_capture:
        raise RuntimeError("approval boundary did not stop before subject capture")

    return {
        "schema": "study015.causal-composition/1.0",
        "component": "steward-composition",
        "source_head": git_head(),
        "execution_class": "LOCAL_COMPOSITION_CONTRACT_PROBE",
        "network_used": False,
        "component_probe_root_sha256": COMPONENT_PROBE_ROOT,
        "component_heads": COMPONENT_HEADS,
        "identity": {
            "mission_id": MISSION,
            "work_id": WORK,
            "admission_decision_id": PDR,
            "execution_context_id": CTX,
            "trace_id": TRACE,
            "works_execution_id": WEXEC,
            "attempt_id": ATTEMPT,
            "effect_id": EFFECT,
            "causal_id": CAUSAL,
            "exact_subject": exact_subject,
            "verification_head_sha": CANDIDATE,
        },
        "seams": {
            "runtime_work_bound": outcome.runtime.work_id == WORK,
            "tg_execution_context_bound": (
                outcome.action.execution_context_id
                == outcome.runtime.execution_context_id
            ),
            "tg_admission_decision_bound": (
                outcome.action.admission_decision_id == PDR
            ),
            "candidate_work_attempt_bound": (
                outcome.candidate.work_id == WORK
                and outcome.candidate.attempt_id == ATTEMPT
            ),
            "post_effect_causal_subject_bound": (
                outcome.subject_binding.works_execution_id == WEXEC
                and outcome.subject_binding.effect_id == EFFECT
                and outcome.subject_binding.causal_id == CAUSAL
                and outcome.subject_binding.subject == exact_subject
            ),
            "sentinel_exact_head_bound": (
                outcome.verification.head_sha == CANDIDATE
            ),
            "mission_accepted": outcome.accepted,
        },
        "hostile": {
            "rebound_admission_rejected": rebound_admission_rejected,
            "stale_verification_rejected": stale_verification_rejected,
            "approval_stops_before_capture": approval_stops_before_capture,
        },
    }


def main():
    print(json.dumps(run_probe(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
