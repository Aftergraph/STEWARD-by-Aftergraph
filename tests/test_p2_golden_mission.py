import json
import unittest
from unittest.mock import patch

from steward.p2_golden_mission import (
    GoldenMissionCoordinator,
    GoldenMissionNeedsApproval,
    GoldenMissionRequest,
)
from steward.ports import (
    GitSubjectPort,
    GoldenMissionAcceptancePort,
    RuntimeDispatchV2Request,
    RuntimeSubjectBindingPort,
    RuntimeV2Port,
    SentinelPort,
    TrustGatewayClient,
)


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


class RuntimeTransport:
    def dispatch(self, payload):
        return {
            "runtimeDispatchId": "rdisp/1",
            "worksExecutionId": "wexec/1",
            "workId": WORK,
            "executionContextId": CTX,
            "traceId": TRACE,
            "workerId": WORKER,
        }


class SubjectTransport:
    def __init__(self):
        self.calls = []

    def dispatch(self, payload):
        self.calls.append(payload)
        return {**payload, "boundAt": "2026-09-21T08:00:00Z"}


class GitTransport:
    def __init__(self):
        self.capture_calls = 0

    def prepare_worktree(self, payload):
        return {
            **payload,
            "worktreeRef": "wt/p2/1",
            "isolated": True,
            "clean": True,
        }

    def capture_candidate(self, worktree_ref):
        self.capture_calls += 1
        return {
            "repository": "Aftergraph/STEWARD-by-Aftergraph",
            "workId": WORK,
            "attemptId": "attempt/1",
            "worktreeRef": worktree_ref,
            "baseSha": BASE,
            "candidateSha": CANDIDATE,
            "branchRef": "steward/p2-proof",
        }


class AcceptanceTransport:
    def __init__(self, decision="accept", mutate=None):
        self.decision = decision
        self.mutate = mutate
        self.calls = []

    def evaluate(self, payload):
        self.calls.append(payload)
        verification = payload["verification"]
        out = {
            "decision": self.decision,
            "reason": (
                "GOLDEN-001: independently verified"
                if self.decision == "accept"
                else "VERIFIER-FAILURE: rejected"
            ),
            "pin": "sha256:" + "1" * 64,
            "subject_ref": verification["subject_ref"],
            "action_id": verification["action_id"],
            "action_decision_id": verification["action_decision_id"],
        }
        if self.mutate:
            self.mutate(out)
        return out


class SentinelTransport:
    def __init__(self, verdict="SHIP", head=CANDIDATE):
        self.verdict = verdict
        self.head = head

    def verify_exact_head(self, payload):
        return {
            "repository": payload["repository"],
            "headSha": self.head,
            "verdict": self.verdict,
            "verdictRef": "sentinel:receipt/1",
            "evidenceRefs": ["evidence:sentinel/1"],
        }


def dispatch_request():
    return RuntimeDispatchV2Request(
        work_id=WORK,
        organization_id=ORG,
        tenant_id=TENANT,
        principal_id=PRINCIPAL,
        mission_id="mis_p2_golden",
        authority_lease_id=AUTH,
        worker_lease_id=LEASE,
        admission_decision_id=PDR,
        attempt_id="attempt/1",
        effect_id="effect/1",
        idempotency_key="idem/p2/1",
        budget_ref="budget/1",
        budget_ceiling=100,
        checkpoint_id="checkpoint/1",
        evidence_root="evidence/1",
        causal_id="causal/1",
    )


def request():
    return GoldenMissionRequest(
        dispatch=dispatch_request(),
        repository="Aftergraph/STEWARD-by-Aftergraph",
        base_sha=BASE,
        action_id=ACTION,
        tool="git.apply_patch",
        tool_args={"bounded": True},
        branch_ref="steward/p2-proof",
        pull_request=8,
    )


def response(payload, status=200):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return json.dumps(payload).encode()
    out = Response()
    out.status = status
    return out


