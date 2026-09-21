import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.runtime import (
    RuntimeContractError,
    RuntimeDispatchRequest,
    RuntimePort,
    RuntimeRejectedError,
    RuntimeUnavailableError,
    SubprocessRuntimeTransport,
)


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def dispatch(self, payload):
        self.calls.append(dict(payload))
        if self.error is not None:
            raise self.error
        return self.response


def request():
    return RuntimeDispatchRequest(
        work_id="wrk_01",
        mission_id="mis_p2",
        authority_ref="auth_" + "1" * 32,
        authority_epoch=8,
        attempt_id="att_1",
        effect_id="eff_1",
        idempotency_key="idem_1",
        budget_ref="budget_1",
        budget_ceiling=50,
        checkpoint_id="cp_1",
        evidence_root="evidence_1",
        verification_subject="git:sha:abc",
        causal_id="cause_1",
    )


class RuntimePortTests(unittest.TestCase):
    def test_request_does_not_mint_runtime_or_works_owned_ids(self):
        wire = request().to_runtime_wire()
        self.assertEqual("wrk_01", wire["workId"])
        self.assertNotIn("runtimeDispatchId", wire)
        self.assertNotIn("executionContextId", wire)
        self.assertNotIn("traceId", wire)
        self.assertNotIn("verified", wire)
        self.assertEqual("runtime.dispatch-seal/0.1", wire["schema"])

    def test_receipt_adopts_runtime_and_works_correlation(self):
        transport = FakeTransport({
            "runtimeDispatchId": "rdisp/idem",
            "worksExecutionId": "wexec/idem",
            "executionContextId": "ctx_" + "a" * 32,
            "traceId": "trc_" + "b" * 32,
        })
        receipt = RuntimePort(transport).dispatch(request())
        self.assertEqual("rdisp/idem", receipt.runtime_dispatch_id)
        self.assertEqual("wexec/idem", receipt.works_execution_id)
        self.assertEqual(1, len(transport.calls))

    def test_malformed_correlation_fails_closed(self):
        transport = FakeTransport({
            "runtimeDispatchId": "rdisp/idem",
            "worksExecutionId": "wexec/idem",
            "executionContextId": "ctx_short",
        })
        with self.assertRaises(RuntimeContractError):
            RuntimePort(transport).dispatch(request())

    def test_transport_failure_has_no_local_bypass(self):
        transport = FakeTransport(error=OSError("down"))
        with self.assertRaises(RuntimeUnavailableError):
            RuntimePort(transport).dispatch(request())
        self.assertEqual(1, len(transport.calls))

    def test_negative_budget_fails_before_transport(self):
        bad = RuntimeDispatchRequest(**(request().__dict__ | {"budget_ceiling": -1}))
        transport = FakeTransport({})
        with self.assertRaises(RuntimeContractError):
            RuntimePort(transport).dispatch(bad)
        self.assertEqual([], transport.calls)


class SubprocessRuntimeTransportTests(unittest.TestCase):
    def _echo_command(self, response, exit_code=0):
        encoded = json.dumps(response)
        script = (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            f"payload=json.loads({encoded!r});"
            "print(json.dumps(payload));"
            f"sys.exit({exit_code})"
        )
        return (sys.executable, "-c", script)

    def test_cli_transport_maps_canonical_runtime_receipt(self):
        response = {
            "ok": True,
            "receipt": {
                "runtimeDispatchId": "rdisp/idem",
                "worksExecutionId": "wexec/idem",
                "executionContextId": "ctx_" + "a" * 32,
                "traceId": "trc_" + "b" * 32,
            },
        }
        transport = SubprocessRuntimeTransport(self._echo_command(response))
        receipt = RuntimePort(transport).dispatch(request())
        self.assertEqual("rdisp/idem", receipt.runtime_dispatch_id)
        self.assertEqual("wexec/idem", receipt.works_execution_id)

    def test_cli_transport_keeps_credentials_out_of_request_payload(self):
        script = (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "assert 'WORKS_BEARER_TOKEN' not in req;"
            "assert 'WORKS_BASE_URL' not in req;"
            "print(json.dumps({'ok':True,'receipt':{"
            "'runtimeDispatchId':'rdisp/1','worksExecutionId':'wexec/1',"
            "'executionContextId':'ctx_'+'a'*32,'traceId':'trc_'+'b'*32}}))"
        )
        transport = SubprocessRuntimeTransport(
            (sys.executable, "-c", script),
            environment={
                "WORKS_BASE_URL": "https://works.invalid",
                "WORKS_BEARER_TOKEN": "secret-test-token",
            },
        )
        receipt = RuntimePort(transport).dispatch(request())
        self.assertEqual("rdisp/1", receipt.runtime_dispatch_id)

    def test_cli_rejection_is_typed_and_never_bypassed(self):
        transport = SubprocessRuntimeTransport(
            self._echo_command({"ok": False, "reason": "stale_authority"}, 1)
        )
        with self.assertRaises(RuntimeRejectedError) as ctx:
            RuntimePort(transport).dispatch(request())
        self.assertEqual("stale_authority", ctx.exception.reason)

    def test_cli_non_json_output_fails_closed(self):
        script = "print('not-json')"
        transport = SubprocessRuntimeTransport((sys.executable, "-c", script))
        with self.assertRaises(RuntimeContractError):
            RuntimePort(transport).dispatch(request())


if __name__ == "__main__":
    unittest.main()
