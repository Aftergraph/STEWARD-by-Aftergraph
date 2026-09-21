"""Exact-subject Git/worktree composition port for STEWARD P2.

This module does not become the worktree implementation owner. It validates the
binding STEWARD requires from a Habitat/worker sandbox provider:

    Work + Attempt + repository + exact base SHA
        -> isolated clean worktree
        -> candidate exact SHA
        -> immutable verification subject

A branch name is navigation only and is never accepted as a verification
subject.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol


_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class GitSubjectError(RuntimeError):
    """Base class for Git subject/worktree failures."""


class GitSubjectContractError(GitSubjectError):
    """Worktree/candidate response violates the STEWARD binding contract."""


class GitSubjectUnavailableError(GitSubjectError):
    """The selected Habitat/worktree provider is unavailable."""


@dataclass(frozen=True)
class GitWorktreeRequest:
    repository: str
    work_id: str
    attempt_id: str
    base_sha: str
    branch_ref: str | None = None

    def to_wire(self) -> dict[str, Any]:
        if not isinstance(self.repository, str) or "/" not in self.repository:
            raise GitSubjectContractError("repository must be owner/name")
        if not isinstance(self.work_id, str) or not self.work_id.strip():
            raise GitSubjectContractError("work_id is required")
        if not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
            raise GitSubjectContractError("attempt_id is required")
        if not isinstance(self.base_sha, str) or not _SHA_RE.fullmatch(self.base_sha):
            raise GitSubjectContractError("base_sha must be an exact 40-hex commit")
        if self.branch_ref is not None and not self.branch_ref.strip():
            raise GitSubjectContractError("branch_ref cannot be empty")
        return {
            "repository": self.repository,
            "workId": self.work_id,
            "attemptId": self.attempt_id,
            "baseSha": self.base_sha.lower(),
            **({"branchRef": self.branch_ref} if self.branch_ref is not None else {}),
        }


@dataclass(frozen=True)
class GitWorktreeBinding:
    repository: str
    work_id: str
    attempt_id: str
    base_sha: str
    worktree_ref: str
    branch_ref: str | None
    isolated: bool
    clean: bool

    @classmethod
    def from_wire(
        cls,
        request: GitWorktreeRequest,
        payload: Mapping[str, Any],
    ) -> "GitWorktreeBinding":
        repository = payload.get("repository")
        work_id = payload.get("workId")
        attempt_id = payload.get("attemptId")
        base_sha = payload.get("baseSha")
        worktree_ref = payload.get("worktreeRef")
        branch_ref = payload.get("branchRef")
        isolated = payload.get("isolated")
        clean = payload.get("clean")

        if repository != request.repository:
            raise GitSubjectContractError("worktree repository mismatch")
        if work_id != request.work_id or attempt_id != request.attempt_id:
            raise GitSubjectContractError("worktree is not bound to requested Work/Attempt")
        if not isinstance(base_sha, str) or not _SHA_RE.fullmatch(base_sha):
            raise GitSubjectContractError("worktree response missing exact base SHA")
        if base_sha.lower() != request.base_sha.lower():
            raise GitSubjectContractError("worktree base SHA mismatch")
        if not isinstance(worktree_ref, str) or not worktree_ref.strip():
            raise GitSubjectContractError("worktree_ref is required")
        if branch_ref is not None and not isinstance(branch_ref, str):
            raise GitSubjectContractError("branch_ref must be a string when supplied")
        if isolated is not True:
            raise GitSubjectContractError("worktree provider did not attest isolation")
        if clean is not True:
            raise GitSubjectContractError("worktree must be clean before implementation")

        return cls(
            repository=repository,
            work_id=work_id,
            attempt_id=attempt_id,
            base_sha=base_sha.lower(),
            worktree_ref=worktree_ref,
            branch_ref=branch_ref,
            isolated=True,
            clean=True,
        )


@dataclass(frozen=True)
class GitCandidateSubject:
    repository: str
    work_id: str
    attempt_id: str
    worktree_ref: str
    base_sha: str
    candidate_sha: str
    branch_ref: str | None = None

    @property
    def verification_subject(self) -> str:
        return self.candidate_sha

    @classmethod
    def from_wire(
        cls,
        binding: GitWorktreeBinding,
        payload: Mapping[str, Any],
    ) -> "GitCandidateSubject":
        repository = payload.get("repository")
        work_id = payload.get("workId")
        attempt_id = payload.get("attemptId")
        worktree_ref = payload.get("worktreeRef")
        base_sha = payload.get("baseSha")
        candidate_sha = payload.get("candidateSha")
        branch_ref = payload.get("branchRef")

        if repository != binding.repository:
            raise GitSubjectContractError("candidate repository mismatch")
        if work_id != binding.work_id or attempt_id != binding.attempt_id:
            raise GitSubjectContractError("candidate Work/Attempt mismatch")
        if worktree_ref != binding.worktree_ref:
            raise GitSubjectContractError("candidate came from another worktree")
        if not isinstance(base_sha, str) or base_sha.lower() != binding.base_sha:
            raise GitSubjectContractError("candidate base SHA mismatch")
        if not isinstance(candidate_sha, str) or not _SHA_RE.fullmatch(candidate_sha):
            raise GitSubjectContractError("candidate_sha must be an exact 40-hex commit")
        if branch_ref is not None and not isinstance(branch_ref, str):
            raise GitSubjectContractError("candidate branch_ref must be a string when supplied")

        return cls(
            repository=repository,
            work_id=work_id,
            attempt_id=attempt_id,
            worktree_ref=worktree_ref,
            base_sha=binding.base_sha,
            candidate_sha=candidate_sha.lower(),
            branch_ref=branch_ref,
        )

    def is_current(self, current_sha: str) -> bool:
        return (
            isinstance(current_sha, str)
            and bool(_SHA_RE.fullmatch(current_sha))
            and self.candidate_sha == current_sha.lower()
        )


class GitSubjectTransport(Protocol):
    """Injected Habitat/sandbox transport. STEWARD owns no Git workspace daemon."""

    def prepare_worktree(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def capture_candidate(self, worktree_ref: str) -> Mapping[str, Any]: ...


class GitSubjectPort:
    """Fail-closed Work/Attempt→worktree→exact-subject binder."""

    def __init__(self, transport: GitSubjectTransport) -> None:
        self._transport = transport

    def prepare(self, request: GitWorktreeRequest) -> GitWorktreeBinding:
        try:
            payload = self._transport.prepare_worktree(request.to_wire())
        except GitSubjectError:
            raise
        except Exception as exc:
            raise GitSubjectUnavailableError("worktree provider failed") from exc
        if not isinstance(payload, Mapping):
            raise GitSubjectContractError("worktree provider returned non-object response")
        return GitWorktreeBinding.from_wire(request, payload)

    def capture(self, binding: GitWorktreeBinding) -> GitCandidateSubject:
        try:
            payload = self._transport.capture_candidate(binding.worktree_ref)
        except GitSubjectError:
            raise
        except Exception as exc:
            raise GitSubjectUnavailableError("candidate capture failed") from exc
        if not isinstance(payload, Mapping):
            raise GitSubjectContractError("candidate provider returned non-object response")
        return GitCandidateSubject.from_wire(binding, payload)