class GoldenMissionTests(unittest.TestCase):
    def coordinator(self, git=None, sentinel=None, acceptance=None):
        subject = SubjectTransport()
        git = git or GitTransport()
        acceptance = acceptance or AcceptanceTransport()
        return (
            GoldenMissionCoordinator(
                RuntimeV2Port(RuntimeTransport()),
                TrustGatewayClient("https://tg.example", "token"),
                GitSubjectPort(git),
                RuntimeSubjectBindingPort(subject),
                SentinelPort(sentinel or SentinelTransport()),
                GoldenMissionAcceptancePort(
                    acceptance,
                    verifier_principal="prn_" + "e" * 32,
                ),
            ),
            git,
            subject,
            acceptance,
        )

    def test_accepts_only_composed_current_exact_subject_ship(self):
        coordinator, _, subject, acceptance = self.coordinator()
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
            "result": {"effect": "applied"},
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            outcome = coordinator.execute(request())
        self.assertTrue(outcome.accepted)
        self.assertEqual(f"git:Aftergraph/STEWARD-by-Aftergraph@{CANDIDATE}", outcome.subject_binding.subject)
        self.assertEqual(1, len(subject.calls))
        self.assertEqual(1, len(acceptance.calls))
        self.assertEqual("accept", outcome.acceptance.decision)

    def test_approval_stops_before_effect_subject_and_sentinel(self):
        coordinator, git, subject, acceptance = self.coordinator()
        tg = {"decision": "needs_approval", "approvalId": "approval/1"}
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg, 202)):
            outcome = coordinator.execute(request())
        self.assertIsInstance(outcome, GoldenMissionNeedsApproval)
        self.assertEqual(0, git.capture_calls)
        self.assertEqual([], subject.calls)
        self.assertEqual([], acceptance.calls)

    def test_non_ship_verdict_never_accepts_mission(self):
        coordinator, _, _, acceptance = self.coordinator(sentinel=SentinelTransport("DO_NOT_SHIP"))
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            outcome = coordinator.execute(request())
        self.assertFalse(outcome.accepted)
        self.assertEqual("reject", acceptance.calls[0]["verification"]["verdict"])

    def test_owner_reject_overrides_sentinel_ship(self):
        acceptance = AcceptanceTransport(decision="reject")
        coordinator, _, _, _ = self.coordinator(acceptance=acceptance)
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            outcome = coordinator.execute(request())
        self.assertFalse(outcome.accepted)
        self.assertEqual("SHIP", outcome.verification.verdict)
        self.assertEqual("reject", outcome.acceptance.decision)

    def test_owner_subject_rebind_fails_closed(self):
        def mutate(out):
            out["subject_ref"] = "git:Aftergraph/STEWARD-by-Aftergraph@" + "f" * 40
        coordinator, _, _, _ = self.coordinator(
            acceptance=AcceptanceTransport(mutate=mutate)
        )
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            with self.assertRaisesRegex(RuntimeError, "rebound verification subject"):
                coordinator.execute(request())

    def test_owner_action_rebind_fails_closed(self):
        def mutate(out):
            out["action_id"] = "act_" + "f" * 32
        coordinator, _, _, _ = self.coordinator(
            acceptance=AcceptanceTransport(mutate=mutate)
        )
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            with self.assertRaisesRegex(RuntimeError, "rebound action"):
                coordinator.execute(request())

    def test_tg_admission_decision_rebind_fails_closed_before_acceptance(self):
        coordinator, _, _, acceptance = self.coordinator()
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": "pdr_" + "f" * 32,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            with self.assertRaisesRegex(RuntimeError, "admission decision"):
                coordinator.execute(request())
        self.assertEqual([], acceptance.calls)

    def test_stale_sentinel_subject_fails_closed(self):
        coordinator, _, _, acceptance = self.coordinator(sentinel=SentinelTransport(head="f" * 40))
        tg = {
            "decision": "allow",
            "execution_context_id": CTX,
            "execution_pdr_id": "pdr_" + "e" * 32,
            "admission_decision_id": PDR,
        }
        with patch("steward.ports.trust_gateway.urlopen", return_value=response(tg)):
            with self.assertRaisesRegex(RuntimeError, "different Git subject"):
                coordinator.execute(request())
        self.assertEqual([], acceptance.calls)


if __name__ == "__main__":
    unittest.main()
