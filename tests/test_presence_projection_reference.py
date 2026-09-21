import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, FormatChecker
from steward_reference.presence_projection import PresenceProjectionError, build_presence_projection

ROOT = Path(__file__).resolve().parents[1]

class PresenceProjectionReferenceTests(unittest.TestCase):
    def setUp(self):
        schema = json.loads((ROOT / "schemas" / "presence-projection.schema.json").read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_verified_success_is_schema_valid_and_side_effect_free(self):
        projection = build_presence_projection(
            projection_id="presence:test:verified", subject_kind="verification", subject_id="verification:test:1",
            displayed_state="succeeded", source_owner="sentinel", source_kind="verification-verdict",
            source_id="sentinel:verdict:1", verification_verdict_id="verdict:1", evidence_ref="evidence:1",
            generated_at="2026-09-21T17:00:00Z")
        self.assertEqual([], list(self.validator.iter_errors(projection)))
        self.assertFalse(projection["canonical_truth"])
        self.assertFalse(projection["authority_effect"])
        self.assertFalse(projection["verification_effect"])

    def test_completed_work_cannot_project_as_succeeded(self):
        with self.assertRaises(PresenceProjectionError):
            build_presence_projection(
                projection_id="presence:test:false-success", subject_kind="work", subject_id="work:1",
                displayed_state="succeeded", source_owner="works-execution", source_kind="work-state",
                source_id="work:1", generated_at="2026-09-21T17:00:00Z")

    def test_agent_self_report_cannot_project_verifying(self):
        with self.assertRaises(PresenceProjectionError):
            build_presence_projection(
                projection_id="presence:test:false-verify", subject_kind="work", subject_id="work:1",
                displayed_state="verifying", source_owner="steward", source_kind="projection-local",
                source_id="agent:self-report", generated_at="2026-09-21T17:00:00Z")

if __name__ == "__main__":
    unittest.main()
