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

    def test_persona_visual_roles_match_actor_persona_schema_exactly(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        actor_schema = self._read("schemas/actor-persona.schema.json")
        canonical_roles = actor_schema["properties"]["role"]["enum"]
        visual_roles = profile["persona_roles"]["roles"]
        self.assertEqual(canonical_roles, visual_roles)
        self.assertEqual(6, len(visual_roles))

    def test_persona_visual_roles_are_same_rig_projection_only(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        persona = profile["persona_roles"]
        self.assertEqual("steward.persona-role-assets/1.0", persona["schema_version"])
        self.assertEqual("/assets/persona-roles/manifest-v1.json", persona["manifest_path"])
        self.assertEqual(
            "7ba7453e8c6ef610dee90aa74fc4966da83c5e425cfd9972e50c2152571bba09",
            persona["manifest_sha256"],
        )
        self.assertEqual(5, persona["source_revision"])
        self.assertEqual(
            "b88ce626ea5f7aa70439da71600c25a9a6e24c27",
            persona["source_commit"],
        )
        self.assertFalse(persona["authority_effect"])
        self.assertFalse(persona["verification_effect"])
        self.assertFalse(profile["presentation_boundary"]["authority_effect"])
        self.assertFalse(profile["presentation_boundary"]["verification_effect"])

    def test_persona_visual_assets_are_exactly_pinned(self):
        persona = self._read("fixtures/valid/visual-frontier-profile.json")["persona_roles"]
        self.assertEqual(
            {
                "reviewer": "control_cyan",
                "subscriber": "system_blue",
                "maintainer": "steward_copper",
                "observer": "slate",
                "auditor": "pine_teal",
                "integrator": "decision_amber",
            },
            persona["accent_tokens"],
        )
        self.assertEqual(6, len(persona["asset_sha256"]))
        for digest in persona["asset_sha256"].values():
            self.assertEqual(64, len(digest))

    def test_persona_visual_qa_evidence_is_complete(self):
        qa = self._read("fixtures/valid/visual-frontier-profile.json")["persona_roles"]["qa"]
        self.assertEqual(7, len(qa))
        self.assertTrue(all(qa.values()))

    def test_role_state_composition_is_cartesian_product_of_canonical_axes(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        composition = profile["role_state_composition"]
        self.assertEqual(profile["persona_roles"]["roles"], self._read("schemas/actor-persona.schema.json")["properties"]["role"]["enum"])
        self.assertEqual(profile["motion_runtime"]["states"], self._read("schemas/presence-projection.schema.json")["properties"]["displayed_state"]["enum"])
        self.assertEqual(len(profile["persona_roles"]["roles"]), composition["role_count"])
        self.assertEqual(len(profile["motion_runtime"]["states"]), composition["state_count"])
        self.assertEqual(
            composition["role_count"] * composition["state_count"],
            composition["combination_count"],
        )
        self.assertEqual(72, composition["combination_count"])

    def test_role_and_state_visual_channels_are_orthogonal(self):
        composition = self._read("fixtures/valid/visual-frontier-profile.json")["role_state_composition"]
        self.assertEqual(["badge_accent"], composition["role_channel"])
        self.assertEqual(
            ["pose", "eyes", "custody_node", "halo_nodes", "rim_signal"],
            composition["state_channel"],
        )
        self.assertEqual(
            ["core_silhouette", "visor", "halo_geometry", "custody_ring_geometry"],
            composition["identity_channel"],
        )
        self.assertTrue(set(composition["role_channel"]).isdisjoint(composition["state_channel"]))
        self.assertTrue(set(composition["identity_channel"]).isdisjoint(composition["role_channel"]))
        self.assertTrue(set(composition["identity_channel"]).isdisjoint(composition["state_channel"]))

    def test_role_state_composition_is_exactly_pinned_and_projection_only(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        composition = profile["role_state_composition"]
        self.assertEqual("steward.role-state-composition/1.0", composition["schema_version"])
        self.assertEqual("/assets/motion/role-state-composition-v1.json", composition["manifest_path"])
        self.assertEqual(
            "629fa301a67ddb30fd047d73f0892cd3dc08f76616b49659f701fcaeb941cc2b",
            composition["manifest_sha256"],
        )
        self.assertEqual(
            "4f01ab0b298b83d6a9033e68c758d0a5e24bece2",
            composition["source_commit"],
        )
        self.assertEqual("state-semantic-priority", composition["fallback"])
        self.assertFalse(composition["canonical_truth"])
        self.assertFalse(composition["authority_effect"])
        self.assertFalse(composition["verification_effect"])

    def test_role_state_composition_qa_covers_all_72_combinations(self):
        qa = self._read("fixtures/valid/visual-frontier-profile.json")["role_state_composition"]["qa"]
        self.assertEqual(72, qa["combinations_checked"])
        self.assertTrue(qa["all_combinations_pass"])
        self.assertTrue(qa["no_role_fallback_pass"])
        self.assertTrue(qa["console_errors_zero"])
        self.assertTrue(qa["network_errors_zero"])

    def test_persona_accessory_runtime_matches_canonical_roles_and_brand_contract(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        accessory = profile["persona_accessory_runtime"]
        canonical_roles = self._read("schemas/actor-persona.schema.json")["properties"]["role"]["enum"]
        self.assertEqual("Aftergraph/brand", accessory["contract_owner"])
        self.assertEqual("steward.persona-role-visual/1.0", accessory["role_contract"])
        self.assertEqual(canonical_roles, accessory["roles"])
        self.assertEqual(profile["persona_roles"]["roles"], accessory["roles"])
        self.assertEqual(
            {
                "reviewer": "review-check",
                "subscriber": "attention-signal",
                "maintainer": "maintenance-tool",
                "observer": "read-only-lens",
                "auditor": "evidence-lens",
                "integrator": "contract-bridge",
            },
            accessory["accessories"],
        )
        self.assertEqual(6, len(set(accessory["accessories"].values())))

    def test_persona_accessory_runtime_is_exactly_pinned(self):
        accessory = self._read("fixtures/valid/visual-frontier-profile.json")["persona_accessory_runtime"]
        self.assertEqual("steward.persona-role-accessory-runtime/1.0", accessory["schema_version"])
        self.assertEqual("/assets/motion/persona-role-accessories-v1.json", accessory["manifest_path"])
        self.assertEqual(
            "37c62a36e7b8fba3e609a102a5a8fc68c5a8cec6a57bcdc9329aa46cde38d10e",
            accessory["manifest_sha256"],
        )
        self.assertEqual("02d7095b657c6ffaf98f0d204f2cdcb67d811bed", accessory["source_commit"])
        self.assertEqual(5, accessory["source_revision"])
        self.assertEqual("STEWARD_Rig", accessory["rig"])
        self.assertEqual("badge", accessory["anchor"])

    def test_persona_accessory_channels_preserve_role_state_identity_orthogonality(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        accessory = profile["persona_accessory_runtime"]
        self.assertEqual(["badge_accent", "functional_accessory"], accessory["role_channel"])
        self.assertEqual(
            ["pose", "eyes", "custody_node", "halo_nodes", "rim_signal"],
            accessory["state_channel"],
        )
        self.assertEqual(
            ["core_silhouette", "visor", "halo_geometry", "custody_ring_geometry"],
            accessory["identity_channel"],
        )
        self.assertTrue(set(accessory["role_channel"]).isdisjoint(accessory["state_channel"]))
        self.assertTrue(set(accessory["identity_channel"]).isdisjoint(accessory["role_channel"]))
        self.assertTrue(set(accessory["identity_channel"]).isdisjoint(accessory["state_channel"]))
        self.assertEqual("state-semantic-priority", accessory["fallback"])

    def test_persona_accessory_runtime_is_projection_only_and_qa_complete(self):
        profile = self._read("fixtures/valid/visual-frontier-profile.json")
        accessory = profile["persona_accessory_runtime"]
        self.assertFalse(accessory["canonical_truth"])
        self.assertFalse(accessory["authority_effect"])
        self.assertFalse(accessory["verification_effect"])
        self.assertFalse(profile["presentation_boundary"]["canonical_truth"])
        self.assertFalse(profile["presentation_boundary"]["authority_effect"])
        self.assertFalse(profile["presentation_boundary"]["verification_effect"])
        self.assertEqual(
            {
                "roles_checked": 6,
                "unique_role_render_hashes": 6,
                "critical_state_priority_cases": 4,
                "reduced_motion": True,
                "forced_glb_fallback": True,
                "console_errors_zero": True,
                "network_errors_zero": True,
            },
            accessory["qa"],
        )


if __name__ == "__main__":
    unittest.main()
