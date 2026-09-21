import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from steward.p2_frontier import inspect_p2_frontier, main
from steward.p2_production_binding import ProductionBindingObservation


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


def production_payload():
    return {
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


def live_environment():
    return {
        "STEWARD_RUNTIME_COMMAND": "runtime-cli dispatch",
        "STEWARD_TRUST_GATEWAY_URL": "https://trust-gateway.internal",
        "STEWARD_TRUST_GATEWAY_TOKEN": "never-print-this-secret",
        "STEWARD_HABITAT_COMMAND": "habitat-cli run",
        "STEWARD_SENTINEL_COMMAND": "sentinel-cli verify",
    }


class P2FrontierTests(unittest.TestCase):
    def test_empty_frontier_is_blocked_and_secret_free(self):
        report = inspect_p2_frontier(None, {})
        self.assertEqual("BLOCKED", report.state)
        self.assertIn("production_observation_missing", report.blockers)
        self.assertFalse(report.to_wire()["execution_attempted"])
        self.assertFalse(report.to_wire()["authority_granted"])
        self.assertFalse(report.to_wire()["mission_accepted"])

    @patch("steward.p2_live_readiness.shutil.which", return_value="/bin/resolved")
    def test_exact_binding_and_live_environment_are_ready_to_attempt_only(self, _which):
        observation = ProductionBindingObservation.from_wire(production_payload())
        report = inspect_p2_frontier(observation, live_environment())
        wire = report.to_wire()

        self.assertEqual("READY_TO_ATTEMPT", report.state)
        self.assertEqual([], wire["blockers"])
        self.assertTrue(wire["ready_to_attempt_golden_mission"])
        self.assertFalse(wire["execution_attempted"])
        self.assertFalse(wire["authority_granted"])
        self.assertFalse(wire["mission_accepted"])
        self.assertNotIn("never-print-this-secret", json.dumps(wire))

    @patch("steward.p2_live_readiness.shutil.which", return_value="/bin/resolved")
    def test_production_sha_drift_blocks_frontier(self, _which):
        payload = production_payload()
        payload["owners"][0]["observed_sha"] = "f" * 40
        report = inspect_p2_frontier(
            ProductionBindingObservation.from_wire(payload),
            live_environment(),
        )
        self.assertEqual("BLOCKED", report.state)
        self.assertIn("production:owner_sha_mismatch:runtime", report.blockers)

    def test_invalid_secret_bearing_observation_fails_closed_without_echoing_value(self):
        payload = production_payload()
        payload["github_token"] = "super-secret-value"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binding.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch("sys.stdout") as stdout:
                code = main([str(path)])
        self.assertEqual(2, code)
        rendered = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertIn("secret-bearing field forbidden", rendered)
        self.assertNotIn("super-secret-value", rendered)

    @patch("steward.p2_live_readiness.shutil.which", return_value="/bin/resolved")
    def test_live_binding_gap_blocks_even_when_production_observation_is_green(self, _which):
        observation = ProductionBindingObservation.from_wire(production_payload())
        env = live_environment()
        del env["STEWARD_TRUST_GATEWAY_TOKEN"]
        report = inspect_p2_frontier(observation, env)
        self.assertEqual("BLOCKED", report.state)
        self.assertIn("live:trust_gateway_token:binding_missing", report.blockers)


if __name__ == "__main__":
    unittest.main()
