import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
    def _schema(self, name):
        return json.loads((ROOT / 'schemas' / name).read_text(encoding='utf-8'))

    def _fixture(self, category, name):
        return json.loads((ROOT / 'fixtures' / category / name).read_text(encoding='utf-8'))

    def _errors(self, schema, instance):
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return list(validator.iter_errors(instance))

    def test_valid_intent_envelope(self):
        self.assertEqual([], self._errors(self._schema('intent-envelope.schema.json'), self._fixture('valid', 'intent-envelope.json')))

    def test_valid_work_claim(self):
        self.assertEqual([], self._errors(self._schema('work-claim.schema.json'), self._fixture('valid', 'work-claim.json')))

    def test_valid_git_effect_intent(self):
        self.assertEqual([], self._errors(self._schema('git-effect-intent.schema.json'), self._fixture('valid', 'git-effect-intent.json')))

    def test_git_effect_requires_authority(self):
        self.assertTrue(self._errors(self._schema('git-effect-intent.schema.json'), self._fixture('invalid', 'git-effect-intent-missing-authority.json')))

    def test_work_claim_scope_cannot_be_empty(self):
        self.assertTrue(self._errors(self._schema('work-claim.schema.json'), self._fixture('invalid', 'work-claim-empty-scope.json')))

    def test_valid_presence_projection(self):
        self.assertEqual([], self._errors(self._schema('presence-projection.schema.json'), self._fixture('valid', 'presence-projection.json')))

    def test_succeeded_presence_requires_verification_verdict(self):
        self.assertTrue(self._errors(self._schema('presence-projection.schema.json'), self._fixture('invalid', 'presence-projection-succeeded-without-verdict.json')))

if __name__ == '__main__':
    unittest.main()
