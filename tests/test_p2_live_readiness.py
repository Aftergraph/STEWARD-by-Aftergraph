import json
import unittest
from unittest.mock import patch

from steward.p2_live_readiness import inspect_live_readiness, main


class LiveReadinessTests(unittest.TestCase):
    def test_empty_environment_is_explicitly_blocked(self):
        report = inspect_live_readiness({})
        self.assertEqual("BLOCKED", report.state)
        self.assertTrue(all(not check.ready for check in report.checks))

    def test_secret_values_never_appear_in_report(self):
        secret = "tg-super-secret-value"
        report = inspect_live_readiness({"STEWARD_TRUST_GATEWAY_TOKEN": secret})
        self.assertNotIn(secret, report.to_json())
        token = next(c for c in report.checks if c.name == "trust_gateway_token")
        self.assertEqual("secret_present", token.reason)

    def test_invalid_url_and_missing_commands_fail_closed(self):
        report = inspect_live_readiness({"STEWARD_TRUST_GATEWAY_URL": "file:///tmp/tg"})
        by_name = {check.name: check for check in report.checks}
        self.assertEqual("invalid_http_url", by_name["trust_gateway_url"].reason)
        self.assertEqual("binding_missing", by_name["runtime_command"].reason)

    def test_complete_resolvable_bindings_are_ready(self):
        env = {
            "STEWARD_RUNTIME_COMMAND": "runtime-steward-dispatch-v2",
            "STEWARD_TRUST_GATEWAY_URL": "https://tg.example",
            "STEWARD_TRUST_GATEWAY_TOKEN": "secret",
            "STEWARD_HABITAT_COMMAND": "aftergraph-habitat",
            "STEWARD_SENTINEL_COMMAND": "aftergraph-sentinel",
        }
        with patch("steward.p2_live_readiness.shutil.which", return_value="/bin/owner"):
            report = inspect_live_readiness(env)
        self.assertEqual("READY", report.state)
        self.assertTrue(all(check.ready for check in report.checks))

    def test_cli_returns_two_and_machine_readable_json_when_blocked(self):
        with patch.dict("os.environ", {}, clear=True), patch("builtins.print") as emit:
            self.assertEqual(2, main([]))
        payload = json.loads(emit.call_args.args[0])
        self.assertEqual("steward.p2.live-readiness/0.1", payload["schema"])
        self.assertEqual("BLOCKED", payload["state"])


if __name__ == "__main__":
    unittest.main()
