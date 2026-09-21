"""Git worktree isolation primitive for STEWARD Habitat coding work.

This module owns local workspace isolation only.  It does not own Work,
authority, repository truth, merge authority, or verification.  The returned
binding is intended to be correlated into canonical WORKS execution state.

No shell is used and no network operation is performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Sequence


_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class WorktreeError(RuntimeError):
    """Base class for Habitat worktree failures."""


class WorktreeContractError(WorktreeError):
    """Requested worktree binding is invalid."""


class WorktreeDirtyError(WorktreeError):
    """A worktree cannot be released without explicit force while dirty."""


@dataclass(frozen=True)
class WorktreeSpec:
    repository_path: str
    target_path: str
    base_commit: str
    work_id: str
    attempt_id: str
    branch_name: str | None = None

    def validate(self) -> None:
        if not _SHA_RE.fullmatch(self.base_commit):
            raise WorktreeContractError("base_commit must be an exact 40-hex commit SHA")
        if not self.work_id.strip() or not self.attempt_id.strip():
            raise WorktreeContractError("work_id and attempt_id are required")
        repo = Path(self.repository_path).expanduser().resolve()
        target = Path(self.target_path).expanduser().resolve()
        if repo == target:
            raise WorktreeContractError("target_path cannot be the repository root")
        if target.exists():
            raise WorktreeContractError("target_path already exists")


@dataclass(frozen=True)
class WorktreeBinding:
    repository_path: str
    worktree_path: str
    base_commit: str
    current_head: str
    work_id: str
    attempt_id: str
    branch_name: str | None
    dirty: bool


class GitWorktreeManager:
    """Provision/inspect/release isolated local Git worktrees."""

    def provision(self, spec: WorktreeSpec) -> WorktreeBinding:
        spec.validate()
        repo = Path(spec.repository_path).expanduser().resolve()
        target = Path(spec.target_path).expanduser().resolve()

        root = self._git(repo, "rev-parse", "--show-toplevel").strip()
        if Path(root).resolve() != repo:
            raise WorktreeContractError("repository_path must be the Git worktree root")

        resolved = self._git(repo, "rev-parse", "--verify", f"{spec.base_commit}^{{commit}}").strip()
        if resolved.lower() != spec.base_commit.lower():
            raise WorktreeContractError("base_commit did not resolve to the exact requested commit")

        target.parent.mkdir(parents=True, exist_ok=True)
        args: list[str] = ["worktree", "add"]
        if spec.branch_name is None:
            args += ["--detach", str(target), spec.base_commit]
        else:
            self._git(repo, "check-ref-format", "--branch", spec.branch_name)
            args += ["-b", spec.branch_name, str(target), spec.base_commit]
        self._git(repo, *args)

        binding = self.inspect(
            repository_path=str(repo),
            worktree_path=str(target),
            base_commit=spec.base_commit,
            work_id=spec.work_id,
            attempt_id=spec.attempt_id,
        )
        if binding.current_head.lower() != spec.base_commit.lower():
            # Fail closed and clean up the newly provisioned path.
            self._git(repo, "worktree", "remove", "--force", str(target))
            raise WorktreeContractError("provisioned worktree HEAD does not equal exact base_commit")
        if spec.branch_name != binding.branch_name:
            self._git(repo, "worktree", "remove", "--force", str(target))
            raise WorktreeContractError("provisioned worktree branch does not match requested branch")
        return binding

    def inspect(
        self,
        *,
        repository_path: str,
        worktree_path: str,
        base_commit: str,
        work_id: str,
        attempt_id: str,
    ) -> WorktreeBinding:
        repo = Path(repository_path).expanduser().resolve()
        wt = Path(worktree_path).expanduser().resolve()
        if not wt.is_dir():
            raise WorktreeContractError("worktree_path does not exist")
        head = self._git(wt, "rev-parse", "HEAD").strip()
        if not _SHA_RE.fullmatch(head):
            raise WorktreeContractError("worktree returned malformed HEAD")
        branch = self._git_optional(wt, "symbolic-ref", "--short", "-q", "HEAD")
        status = self._git(wt, "status", "--porcelain=v1", "--untracked-files=all")
        return WorktreeBinding(
            repository_path=str(repo),
            worktree_path=str(wt),
            base_commit=base_commit.lower(),
            current_head=head.lower(),
            work_id=work_id,
            attempt_id=attempt_id,
            branch_name=branch.strip() if branch else None,
            dirty=bool(status.strip()),
        )

    def release(self, binding: WorktreeBinding, *, force: bool = False) -> None:
        inspected = self.inspect(
            repository_path=binding.repository_path,
            worktree_path=binding.worktree_path,
            base_commit=binding.base_commit,
            work_id=binding.work_id,
            attempt_id=binding.attempt_id,
        )
        if inspected.dirty and not force:
            raise WorktreeDirtyError("refusing to remove dirty worktree without force")
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(binding.worktree_path)
        self._git(Path(binding.repository_path), *args)
        self._git(Path(binding.repository_path), "worktree", "prune")

    @staticmethod
    def _git(cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
            raise WorktreeContractError(detail)
        return completed.stdout

    @staticmethod
    def _git_optional(cwd: Path, *args: str) -> str | None:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout
        if completed.returncode == 1:
            return None
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise WorktreeContractError(detail)
