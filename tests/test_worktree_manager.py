from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.habitat.worktrees import (
    GitWorktreeManager,
    WorktreeContractError,
    WorktreeDirtyError,
    WorktreeSpec,
)


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return r.stdout.strip()


class Repository:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Steward Test")
        git(self.root, "config", "user.email", "steward@example.invalid")
        (self.root / "value.txt").write_text("base\n")
        git(self.root, "add", "value.txt")
        git(self.root, "commit", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


class WorktreeManagerTests(unittest.TestCase):
    def test_provisions_detached_worktree_at_exact_base(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt-a"
            binding = GitWorktreeManager().provision(
                WorktreeSpec(str(r.root), str(target), r.base, "wrk_1", "att_1")
            )
            self.assertEqual(r.base, binding.current_head)
            self.assertIsNone(binding.branch_name)
            self.assertFalse(binding.dirty)
            self.assertEqual("base\n", (target / "value.txt").read_text())

    def test_named_branch_is_bound_to_exact_base(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt-branch"
            binding = GitWorktreeManager().provision(
                WorktreeSpec(
                    str(r.root),
                    str(target),
                    r.base,
                    "wrk_1",
                    "att_1",
                    branch_name="steward/work-1",
                )
            )
            self.assertEqual("steward/work-1", binding.branch_name)
            self.assertEqual(r.base, binding.current_head)

    def test_two_worktrees_isolate_mutation(self):
        with Repository() as r:
            manager = GitWorktreeManager()
            a = Path(r.tmp.name) / "wt-a"
            b = Path(r.tmp.name) / "wt-b"
            ba = manager.provision(WorktreeSpec(str(r.root), str(a), r.base, "wrk_a", "att_a"))
            bb = manager.provision(WorktreeSpec(str(r.root), str(b), r.base, "wrk_b", "att_b"))
            (a / "value.txt").write_text("changed only in a\n")
            self.assertEqual("base\n", (b / "value.txt").read_text())
            self.assertTrue(manager.inspect(
                repository_path=ba.repository_path,
                worktree_path=ba.worktree_path,
                base_commit=ba.base_commit,
                work_id=ba.work_id,
                attempt_id=ba.attempt_id,
            ).dirty)
            self.assertFalse(manager.inspect(
                repository_path=bb.repository_path,
                worktree_path=bb.worktree_path,
                base_commit=bb.base_commit,
                work_id=bb.work_id,
                attempt_id=bb.attempt_id,
            ).dirty)

    def test_invalid_exact_sha_fails_before_provision(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt"
            with self.assertRaises(WorktreeContractError):
                GitWorktreeManager().provision(
                    WorktreeSpec(str(r.root), str(target), "main", "wrk", "att")
                )
            self.assertFalse(target.exists())

    def test_unknown_exact_sha_fails_before_target_creation(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt"
            with self.assertRaises(WorktreeContractError):
                GitWorktreeManager().provision(
                    WorktreeSpec(str(r.root), str(target), "f" * 40, "wrk", "att")
                )
            self.assertFalse(target.exists())

    def test_release_refuses_dirty_worktree_without_force(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt"
            manager = GitWorktreeManager()
            binding = manager.provision(
                WorktreeSpec(str(r.root), str(target), r.base, "wrk", "att")
            )
            (target / "new.txt").write_text("unpersisted\n")
            with self.assertRaises(WorktreeDirtyError):
                manager.release(binding)
            self.assertTrue(target.exists())
            manager.release(binding, force=True)
            self.assertFalse(target.exists())

    def test_clean_release_removes_worktree(self):
        with Repository() as r:
            target = Path(r.tmp.name) / "wt"
            manager = GitWorktreeManager()
            binding = manager.provision(
                WorktreeSpec(str(r.root), str(target), r.base, "wrk", "att")
            )
            manager.release(binding)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
