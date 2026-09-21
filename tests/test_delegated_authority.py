import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from jsonschema import Draft202012Validator, FormatChecker

from steward_reference.delegated_authority import (
    DelegatedAuthorityError,
    grant_state,
    is_attenuated,
    resolve_action,
    validate_grant,
)

ROOT = Path(__file__).resolve().parents[1]


class DelegatedAuthorityContractTests(unittest.TestCase):
    def _schema(self):
        return json.loads((ROOT / 'schemas' / 'delegated-authority.schema.json').read_text(encoding='utf-8'))

    def _fixture(self, category, name):
        return json.loads((ROOT / 'fixtures' / category / name).read_text(encoding='utf-8'))

    def _errors(self, instance):
        validator = Draft202012Validator(self._schema(), format_checker=FormatChecker())
        return list(validator.iter_errors(instance))

    def test_valid_merge_agent_grant(self):
        self.assertEqual([], self._errors(self._fixture('valid', 'delegated-authority-merge-agent.json')))

    def test_valid_verifier_grant_with_sentinel_binding(self):
        self.assertEqual([], self._errors(self._fixture('valid', 'delegated-authority-verifier.json')))

    def test_escalation_grant_is_structurally_valid_but_algorithmically_denied(self):
        escalation = self._fixture('invalid', 'delegated-authority-escalation.json')
        self.assertEqual([], self._errors(escalation))
        self.assertFalse(is_attenuated(escalation))
        for capability in escalation['capabilities']:
            out = resolve_action(grant=escalation, requested_capability=capability,
                                  now=datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc))
            self.assertEqual(out['decision'], 'DENY')

    def test_verify_capability_requires_sentinel_binding_in_schema(self):
        errors = self._errors(self._fixture('invalid', 'delegated-authority-verify-without-sentinel.json'))
        self.assertTrue(errors)


class DelegatedAuthorityAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
        self.merge_grant = json.loads((ROOT / 'fixtures' / 'valid' / 'delegated-authority-merge-agent.json').read_text(encoding='utf-8'))
        self.verifier_grant = json.loads((ROOT / 'fixtures' / 'valid' / 'delegated-authority-verifier.json').read_text(encoding='utf-8'))

    def test_grant_is_well_formed(self):
        validate_grant(self.merge_grant)
        validate_grant(self.verifier_grant)

    def test_grant_is_attenuated(self):
        self.assertTrue(is_attenuated(self.merge_grant))
        self.assertTrue(is_attenuated(self.verifier_grant))

    def test_active_grant_allows_granted_capability(self):
        out = resolve_action(grant=self.merge_grant, requested_capability='pr:merge', now=self.now)
        self.assertEqual(out['decision'], 'ALLOW')
        self.assertEqual(out['authority_source'], 'aie')

    def test_active_grant_denies_ungranted_capability(self):
        out = resolve_action(grant=self.merge_grant, requested_capability='repo:admin', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('capability_not_granted', out['reason'])

    def test_escalation_is_denied(self):
        grant = json.loads((ROOT / 'fixtures' / 'invalid' / 'delegated-authority-escalation.json').read_text(encoding='utf-8'))
        out = resolve_action(grant=grant, requested_capability='repo:admin', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('escalation', out['reason'])

    def test_expired_grant_is_denied(self):
        grant = json.loads((ROOT / 'fixtures' / 'invalid' / 'delegated-authority-expired.json').read_text(encoding='utf-8'))
        self.assertEqual(grant_state(grant, now=self.now), 'expired')
        out = resolve_action(grant=grant, requested_capability='pr:merge', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('expired', out['reason'])

    def test_expired_grant_was_active_before_expiry(self):
        grant = json.loads((ROOT / 'fixtures' / 'invalid' / 'delegated-authority-expired.json').read_text(encoding='utf-8'))
        before = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(grant_state(grant, now=before), 'active')
        out = resolve_action(grant=grant, requested_capability='pr:merge', now=before)
        self.assertEqual(out['decision'], 'ALLOW')

    def test_revocation_is_denied(self):
        grant = dict(self.merge_grant)
        grant['revoked_at'] = '2026-09-21T10:00:00Z'
        out = resolve_action(grant=grant, requested_capability='pr:merge', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('revoked', out['reason'])

    def test_expiry_boundary_determines_state(self):
        grant = dict(self.merge_grant)
        expires = datetime(2026, 9, 28, 8, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(grant_state(grant, now=expires - timedelta(seconds=1)), 'active')
        self.assertEqual(grant_state(grant, now=expires), 'expired')

    def test_verify_capability_requires_sentinel_binding(self):
        grant = dict(self.verifier_grant)
        grant.pop('verification_binding')
        out = resolve_action(grant=grant, requested_capability='verify:exact-subject',
                             requested_subject_sha='94a64d4322c159d524708d721aeee5223f2c873a', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('sentinel', out['reason'])

    def test_exact_subject_verification_requires_subject_sha(self):
        out = resolve_action(grant=self.verifier_grant, requested_capability='verify:exact-subject', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('subject_sha', out['reason'])

    def test_subject_mismatch_is_denied(self):
        out = resolve_action(grant=self.verifier_grant, requested_capability='verify:exact-subject',
                             requested_subject_sha='ffffffffffffffffffffffffffffffffffffffff', now=self.now)
        self.assertEqual(out['decision'], 'DENY')
        self.assertIn('subject_mismatch', out['reason'])

    def test_bound_subject_verification_is_allowed(self):
        out = resolve_action(grant=self.verifier_grant, requested_capability='verify:exact-subject',
                             requested_subject_sha='94a64d4322c159d524708d721aeee5223f2c873a', now=self.now)
        self.assertEqual(out['decision'], 'ALLOW')

    def test_malformed_grant_raises(self):
        with self.assertRaises(DelegatedAuthorityError):
            validate_grant({'grant_id': '', 'grantee_persona_id': ''})

    def test_grant_with_reversed_temporal_bounds_raises(self):
        grant = dict(self.merge_grant)
        grant['granted_at'], grant['expires_at'] = grant['expires_at'], grant['granted_at']
        with self.assertRaises(DelegatedAuthorityError):
            validate_grant(grant)

    def test_self_authorized_grant_without_parent_set_cannot_escalate(self):
        self_authorized = json.loads((ROOT / 'fixtures' / 'invalid' / 'delegated-authority-escalation.json').read_text(encoding='utf-8'))
        self.assertFalse(is_attenuated(self_authorized))
        for capability in self_authorized['capabilities']:
            out = resolve_action(grant=self_authorized, requested_capability=capability, now=self.now)
            self.assertEqual(out['decision'], 'DENY')


if __name__ == '__main__':
    unittest.main()
