import json
import tempfile
import unittest
from pathlib import Path

from steward.p2_production_binding import (
    ProductionBindingContractError,
    ProductionBindingObservation,
    evaluate_production_binding,
    load_observation,
)


HEADS = {
    "runtime": "3a1018406f570f04fa40c86d649fe4e8b43db129",
    "works": "2365e7aab195fa9ec7bf3e2e56076731a72dbf39",
    "trust_gateway": "e7a693ea895ae0412f754eea5a291fc8ed3779a3",
    "aie": "4e3514b936d2d65433b6c51901afb56908abd545",
    "sentinel": "eb51f824af2279ee3eee5daa8572bd54a34b3ca8",
}

REPOS = {
    "runtime": "Aftergraph/runtime",
    "works": "Aftergraph/works-execution",
    "trust_gateway": "Aftergraph/trust-gateway",
    "aie": "Aftergraph/aie",
    "sentinel": "Aftergraph/sentinel",
}


def observation(**overrides):
    payload = {
        "schema": "steward.p2.production-binding/0.1",
        "execution_plane": "aftergraph-vds-production",
        "environment": "production",
        "owners": [
            {
                "owner": owner,
                "repository": REPOS[owner],
                "expected_sha": sha,
                "observed_sha": sha,
                "mode": "service" if owner in {"works", "trust_gateway"} else "module",
                "active": True,
                "deployment_evidence_ref": f"deploy:{owner}/exact-head",
                "health_or_invocation_evidence_ref": f"health:{owner}/exact-head",
            }
            for owner, sha in HEADS.items()
        ],
        "works_durable_state": True,
        "tg_adapter_runtime_enabled": True,
        "aie_action_time_revalidation_live": True,
        "scoped_credential_surrogation_live": True,
        "remote_git_readback_live": True,
        "independent_sentinel_live": True,
    }
    payload.update(overrides)
    return payload


class P2ProductionBindingTests(unittest.TestCase):
    def test_exact_production_observation_projects_ready_without_granting_authority(self):
        report = evaluate_production_binding(
            ProductionBindingObservation.from_wire(observation())
        )
        self.assertTrue(report.ready)
        self.assertEqual((), report.blockers)
        self.assertEqual(HEADS, dict(report.exact_owner_heads))
        wire = report.to_wire()
        self.assertFalse(wire["authority_granted"])
        self.assertFalse(wire["mission_accepted"])

    def test_sha_drift_and_inactive_owner_fail_closed(self):
        payload = observation()
        payload["owners"][0]["observed_sha"] = "f" * 40
        payload["owners"][1]["active"] = False
        report = evaluate_production_binding(
            ProductionBindingObservation.from_wire(payload)
        )
        self.assertFalse(report.ready)
        self.assertIn("owner_sha_mismatch:runtime", report.blockers)
        self.assertIn("owner_inactive:works", report.blockers)

    def test_missing_owner_and_missing_cross_plane_binding_fail_closed(self):
        payload = observation(
            owners=observation()["owners"][:-1],
            independent_sentinel_live=False,
        )
        report = evaluate_production_binding(
            ProductionBindingObservation.from_wire(payload)
        )
        self.assertFalse(report.ready)
        self.assertIn("owner_missing:sentinel", report.blockers)
        self.assertIn(
            "binding_missing:independent_sentinel_live",
            report.blockers,
        )

    def test_non_production_and_secret_bearing_documents_are_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingContractError, "environment must be production"
        ):
            ProductionBindingObservation.from_wire(
                observation(environment="staging")
            )

        secret_payload = observation()
        secret_payload["github_token"] = "should-never-be-in-evidence"
        with self.assertRaisesRegex(
            ProductionBindingContractError, "secret-bearing field forbidden"
        ):
            ProductionBindingObservation.from_wire(secret_payload)

    def test_loader_accepts_secret_free_exact_state_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binding.json"
            path.write_text(json.dumps(observation()), encoding="utf-8")
            loaded = load_observation(path)
        self.assertEqual("production", loaded.environment)
        self.assertEqual("aftergraph-vds-production", loaded.execution_plane)


if __name__ == "__main__":
    unittest.main()
