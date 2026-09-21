from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.runtime import (
    RuntimeContractError,
    RuntimeDispatchRequest,
    RuntimePort,
    RuntimeUnavailableError,
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


if __name__ == "__main__":
    unittest.main()
