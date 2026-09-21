import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from steward_reference.governed_agent import GovernedAgent, governed_agent_run

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def _load_grant(category, name):
    return json.loads((ROOT / 'fixtures' / category / name).read_text(encoding='utf-8'))


class GovernedAgentLevel4Tests(unittest.TestCase):
    def setUp(self):
        self.merge_grant = _load_grant('valid', 'delegated-authority-merge-agent.json')
        self.verifier_grant = _load_grant('valid', 'delegated-authority-verifier.json')

    def test_authorized_agent_performs_real_governed_merge(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        self.assertTrue(receipt['merged'])
        self.assertEqual(receipt['decision']['decision'], 'ALLOW')
        self.assertEqual(receipt['decision']['authority_source'], 'aie')
        self.assertIsNotNone(receipt['result_sha'])
        self.assertGreater(len(receipt['result_sha']), 0)

    def test_denied_agent_leaves_subject_untouched(self):
        expired = _load_grant('invalid', 'delegated-authority-expired.json')
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=expired)
        receipt = agent.attempt_merge(now=NOW)
        self.assertFalse(receipt['merged'])
        self.assertEqual(receipt['decision']['decision'], 'DENY')
        self.assertIn('expired', receipt['decision']['reason'])
        self.assertIsNone(receipt['result_sha'])
        kinds = [e.kind for e in agent.trace()]
        self.assertIn('authority.resolve', kinds)
        self.assertIn('effect.blocked', kinds)
        self.assertNotIn('git.merge', kinds)

    def test_escalated_agent_is_denied_before_any_effect(self):
        escalated = _load_grant('invalid', 'delegated-authority-escalation.json')
        agent = GovernedAgent(persona_id='persona-self-authorizing-reviewer-v0', grant=escalated)
        receipt = agent.attempt_merge(now=NOW)
        self.assertFalse(receipt['merged'])
        self.assertIn('escalation', receipt['decision']['reason'])

    def test_merge_agent_cannot_self_verify(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        merge_receipt = agent.attempt_merge(now=NOW)
        self.assertTrue(merge_receipt['merged'])
        verdict = agent.verify_independently(result_sha=merge_receipt['result_sha'], now=NOW)
        self.assertEqual(verdict['decision'], 'DENY')
        self.assertIn('capability_not_granted', verdict['reason'])

    def test_bound_verifier_claims_only_bound_subject(self):
        agent = GovernedAgent(persona_id='persona-verification-subscriber-v1', grant=self.verifier_grant)
        bound_sha = self.verifier_grant['verification_binding']['subject_sha']
        allowed = agent.verify_independently(result_sha=bound_sha, now=NOW)
        self.assertEqual(allowed['decision'], 'ALLOW')
        mismatch = agent.verify_independently(
            result_sha='ffffffffffffffffffffffffffffffffffffffff', now=NOW)
        self.assertEqual(mismatch['decision'], 'DENY')
        self.assertIn('subject_mismatch', mismatch['reason'])

    def test_acceptance_requires_external_verification(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        merge_receipt = agent.attempt_merge(now=NOW)
        self.assertTrue(merge_receipt['merged'])
        unverified = agent.accept_mission(merged=True, verdict={'decision': 'DENY'})
        self.assertFalse(unverified)
        verified = agent.accept_mission(merged=True, verdict={'decision': 'ALLOW'})
        self.assertTrue(verified)

    def test_full_chain_produces_ordered_audit_trace(self):
        bundle = governed_agent_run(persona_id='persona-merge-agent-v1',
                                    grant=self.merge_grant, now=NOW)
        self.assertEqual(bundle['outcome']['merged'], True)
        self.assertEqual(bundle['outcome']['verdict_decision'], 'DENY')
        self.assertEqual(bundle['outcome']['accepted'], False)
        self.assertEqual(bundle['grant_state'], 'active')
        seqs = [e['seq'] for e in bundle['trace']]
        self.assertEqual(seqs, sorted(seqs))
        kinds = [e['kind'] for e in bundle['trace']]
        self.assertIn('authority.resolve', kinds)
        self.assertIn('git.merge', kinds)
        self.assertIn('verification.claim', kinds)
        self.assertIn('mission.acceptance', kinds)

    def test_full_chain_without_grant_produces_no_effect(self):
        expired = _load_grant('invalid', 'delegated-authority-expired.json')
        bundle = governed_agent_run(persona_id='persona-merge-agent-v1',
                                    grant=expired, now=NOW)
        self.assertEqual(bundle['outcome']['merged'], False)
        self.assertEqual(bundle['outcome']['accepted'], False)
        self.assertEqual(bundle['grant_state'], 'expired')
        kinds = [e['kind'] for e in bundle['trace']]
        self.assertNotIn('git.merge', kinds)

    def test_every_trace_event_is_attributable(self):
        bundle = governed_agent_run(persona_id='persona-merge-agent-v1',
                                    grant=self.merge_grant, now=NOW)
        for event in bundle['trace']:
            self.assertEqual(event['actor'], 'persona-merge-agent-v1')
            self.assertTrue(event['at'])
            self.assertIn(event['decision'], ('ALLOW', 'DENY', 'ACCEPTED', 'REJECTED'))


if __name__ == '__main__':
    unittest.main()
