import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.runtime import (
    RuntimeContractError,
    RuntimeDispatchV2Request,
    RuntimeRejectedError,
    RuntimeV2Port,
    SubprocessRuntimeTransport,
)


def request():
    return RuntimeDispatchV2Request(
        work_id="wrk_" + "1" * 32,
        organization_id="org_" + "2" * 32,
        tenant_id="ten_" + "3" * 32,
        principal_id="prn_" + "4" * 32,
        mission_id="mis_example",
        authority_lease_id="auth_" + "5" * 32,
        worker_lease_id="lse_" + "6" * 32,
        admission_decision_id="pdr_" + "7" * 32,
        attempt_id="attempt/1",
        effect_id="effect/1",
        idempotency_key="idem/v2/1",
        budget_ref="budget/1",
        budget_ceiling=100,
        checkpoint_id="checkpoint/1",
        evidence_root="evidence/1",
        causal_id="causal/1",
    )


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def dispatch(self, payload):
        self.calls.append(dict(payload))
        return self.response


def receipt():
    return {
        "runtimeDispatchId": "rdisp/abc",
        "worksExecutionId": "wexec/idem/v2/1",
        "workId": "wrk_" + "1" * 32,
        "executionContextId": "ctx_" + "a" * 32,
        "traceId": "trc_" + "b" * 32,
        "workerId": "wrkr_" + "8" * 32,
    }


class RuntimeV2PortTests(unittest.TestCase):
    def test_v2_request_has_no_authority_epoch_or_client_correlation(self):
        wire = request().to_runtime_wire()
        self.assertNotIn("authorityEpoch", wire)
        self.assertNotIn("executionContextId", wire)
        self.assertNotIn("traceId", wire)
        self.assertNotIn("workerId", wire)
        self.assertNotIn("verificationSubject", wire)
        self.assertEqual("auth_" + "5" * 32, wire["authorityLeaseId"])
        self.assertEqual("lse_" + "6" * 32, wire["workerLeaseId"])

    def test_v2_port_adopts_materialized_runtime_receipt(self):
        transport = FakeTransport(receipt())
        got = RuntimeV2Port(transport).dispatch(request())
        self.assertEqual("ctx_" + "a" * 32, got.execution_context_id)
        self.assertEqual("trc_" + "b" * 32, got.trace_id)
        self.assertEqual("wrkr_" + "8" * 32, got.worker_id)

    def test_wrong_lease_grammar_fails_before_transport(self):
        bad = RuntimeDispatchV2Request(
            **(request().__dict__ | {"worker_lease_id": "auth_" + "5" * 32})
        )
        transport = FakeTransport(receipt())
        with self.assertRaises(RuntimeContractError):
            RuntimeV2Port(transport).dispatch(bad)
        self.assertEqual([], transport.calls)

    def test_receipt_rebinding_to_other_work_fails_closed(self):
        transport = FakeTransport(receipt() | {"workId": "wrk_" + "9" * 32})
        with self.assertRaises(RuntimeContractError):
            RuntimeV2Port(transport).dispatch(request())

    def test_malformed_materialized_context_fails_closed(self):
        transport = FakeTransport(receipt() | {"executionContextId": "ctx_short"})
        with self.assertRaises(RuntimeContractError):
            RuntimeV2Port(transport).dispatch(request())


class RuntimeV2SubprocessTests(unittest.TestCase):
    def test_v2_cli_keeps_all_works_credentials_out_of_payload(self):
        script = (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "assert 'WORKS_BEARER_TOKEN' not in req;"
            "assert 'WORKS_BASE_URL' not in req;"
            "assert 'WORKS_PLATFORM_BRIDGE_SECRET' not in req;"
            "assert 'authorityEpoch' not in req;"
            "print(json.dumps({'ok':True,'receipt':{"
            "'runtimeDispatchId':'rdisp/abc','worksExecutionId':'wexec/1',"
            "'workId':'wrk_'+'1'*32,'executionContextId':'ctx_'+'a'*32,"
            "'traceId':'trc_'+'b'*32,'workerId':'wrkr_'+'8'*32}}))"
        )
        transport = SubprocessRuntimeTransport(
            (sys.executable, "-c", script),
            environment={
                "WORKS_BASE_URL": "https://works.invalid",
                "WORKS_BEARER_TOKEN": "secret-token",
                "WORKS_PLATFORM_BRIDGE_SECRET": "bridge-secret",
            },
        )
        got = RuntimeV2Port(transport).dispatch(request())
        self.assertEqual("wexec/1", got.works_execution_id)

    def test_v2_cli_rejection_is_typed(self):
        encoded = json.dumps({"ok": False, "reason": "works_unavailable"})
        script = (
            "import json,sys;"
            "json.load(sys.stdin);"
            f"print({encoded!r});"
            "sys.exit(1)"
        )
        transport = SubprocessRuntimeTransport((sys.executable, "-c", script))
        with self.assertRaises(RuntimeRejectedError):
            RuntimeV2Port(transport).dispatch(request())


if __name__ == "__main__":
    unittest.main()
