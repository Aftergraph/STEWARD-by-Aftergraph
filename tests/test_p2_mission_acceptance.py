import unittest

from steward.p2_mission_acceptance import (
    P2AcceptanceEvidenceError,
    P2EffectVerificationEvidence,
    P2ExecutionEvidence,
    project_owner_acceptance_readiness,
)


WORK = "wrk_" + "1" * 32
CTX = "ctx_" + "2" * 32
ACTION = "act_" + "3" * 32
AUTH = "auth_" + "4" * 32
PDR = "pdr_" + "5" * 32
WEXEC = "wexec/p2/1"
SHA = "a" * 40
RECEIPT = "b" * 64
REPO = "Aftergraph/runtime"
SUBJECT = f"git:{REPO}@{SHA}"


def execution():
    return P2ExecutionEvidence(
        work_id=WORK,
        works_execution_id=WEXEC,
        execution_context_id=CTX,
        action_id=ACTION,
        authority_lease_id=AUTH,
        execution_pdr_id=PDR,
    )


def effect(**overrides):
    values = dict(
        work_id=WORK,
        works_execution_id=WEXEC,
        execution_context_id=CTX,
        action_id=ACTION,
        authority_lease_id=AUTH,
        execution_pdr_id=PDR,
        repository=REPO,
        observed_sha=SHA,
        bound_subject=SUBJECT,
        sentinel_head_sha=SHA,
        sentinel_verdict="SHIP",
        sentinel_receipt_id=RECEIPT,
        remote_readback=True,
        credential_surrogation=True,
        action_time_revalidation=True,
        revocation_fail_closed=True,
    )
    values.update(overrides)
    return P2EffectVerificationEvidence(**values)


class MissionAcceptanceEvidenceTests(unittest.TestCase):
    def test_matching_live_current_subject_is_ready_for_owner_acceptance(self):
        out = project_owner_acceptance_readiness(execution(), effect())
        self.assertTrue(out.ready_for_owner_acceptance)
        self.assertEqual(SUBJECT, out.verification_subject)
        self.assertEqual(RECEIPT, out.sentinel_receipt_id)

    def test_different_execution_context_fails_closed(self):
        with self.assertRaisesRegex(P2AcceptanceEvidenceError, "execution_context_id"):
            project_owner_acceptance_readiness(
                execution(),
                effect(execution_context_id="ctx_" + "9" * 32),
            )

    def test_do_not_ship_never_reaches_owner_acceptance(self):
        with self.assertRaisesRegex(P2AcceptanceEvidenceError, "not SHIP"):
            project_owner_acceptance_readiness(
                execution(), effect(sentinel_verdict="DO_NOT_SHIP")
            )

    def test_stale_sentinel_head_fails_closed(self):
        with self.assertRaisesRegex(P2AcceptanceEvidenceError, "different Git subject"):
            project_owner_acceptance_readiness(
                execution(), effect(sentinel_head_sha="c" * 40)
            )

    def test_unbound_or_rebound_subject_fails_closed(self):
        with self.assertRaisesRegex(P2AcceptanceEvidenceError, "subject binding"):
            project_owner_acceptance_readiness(
                execution(),
                effect(bound_subject=f"git:{REPO}@{'d' * 40}"),
            )

    def test_missing_live_control_evidence_fails_closed(self):
        with self.assertRaisesRegex(P2AcceptanceEvidenceError, "revocation_fail_closed"):
            project_owner_acceptance_readiness(
                execution(), effect(revocation_fail_closed=False)
            )


if __name__ == "__main__":
    unittest.main()
