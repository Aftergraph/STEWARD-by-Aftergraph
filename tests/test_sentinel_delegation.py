import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from steward_reference.governed_agent import GovernedAgent
from steward_reference.sentinel_delegation import (
    AieMint,
    DelegationDeniedError,
    SpawnedVerifier,
    accept_mission_with_delegated_verdict,
    request_sentinel_delegation,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def _load_grant(category, name):
    return json.loads((ROOT / 'fixtures' / category / name).read_text(encoding='utf-8'))


class SentinelDelegationLevel5Tests(unittest.TestCase):
    def setUp(self):
        self.merge_grant = _load_grant('valid', 'delegated-authority-merge-agent.json')
        self.mint = AieMint(mint_ref='org-aftergraph/repo-steward')

    def test_merge_agent_holds_delegation_approval(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        self.assertTrue(receipt['merged'])
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant,
            subject_sha=receipt['result_sha'],
            now=NOW,
            mint=self.mint,
        )
        self.assertIsInstance(spawn, SpawnedVerifier)

    def test_spawned_verdict_is_scoped_to_exact_result_sha(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        verdict = spawn.issue_verdict(subject_sha=receipt['result_sha'], now=NOW)
        self.assertEqual(verdict.verdict, 'PASS')
        self.assertEqual(verdict.subject_sha, receipt['result_sha'])
        self.assertEqual(verdict.verifier_persona_id, 'persona-spawned-verifier-v1')
        self.assertEqual(verdict.delegated_by, 'persona-merge-agent-v1')

    def test_spawned_verifier_rejects_other_subjects(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        with self.assertRaises(DelegationDeniedError) as ctx:
            spawn.issue_verdict(subject_sha='f' * 40, now=NOW)
        self.assertIn('subject_mismatch', str(ctx.exception))

    def test_full_level5_chain_greenlights_mission(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        verdict = spawn.issue_verdict(subject_sha=receipt['result_sha'], now=NOW)
        accepted = accept_mission_with_delegated_verdict(
            merged=receipt['merged'], verdict=verdict, result_sha=receipt['result_sha'])
        self.assertTrue(accepted)

    def test_acceptance_rejects_verdict_on_wrong_subject(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        verdict = spawn.issue_verdict(subject_sha=receipt['result_sha'], now=NOW)
        accepted = accept_mission_with_delegated_verdict(
            merged=receipt['merged'], verdict=verdict, result_sha='f' * 40)
        self.assertFalse(accepted)

    def test_acceptance_rejects_failed_verdict(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        verdict = spawn.issue_verdict(subject_sha=receipt['result_sha'], now=NOW)
        failed = type(verdict)(
            verdict_id=verdict.verdict_id, subject_sha=verdict.subject_sha, verdict='FAIL',
            verifier_persona_id=verdict.verifier_persona_id, delegated_by=verdict.delegated_by,
            child_grant_id=verdict.child_grant_id)
        self.assertFalse(accept_mission_with_delegated_verdict(
            merged=True, verdict=failed, result_sha=receipt['result_sha']))

    def test_acceptance_requires_merged_effect(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        verdict = spawn.issue_verdict(subject_sha=receipt['result_sha'], now=NOW)
        self.assertFalse(accept_mission_with_delegated_verdict(
            merged=False, verdict=verdict, result_sha=receipt['result_sha']))

    def test_delegation_denied_without_delegate_capability(self):
        no_delegate = dict(self.merge_grant)
        no_delegate['capabilities'] = [c for c in no_delegate['capabilities'] if c != 'verify:delegate']
        with self.assertRaises(DelegationDeniedError) as ctx:
            request_sentinel_delegation(
                agent_grant=no_delegate, subject_sha='a' * 40, now=NOW, mint=self.mint)
        self.assertIn('verify:delegate', str(ctx.exception))

    def test_delegation_denied_when_parent_set_lacks_verify(self):
        cannot_spawn_verify = dict(self.merge_grant)
        cannot_spawn_verify['parent_capabilities'] = [
            c for c in cannot_spawn_verify['parent_capabilities'] if not c.startswith('verify:')]
        with self.assertRaises(DelegationDeniedError) as ctx:
            request_sentinel_delegation(
                agent_grant=cannot_spawn_verify, subject_sha='a' * 40, now=NOW, mint=self.mint)
        self.assertIn('escalation', str(ctx.exception))

    def test_delegation_denied_for_expired_agent_grant(self):
        expired = _load_grant('invalid', 'delegated-authority-expired.json')
        with self.assertRaises(DelegationDeniedError) as ctx:
            request_sentinel_delegation(
                agent_grant=expired, subject_sha='a' * 40, now=NOW, mint=self.mint)
        self.assertIn('capability_not_granted', str(ctx.exception))

    def test_expired_grant_with_delegate_capability_is_denied(self):
        expired_delegate = dict(_load_grant('invalid', 'delegated-authority-expired.json'))
        expired_delegate['capabilities'] = ['repo:read', 'pr:merge', 'verify:delegate']
        expired_delegate['parent_capabilities'] = ['repo:read', 'pr:merge', 'verify:delegate', 'verify:exact-subject']
        with self.assertRaises(DelegationDeniedError) as ctx:
            request_sentinel_delegation(
                agent_grant=expired_delegate, subject_sha='a' * 40, now=NOW, mint=self.mint)
        self.assertIn('expired', str(ctx.exception))

    def test_mint_refuses_escalated_parent(self):
        escalated = _load_grant('invalid', 'delegated-authority-escalation.json')
        with self.assertRaises(DelegationDeniedError):
            self.mint.mint_child_grant(
                parent_grant=escalated, subject_sha='a' * 40, now=NOW, requested_by='attacker')

    def test_child_grant_is_attenuated_and_sentinel_bound(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        child = self.mint.mint_child_grant(
            parent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW,
            requested_by='persona-merge-agent-v1')
        self.assertEqual(child['capabilities'], ['verify:exact-subject'])
        self.assertTrue(set(child['capabilities']) <= set(child['parent_capabilities']))
        self.assertEqual(child['verification_binding']['verifier_owner'], 'sentinel')
        self.assertEqual(child['verification_binding']['subject_sha'], receipt['result_sha'])
        self.assertEqual(child['authority_source']['owner'], 'aie')
        self.assertEqual(child['grantee_persona_id'], 'persona-spawned-verifier-v1')

    def test_child_grant_cannot_merge_or_admin(self):
        agent = GovernedAgent(persona_id='persona-merge-agent-v1', grant=self.merge_grant)
        receipt = agent.attempt_merge(now=NOW)
        spawn = request_sentinel_delegation(
            agent_grant=self.merge_grant, subject_sha=receipt['result_sha'], now=NOW, mint=self.mint)
        from steward_reference.delegated_authority import resolve_action
        for capability in ('pr:merge', 'repo:admin', 'verify:delegate'):
            out = resolve_action(grant=spawn.child_grant, requested_capability=capability, now=NOW)
            self.assertEqual(out['decision'], 'DENY')


if __name__ == '__main__':
    unittest.main()
