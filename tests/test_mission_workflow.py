import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from steward_reference.mission_workflow import (
    GovernedMissionWorkflow,
    MissionCorrelationError,
    WorksCorrelation,
)
from steward_reference.sentinel_delegation import AieMint

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)

VALID_CORRELATION = {
    "execution_context_id": "ctx_" + "a" * 32,
    "trace_id": "trc_" + "b" * 32,
}


def _load_grant(name='delegated-authority-merge-agent.json'):
    return json.loads((ROOT / 'fixtures' / 'valid' / name).read_text(encoding='utf-8'))


class WorksCorrelationTests(unittest.TestCase):
    def test_valid_works_correlation_is_accepted(self):
        corr = WorksCorrelation.from_mapping(VALID_CORRELATION)
        self.assertEqual(corr.execution_context_id, "ctx_" + "a" * 32)
        self.assertEqual(corr.trace_id, "trc_" + "b" * 32)

    def test_steward_minted_context_id_is_rejected(self):
        with self.assertRaises(MissionCorrelationError):
            WorksCorrelation.from_mapping({
                "execution_context_id": "steward-minted-001",
                "trace_id": "trc_" + "b" * 32,
            })

    def test_missing_correlation_is_rejected(self):
        with self.assertRaises(MissionCorrelationError):
            WorksCorrelation.from_mapping({"trace_id": "trc_" + "b" * 32})

    def test_malformed_trace_id_is_rejected(self):
        with self.assertRaises(MissionCorrelationError):
            WorksCorrelation.from_mapping({
                "execution_context_id": "ctx_" + "a" * 32,
                "trace_id": "trc_short",
            })


class MissionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.grant = _load_grant()
        self.corr = WorksCorrelation.from_mapping(VALID_CORRELATION)
        self.mint = AieMint(mint_ref='org-aftergraph/repo-steward')

    def _workflow(self):
        return GovernedMissionWorkflow(
            mission_id='mission-test-0001',
            persona_id='persona-merge-agent-v1',
            grant=self.grant,
            correlation=self.corr,
            mint=self.mint,
        )

    def test_autonomous_chain_reaches_greenlight(self):
        bundle = self._workflow().run(now=NOW)
        self.assertTrue(bundle['outcome']['accepted'])
        self.assertIsNotNone(bundle['outcome']['result_sha'])
        self.assertEqual(bundle['outcome']['verifier_persona'], 'persona-spawned-verifier-v1')
        self.assertEqual(bundle['outcome']['delegated_by'], 'persona-merge-agent-v1')

    def test_bundle_carries_external_works_correlation(self):
        bundle = self._workflow().run(now=NOW)
        self.assertEqual(bundle['works_correlation']['execution_context_id'], "ctx_" + "a" * 32)
        self.assertEqual(bundle['works_correlation']['trace_id'], "trc_" + "b" * 32)
        self.assertEqual(bundle['works_correlation']['minted_by'], 'works-execution')

    def test_workflow_steps_are_ordered_and_complete(self):
        bundle = self._workflow().run(now=NOW)
        kinds = [s['kind'] for s in bundle['workflow_steps']]
        self.assertEqual(kinds[0], 'mission.start')
        self.assertIn('effect.complete', kinds)
        self.assertIn('delegation.spawned', kinds)
        self.assertIn('verdict.received', kinds)
        self.assertEqual(kinds[-1], 'mission.acceptance')
        steps = [s['step'] for s in bundle['workflow_steps']]
        self.assertEqual(steps, sorted(steps))
        decisions = {s['decision'] for s in bundle['workflow_steps']}
        self.assertIn('ACCEPTED', decisions)

    def test_audit_trace_is_attributable(self):
        bundle = self._workflow().run(now=NOW)
        for event in bundle['audit_trace']:
            self.assertEqual(event['actor'], 'persona-merge-agent-v1')
            self.assertTrue(event['at'])
            self.assertGreater(event['seq'], 0)

    def test_denied_effect_blocks_the_whole_mission(self):
        expired = json.loads((ROOT / 'fixtures' / 'invalid' / 'delegated-authority-expired.json').read_text(encoding='utf-8'))
        workflow = GovernedMissionWorkflow(
            mission_id='mission-expired-0001',
            persona_id='persona-merge-agent-v1',
            grant=expired,
            correlation=self.corr,
            mint=self.mint,
        )
        bundle = workflow.run(now=NOW)
        self.assertFalse(bundle['outcome']['accepted'])
        self.assertIsNone(bundle['outcome']['result_sha'])
        kinds = [s['kind'] for s in bundle['workflow_steps']]
        self.assertIn('effect.blocked', kinds)
        self.assertNotIn('verdict.received', kinds)
        self.assertNotIn('delegation.spawned', kinds)

    def test_delegation_failure_records_denial_without_verdict(self):
        grant = dict(self.grant)
        grant['capabilities'] = [c for c in grant['capabilities'] if c != 'verify:delegate']
        workflow = GovernedMissionWorkflow(
            mission_id='mission-nodelegate-0001',
            persona_id='persona-merge-agent-v1',
            grant=grant,
            correlation=self.corr,
            mint=self.mint,
        )
        bundle = workflow.run(now=NOW)
        self.assertFalse(bundle['outcome']['accepted'])
        kinds = [s['kind'] for s in bundle['workflow_steps']]
        self.assertIn('effect.complete', kinds)
        self.assertIn('delegation.denied', kinds)
        self.assertNotIn('verdict.received', kinds)


if __name__ == '__main__':
    unittest.main()
