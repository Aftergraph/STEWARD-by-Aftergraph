"""Sentinel verdict delegation: Level 5 of the autonomy ladder.

A merge-completing agent may request an independent Sentinel verdict, but it
can never mint the authority to verify itself. This module implements the
delegation seam:

1. The agent holds `verify:delegate` in its attenuated grant — the approval
   to *spawn* a verifier, not to verify.
2. An external AIE authority instance mints the child grant for the spawned
   verifier persona. The child grant is attenuated against the *agent's*
   parent set: delegation can never escalate.
3. The child grant is bound to the exact result SHA — the verdict it may
   produce is scoped to that subject and nothing else.
4. The spawned verifier resolves `verify:exact-subject` through the same
   fail-closed resolver. Only its ALLOW produces a Sentinel verdict receipt.
5. Mission acceptance consumes the verdict receipt; the merge agent's own
   signature is never sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from steward_reference.delegated_authority import (
    DelegatedAuthorityError,
    is_attenuated,
    resolve_action,
    validate_grant,
)

VERIFIER_PERSONA_ID = "persona-spawned-verifier-v1"
DELEGATION_WINDOW = timedelta(hours=1)


class DelegationDeniedError(RuntimeError):
    """Raised when a delegation request cannot be satisfied fail-closed."""


@dataclass(frozen=True)
class SentinelVerdict:
    verdict_id: str
    subject_sha: str
    verdict: str
    verifier_persona_id: str
    delegated_by: str
    child_grant_id: str


class AieMint:
    """External authority instance that mints child grants.

    This is deliberately a separate class: the agent calls it, it does not
    run inside the agent. It mints only what the parent grant's attenuation
    permits, bound to the exact subject the agent produced.
    """

    def __init__(self, *, mint_ref: str) -> None:
        self.mint_ref = mint_ref
        self._counter = 0

    def mint_child_grant(
        self,
        *,
        parent_grant: dict[str, Any],
        subject_sha: str,
        now: datetime,
        requested_by: str,
    ) -> dict[str, Any]:
        if not is_attenuated(parent_grant):
            raise DelegationDeniedError("cannot mint from an escalated parent grant")
        if "verify:delegate" not in parent_grant["capabilities"]:
            raise DelegationDeniedError("parent grant lacks verify:delegate approval")
        if "verify:exact-subject" not in parent_grant["parent_capabilities"]:
            raise DelegationDeniedError(
                "verify:exact-subject not in parent capability set; delegation would escalate"
            )
        self._counter += 1
        granted_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        expires = (now + DELEGATION_WINDOW).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "schema_version": "steward.delegated-authority/1.0",
            "grant_id": f"grant-spawned-verifier-{self._counter:03d}",
            "grantee_persona_id": VERIFIER_PERSONA_ID,
            "authority_source": {
                "owner": "aie",
                "grant_ref": f"aie:mint/{self.mint_ref}/delegate/{self._counter:03d}",
            },
            "capabilities": ["verify:exact-subject"],
            "parent_capabilities": parent_grant["parent_capabilities"],
            "verification_binding": {
                "verifier_owner": "sentinel",
                "verifier_ref": f"sentinel:verdict/delegated/{self._counter:03d}",
                "subject_sha": subject_sha,
            },
            "granted_at": granted_at,
            "expires_at": expires,
            "status": "granted",
            "delegated_by": requested_by,
        }


class SpawnedVerifier:
    """The delegated verifier persona. Runs the exact-subject verdict."""

    def __init__(self, *, child_grant: dict[str, Any]) -> None:
        self.child_grant = child_grant

    def issue_verdict(self, *, subject_sha: str, now: datetime) -> SentinelVerdict:
        receipt = resolve_action(
            grant=self.child_grant,
            requested_capability="verify:exact-subject",
            requested_subject_sha=subject_sha,
            now=now,
        )
        if receipt["decision"] != "ALLOW":
            raise DelegationDeniedError(f"verifier denied: {receipt['reason']}")
        return SentinelVerdict(
            verdict_id=self.child_grant["verification_binding"]["verifier_ref"],
            subject_sha=subject_sha,
            verdict="PASS",
            verifier_persona_id=self.child_grant["grantee_persona_id"],
            delegated_by=self.child_grant["delegated_by"],
            child_grant_id=self.child_grant["grant_id"],
        )


def request_sentinel_delegation(
    *,
    agent_grant: dict[str, Any],
    subject_sha: str,
    now: datetime,
    mint: AieMint,
) -> SpawnedVerifier:
    """The agent's entry point: check its own delegation approval, then spawn.

    The agent's grant must carry verify:delegate and be resolvable. The mint
    independently re-checks attenuation; the agent cannot influence the child
    grant's capability set or subject binding.
    """
    approval = resolve_action(
        grant=agent_grant,
        requested_capability="verify:delegate",
        now=now,
    )
    if approval["decision"] != "ALLOW":
        raise DelegationDeniedError(f"delegation not approved: {approval['reason']}")
    child_grant = mint.mint_child_grant(
        parent_grant=agent_grant,
        subject_sha=subject_sha,
        now=now,
        requested_by=agent_grant["grantee_persona_id"],
    )
    validate_grant(child_grant)
    return SpawnedVerifier(child_grant=child_grant)


def accept_mission_with_delegated_verdict(
    *,
    merged: bool,
    verdict: SentinelVerdict,
    result_sha: str,
) -> bool:
    """Acceptance requires a completed effect AND a delegated verdict on the exact subject."""
    if not merged:
        return False
    if verdict.subject_sha != result_sha:
        return False
    if verdict.verdict != "PASS":
        return False
    if verdict.verifier_persona_id != VERIFIER_PERSONA_ID:
        return False
    return True
