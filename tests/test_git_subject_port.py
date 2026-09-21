from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.git_subject import (
    GitSubjectContractError,
    GitSubjectPort,
    GitSubjectUnavailableError,
    GitWorktreeRequest,
)

BASE = "a" * 40
CANDIDATE = "b" * 40


class FakeTransport:
    def __init__(self, prepared=None, candidate=None, error=None):
        self.prepared = prepared
        self.candidate = candidate
        self.error = error
        self.prepare_calls = []
        self.capture_calls = []

    def prepare_worktree(self, payload):
        self.prepare_calls.append(dict(payload))
        if self.error is not None:
            raise self.error
        return self.prepared

    def capture_candidate(self, worktree_ref):
        self.capture_calls.append(worktree_ref)
        if self.error is not None:
            raise self.error
        return self.candidate


def request():
    return GitWorktreeRequest(
        repository="Aftergraph/STEWARD-by-Aftergraph",
        work_id="wrk_01",
        attempt_id="att_01",
        base_sha=BASE,
        branch_ref="steward/p2-example",
    )


def prepared(**overrides):
    base = {
        "repository": "Aftergraph/STEWARD-by-Aftergraph",
        "workId": "wrk_01",
        "attemptId": "att_01",
        "baseSha": BASE,
        "worktreeRef": "wt://wrk_01/att_01",
        "branchRef": "steward/p2-example",
        "isolated": True,
        "clean": True,
    }
    return base | overrides


def candidate(**overrides):
    base = {
        "repository": "Aftergraph/STEWARD-by-Aftergraph",
        "workId": "wrk_01",
        "attemptId": "att_01",
        "worktreeRef": "wt://wrk_01/att_01",
        "baseSha": BASE,
        "candidateSha": CANDIDATE,
        "branchRef": "steward/p2-example",
    }
    return base | overrides


class GitSubjectPortTests(unittest.TestCase):
    def test_clean_isolated_worktree_binds_work_and_attempt(self):
        transport = FakeTransport(prepared=prepared(), candidate=candidate())
        port = GitSubjectPort(transport)
        binding = port.prepare(request())
        subject = port.capture(binding)
        self.assertEqual("wrk_01", binding.work_id)
        self.assertEqual("att_01", binding.attempt_id)
        self.assertEqual(CANDIDATE, subject.verification_subject)
        self.assertTrue(subject.is_current(CANDIDATE))
        self.assertFalse(subject.is_current("c" * 40))

    def test_dirty_worktree_fails_before_candidate_capture(self):
        transport = FakeTransport(prepared=prepared(clean=False), candidate=candidate())
        with self.assertRaises(GitSubjectContractError):
            GitSubjectPort(transport).prepare(request())
        self.assertEqual([], transport.capture_calls)

    def test_non_isolated_workspace_fails_closed(self):
        transport = FakeTransport(prepared=prepared(isolated=False), candidate=candidate())
        with self.assertRaises(GitSubjectContractError):
            GitSubjectPort(transport).prepare(request())

    def test_wrong_attempt_binding_is_rejected(self):
        transport = FakeTransport(prepared=prepared(attemptId="att_other"), candidate=candidate())
        with self.assertRaises(GitSubjectContractError):
            GitSubjectPort(transport).prepare(request())

    def test_candidate_from_other_worktree_is_rejected(self):
        transport = FakeTransport(
            prepared=prepared(),
            candidate=candidate(worktreeRef="wt://other"),
        )
        port = GitSubjectPort(transport)
        binding = port.prepare(request())
        with self.assertRaises(GitSubjectContractError):
            port.capture(binding)

    def test_branch_name_is_never_verification_subject(self):
        transport = FakeTransport(prepared=prepared(), candidate=candidate())
        port = GitSubjectPort(transport)
        subject = port.capture(port.prepare(request()))
        self.assertNotEqual(request().branch_ref, subject.verification_subject)
        self.assertRegex(subject.verification_subject, r"^[0-9a-f]{40}$")

    def test_non_sha_base_fails_before_transport(self):
        transport = FakeTransport(prepared=prepared(), candidate=candidate())
        bad = GitWorktreeRequest(
            repository="Aftergraph/STEWARD-by-Aftergraph",
            work_id="wrk_01",
            attempt_id="att_01",
            base_sha="main",
        )
        with self.assertRaises(GitSubjectContractError):
            GitSubjectPort(transport).prepare(bad)
        self.assertEqual([], transport.prepare_calls)

    def test_provider_failure_has_no_unisolated_fallback(self):
        transport = FakeTransport(error=OSError("sandbox unavailable"))
        with self.assertRaises(GitSubjectUnavailableError):
            GitSubjectPort(transport).prepare(request())
        self.assertEqual(1, len(transport.prepare_calls))


if __name__ == "__main__":
    unittest.main()
