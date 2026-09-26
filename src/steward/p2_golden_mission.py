"""Composed STEWARD P2 Golden Mission gate.

This module owns composition only. Runtime owns dispatch, WORKS owns durable
execution truth, Trust Gateway/AIE own effect-time authorization, the Habitat
provider owns worktree execution, and Sentinel owns the verification verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ports.git_subject import GitCandidateSubject, GitSubjectPort, GitWorktreeRequest
from .ports.runtime import RuntimeDispatchV2Request, RuntimeDispatchV2Receipt, RuntimeV2Port
from .ports.runtime_subject import (
    RuntimeSubjectBindingPort,
    RuntimeSubjectBindingReceipt,
    RuntimeSubjectBindingRequest,
)
from .ports.sentinel import SentinelPort, SentinelVerificationProjection, SentinelVerificationRequest
from .ports.mission_acceptance import (
    MissionAcceptancePort,
    MissionAcceptanceProjection,
    MissionAcceptanceRequest,
)
from .ports.trust_gateway import (
    TrustGatewayActionReceipt,
    TrustGatewayActionRequest,
    TrustGatewayApprovalRequired,
    TrustGatewayClient,
)


class GoldenMissionContractError(RuntimeError):
    """Cross-owner receipts cannot be composed into one causal mission."""


@dataclass(frozen=True)
class GoldenMissionRequest:
    dispatch: RuntimeDispatchV2Request
    repository: str
    base_sha: str
    action_id: str
    tool: str
    tool_args: Any = None
    branch_ref: str | None = None
    pull_request: int | None = None


@dataclass(frozen=True)
class GoldenMissionNeedsApproval:
    runtime: RuntimeDispatchV2Receipt
    approval_id: str
    reason: str | None


@dataclass(frozen=True)
class GoldenMissionOutcome:
    runtime: RuntimeDispatchV2Receipt
    action: TrustGatewayActionReceipt
    candidate: GitCandidateSubject
    subject_binding: RuntimeSubjectBindingReceipt
    verification: SentinelVerificationProjection
    mission_acceptance: MissionAcceptanceProjection | None
    accepted: bool


class GoldenMissionCoordinator:
    """Execute the narrow P2 chain without absorbing canonical ownership."""

    def __init__(
        self,
        runtime: RuntimeV2Port,
        trust_gateway: TrustGatewayClient,
        git_subject: GitSubjectPort,
        subject_binding: RuntimeSubjectBindingPort,
        sentinel: SentinelPort,
        mission_acceptance: MissionAcceptancePort,
    ) -> None:
        self._runtime = runtime
        self._trust_gateway = trust_gateway
        self._git_subject = git_subject
        self._subject_binding = subject_binding
        self._sentinel = sentinel
        self._mission_acceptance = mission_acceptance

    def execute(
        self, request: GoldenMissionRequest
    ) -> GoldenMissionOutcome | GoldenMissionNeedsApproval:
        runtime = self._runtime.dispatch(request.dispatch)

        worktree = self._git_subject.prepare(
            GitWorktreeRequest(
                repository=request.repository,
                work_id=request.dispatch.work_id,
                attempt_id=request.dispatch.attempt_id,
                base_sha=request.base_sha,
                branch_ref=request.branch_ref,
            )
        )

        action = self._trust_gateway.execute(
            TrustGatewayActionRequest(
                action_id=request.action_id,
                execution_context_id=runtime.execution_context_id,
                mission_id=request.dispatch.mission_id,
                tool=request.tool,
                args=request.tool_args,
            )
        )
        if isinstance(action, TrustGatewayApprovalRequired):
            return GoldenMissionNeedsApproval(
                runtime=runtime,
                approval_id=action.approval_id,
                reason=action.reason,
            )

        candidate = self._git_subject.capture(worktree)
        if candidate.work_id != runtime.work_id:
            raise GoldenMissionContractError("candidate rebound to another Work")

        exact_subject = f"git:{candidate.repository}@{candidate.candidate_sha}"
        binding = self._subject_binding.bind(
            RuntimeSubjectBindingRequest(
                work_id=runtime.work_id,
                works_execution_id=runtime.works_execution_id,
                attempt_id=request.dispatch.attempt_id,
                effect_id=request.dispatch.effect_id,
                causal_id=request.dispatch.causal_id,
                subject=exact_subject,
            )
        )
        if binding.subject != exact_subject:
            raise GoldenMissionContractError("Runtime bound a different exact subject")

        verification = self._sentinel.verify(
            SentinelVerificationRequest(
                repository=candidate.repository,
                head_sha=candidate.candidate_sha,
                pull_request=request.pull_request,
            )
        )
        if not verification.satisfies(candidate.candidate_sha):
            return GoldenMissionOutcome(
                runtime=runtime,
                action=action,
                candidate=candidate,
                subject_binding=binding,
                verification=verification,
                mission_acceptance=None,
                accepted=False,
            )

        acceptance = self._mission_acceptance.project(
            MissionAcceptanceRequest(
                mission_id=request.dispatch.mission_id,
                work_id=runtime.work_id,
                execution_context_id=runtime.execution_context_id,
                execution_policy_decision_id=action.execution_pdr_id,
            )
        )
        return GoldenMissionOutcome(
            runtime=runtime,
            action=action,
            candidate=candidate,
            subject_binding=binding,
            verification=verification,
            mission_acceptance=acceptance,
            accepted=acceptance.accepted,
        )
