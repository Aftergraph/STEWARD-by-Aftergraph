import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MOTIONS = {
    "idle": "ambient_breathe",
    "thinking": "visor_attention",
    "planning": "ordered_scan",
    "executing": "forward_action",
    "inspecting": "focus_scan",
    "waiting": "slow_hold",
    "blocked": "boundary_stop",
    "approval": "attention_gate",
    "verifying": "custody_ring_raise",
    "approving": "bounded_confirm",
    "succeeded": "settled_confirm",
    "failed": "bounded_break",
}

EXPECTED_ACCENTS = {
    "idle": "steward_copper",
    "thinking": "steward_copper",
    "planning": "system_blue",
    "executing": "decision_amber",
    "inspecting": "control_cyan",
    "waiting": "slate",
    "blocked": "decision_amber",
    "approval": "authority_violet",
    "verifying": "pine_teal",
    "approving": "authority_violet",
    "succeeded": "moss",
    "failed": "decision_amber",
}


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
        self.assertEqual(canonical_states, profile["motion_runtime"]["states"])

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
        self.assertEqual("04b075c2ba609c08e8a39ca1936badc3c6153911", compact["source_commit"])
        self.assertEqual(["idle", "verifying", "succeeded"], compact["states"])
        self.assertTrue(set(compact["states"]) <= canonical_states)
        self.assertEqual(profile["source_scene"]["proportion_profile"], compact["proportion_profile"])
        self.assertEqual(profile["source_scene"]["material_profile"], compact["material_profile"])
        self.assertTrue(compact["geometry_unchanged"])

    def test_motion_runtime_is_exactly_bound_to_brand_contract(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        motion = profile["motion_runtime"]
        self.assertEqual("Aftergraph/brand", motion["contract_owner"])
        self.assertEqual("steward.presence.v1", motion["contract_id"])
        self.assertEqual("steward.motion-runtime/2.0", motion["runtime_version"])
        self.assertEqual("/assets/motion/presence-runtime-v2.json", motion["manifest_path"])
        self.assertEqual(
            "047464f20b75763d14d969fbb14fa16780a7d6dfdb554cb3a90e9e8809e92378",
            motion["manifest_sha256"],
        )
        self.assertEqual("4c71ce1322281056c70dd896abefc03936fd43f6", motion["source_commit"])
        self.assertEqual(EXPECTED_MOTIONS, motion["motions"])
        self.assertEqual(EXPECTED_ACCENTS, motion["accent_tokens"])

    def test_motion_runtime_respects_brand_bounds_and_reduced_motion(self):
        motion = self._read("fixtures/valid/visual-frontier-profile.json")["motion_runtime"]
        self.assertEqual((160, 420), (motion["transition_ms_min"], motion["transition_ms_max"]))
        self.assertEqual((3.5, 5.5), (motion["blink_seconds_min"], motion["blink_seconds_max"]))
        self.assertEqual(6, motion["pointer_orientation_max_degrees"])
        self.assertEqual(
            {
                "continuous_motion": False,
                "transition_ms": 0,
                "preserve_state_label": True,
                "preserve_final_pose": True,
            },
            motion["reduced_motion"],
        )

    def test_motion_runtime_qa_evidence_is_complete(self):
        qa = self._read("fixtures/valid/visual-frontier-profile.json")["motion_runtime"]["qa"]
        self.assertTrue(all(qa.values()))

    def test_presence_inspector_binds_only_to_existing_motion_runtime(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        inspector = profile["presence_inspector"]
        motion = profile["motion_runtime"]
        self.assertEqual("steward.presence-inspector/1.0", inspector["surface_id"])
        self.assertEqual("12131e6fe54d8664bb4bb1977073036fbc50bb6a", inspector["source_commit"])
        self.assertEqual("motion_runtime.states", inspector["state_source"])
        self.assertEqual("motion_runtime.motions", inspector["motion_source"])
        self.assertEqual(len(motion["states"]), inspector["control_count"])
        self.assertEqual(12, inspector["control_count"])
        self.assertEqual("presence", inspector["router_search_key"])
        self.assertEqual("StewardThreeHero.mode", inspector["hero_binding"])

    def test_presence_inspector_is_explicitly_projection_only(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        inspector = profile["presence_inspector"]
        self.assertEqual(
            "Visual preview only · canonical state is untouched",
            inspector["truth_boundary_copy"],
        )
        self.assertFalse(profile["presentation_boundary"]["canonical_truth"])
        self.assertFalse(profile["presentation_boundary"]["authority_effect"])
        self.assertFalse(profile["presentation_boundary"]["verification_effect"])

    def test_presence_inspector_qa_evidence_is_complete(self):
        qa = self._read("fixtures/valid/visual-frontier-profile.json")["presence_inspector"]["qa"]
        self.assertEqual(7, len(qa))
        self.assertTrue(all(qa.values()))


if __name__ == "__main__":
    unittest.main()
