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

    def test_revision_5_frontier_profile_is_valid(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertEqual([], self._errors(profile))

    def test_visual_profile_cannot_create_authority(self):
        profile = self._read("fixtures/invalid/visual-frontier-profile-authority.json")
        self.assertTrue(self._errors(profile))

    def test_profile_keeps_brand_ownership_external(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertEqual("Aftergraph/brand", profile["identity_owner"])
        self.assertEqual("Aftergraph/STEWARD-by-Aftergraph", profile["renderer_owner"])

    def test_runtime_evidence_is_exactly_pinned(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        self.assertEqual(5, profile["source_scene"]["revision"])
        self.assertEqual("frontier-proportions/1.0", profile["source_scene"]["proportion_profile"])
        self.assertEqual("/assets/steward-rig-v2.glb", profile["runtime"]["asset_path"])
        self.assertEqual(
            "018fb057659975d67a3f6de3dc90a5167bc046d3bf366e3c0a9fe6ec96ecf6a8",
            profile["runtime"]["asset_sha256"],
        )
        self.assertEqual(
            "a25fa626979b3f938e9cec232cbaef52771e9db3",
            profile["runtime"]["source_commit"],
        )
        self.assertEqual({"idle", "blink", "verify"}, set(profile["runtime"]["required_clips"]))

    def test_visual_state_vocabulary_matches_presence_projection(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        presence_schema = self._read("schemas/presence-projection.schema.json")
        canonical_states = presence_schema["properties"]["displayed_state"]["enum"]
        self.assertEqual(canonical_states, profile["state_assets"]["states"])

    def test_state_pack_is_revision_5_and_full_vocabulary(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        state_assets = profile["state_assets"]
        self.assertEqual("steward.rig-state-assets/4.0", state_assets["schema_version"])
        self.assertEqual(5, state_assets["source_revision"])
        self.assertEqual(12, len(state_assets["states"]))
        self.assertFalse(state_assets["geometry_topology_changed"])
        self.assertFalse(state_assets["armature_changed"])

    def test_compact_presence_is_same_rig_derived_subset(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        presence_schema = self._read("schemas/presence-projection.schema.json")
        canonical_states = set(presence_schema["properties"]["displayed_state"]["enum"])
        compact = profile["compact_presence"]
        self.assertEqual("steward.compact-presence-assets/1.0", compact["schema_version"])
        self.assertEqual("/assets/compact-presence/manifest-v1.json", compact["manifest_path"])
        self.assertEqual(5, compact["source_revision"])
        self.assertEqual(
            "04b075c2ba609c08e8a39ca1936badc3c6153911",
            compact["source_commit"],
        )
        self.assertEqual(["idle", "verifying", "succeeded"], compact["states"])
        self.assertTrue(set(compact["states"]) <= canonical_states)
        self.assertEqual(
            profile["source_scene"]["proportion_profile"],
            compact["proportion_profile"],
        )
        self.assertEqual(
            profile["source_scene"]["material_profile"],
            compact["material_profile"],
        )
        self.assertTrue(compact["geometry_unchanged"])


if __name__ == "__main__":
    unittest.main()
