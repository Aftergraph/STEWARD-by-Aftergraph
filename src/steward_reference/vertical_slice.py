from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import subprocess
import tempfile
import time
import uuid


def _call(cwd: Path, *args: str) -> None:
    subprocess.check_call(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


@dataclass(frozen=True)
class TraceEvent:
    seq: int
    kind: str
    subject: str
    detail: str


@dataclass(frozen=True)
class ReferenceVerdict:
    subject_sha: str
    verdict: str
    verifier: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class VerticalSliceResult:
    mission_id: str
    work_id: str
    base_sha: str
    candidate_sha: str
    verifier_sha: str
    tests_passed: bool
    verification: ReferenceVerdict
    mission_accepted: bool
    trace: tuple[TraceEvent, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class ReferenceVerticalSlice:
    """Executable P1 semantics using real Git/worktrees and deterministic tests.

    This proves local STEWARD contract behavior only. Production authority,
    durable WORKS state, Runtime dispatch, Trust Gateway, and Sentinel remain
    external integration gates.
    """

    def __init__(self) -> None:
        self._trace: list[TraceEvent] = []

    def _event(self, kind: str, subject: str, detail: str) -> None:
        self._trace.append(TraceEvent(len(self._trace) + 1, kind, subject, detail))

    def run(self) -> VerticalSliceResult:
        mission_id = f"mission-{uuid.uuid4().hex[:12]}"
        work_id = f"work-{uuid.uuid4().hex[:12]}"
        self._event("mission.created", mission_id, "acceptance: deterministic unit test passes at exact commit")
        self._event("work.created", work_id, "one coding node")

        with tempfile.TemporaryDirectory(prefix="steward-p1-") as td:
            root = Path(td)
            repo = root / "repo"
            builder = root / "wt-builder"
            verifier = root / "wt-verifier"
            repo.mkdir()

            _call(repo, "git", "init", "-b", "main")
            _call(repo, "git", "config", "user.name", "Steward Reference")
            _call(repo, "git", "config", "user.email", "reference@aftergraph.org")
            (repo / "mathlib.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
            (repo / "test_mathlib.py").write_text(
                "import unittest\nfrom mathlib import add\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_add(self): self.assertEqual(add(2, 3), 5)\n\n"
                "if __name__ == '__main__': unittest.main()\n",
                encoding="utf-8",
            )
            _call(repo, "git", "add", ".")
            _call(repo, "git", "commit", "-m", "seed failing subject")
            base_sha = _run(repo, "git", "rev-parse", "HEAD")
            self._event("git.baseline", base_sha, "exact base SHA recorded")

            _call(repo, "git", "worktree", "add", "-b", "feat/fix-add", str(builder), base_sha)
            self._event("worktree.provisioned", str(builder), f"isolated builder worktree from {base_sha}")

            before = subprocess.run(
                ["python3", "-m", "unittest", "-q"], cwd=builder, capture_output=True, text=True
            )
            if before.returncode == 0:
                raise AssertionError("Reference baseline unexpectedly passed; proof subject is invalid")
            self._event("test.failed", base_sha, "baseline reproduces defect")

            (builder / "mathlib.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            self._event("code.mutated", work_id, "bounded fix applied in isolated worktree")
            after = subprocess.run(
                ["python3", "-m", "unittest", "-q"], cwd=builder, capture_output=True, text=True
            )
            tests_passed = after.returncode == 0
            if not tests_passed:
                raise AssertionError(after.stdout + after.stderr)
            self._event("test.passed", work_id, "deterministic local test passed")

            _call(builder, "git", "add", "mathlib.py")
            _call(builder, "git", "commit", "-m", "fix: correct add implementation")
            candidate_sha = _run(builder, "git", "rev-parse", "HEAD")
            self._event("git.commit", candidate_sha, "candidate exact subject created")

            _call(repo, "git", "worktree", "add", "--detach", str(verifier), candidate_sha)
            verifier_sha = _run(verifier, "git", "rev-parse", "HEAD")
            if verifier_sha != candidate_sha:
                raise AssertionError("Verifier worktree is not pinned to candidate exact SHA")
            self._event("verification.worktree", verifier_sha, "fresh detached exact-subject worktree")

            independent = subprocess.run(
                ["python3", "-m", "unittest", "-q"], cwd=verifier, capture_output=True, text=True
            )
            verdict = ReferenceVerdict(
                subject_sha=verifier_sha,
                verdict="PASS" if independent.returncode == 0 else "FAIL",
                verifier="reference-exact-head-verifier",
                evidence=("python-unittest", "fresh-detached-worktree"),
            )
            self._event("verification.verdict", verifier_sha, verdict.verdict)

            mission_accepted = tests_passed and verdict.verdict == "PASS" and verdict.subject_sha == candidate_sha
            self._event(
                "mission.acceptance",
                mission_id,
                "ACCEPTED" if mission_accepted else "REJECTED",
            )
            if not mission_accepted:
                raise AssertionError("Mission acceptance occurred without exact-subject verification")

            return VerticalSliceResult(
                mission_id=mission_id,
                work_id=work_id,
                base_sha=base_sha,
                candidate_sha=candidate_sha,
                verifier_sha=verifier_sha,
                tests_passed=tests_passed,
                verification=verdict,
                mission_accepted=mission_accepted,
                trace=tuple(self._trace),
            )
