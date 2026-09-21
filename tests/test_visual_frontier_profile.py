import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


class VisualFrontierProfileTests(unittest.TestCase):
    def _read(self, path):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    def _errors(self, instance):
        schema = self._read("schemas/visual-frontier-profile.schema.json")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return list(validator.iter_errors(instance))

    def test_revision_4_frontier_profile_is_valid(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertEqual([], self._errors(profile))

    def test_visual_profile_cannot_create_authority(self):
        profile = self._read("fixtures/invalid/visual-frontier-profile-authority.json")
        self.assertTrue(self._errors(profile))

    def test_profile_keeps_brand_ownership_external(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertEqual("Aftergraph/brand", profile["identity_owner"])
        self.assertEqual("Aftergraph/STEWARD-by-Aftergraph", profile["renderer_owner"])

    def test_required_motion_and_state_vocabulary_are_pinned(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertTrue({"idle", "blink", "verify"} <= set(profile["runtime"]["required_clips"]))
        self.assertEqual(
            {"idle", "thinking", "planning", "executing", "verifying", "succeeded"},
            set(profile["state_assets"]["states"]),
        )


if __name__ == "__main__":
    unittest.main()
