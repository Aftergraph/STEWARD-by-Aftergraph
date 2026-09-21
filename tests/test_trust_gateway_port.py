from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.trust_gateway import (
    TrustGatewayActionRequest,
    TrustGatewayApprovalRequired,
    TrustGatewayClient,
    TrustGatewayContractError,
    TrustGatewayDeniedError,
    TrustGatewayUnavailableError,
)


ACTION = "act_" + "1" * 32
CTX = "ctx_" + "2" * 32
PDR = "pdr_" + "3" * 32


def action() -> TrustGatewayActionRequest:
    return TrustGatewayActionRequest(
        action_id=ACTION,
        execution_context_id=CTX,
        mission_id="mis_example",
        tool="fs.read:x",
        args={"path": "x"},
    )


class Harness:
    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length else None
                outer.requests.append(
                    {
                        "path": self.path,
                        "body": body,
                        "authorization": self.headers.get("Authorization"),
                    }
                )
                status, payload = outer.responder(body)
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        host, port = self.server.server_address
        return self, f"http://{host}:{port}"

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class TrustGatewayPortTests(unittest.TestCase):
    def test_client_always_uses_v21_context_bound_action_surface(self):
        def responder(body):
            self.assertEqual(ACTION, body["action_id"])
            self.assertEqual(CTX, body["execution_context_id"])
            return 200, {
                "decision": "allow",
                "admission_decision_id": "adm_1",
                "execution_context_id": CTX,
                "execution_pdr_id": PDR,
                "result": {"ok": True},
            }

        with Harness(responder) as (h, url):
            receipt = TrustGatewayClient(url, "token").execute(action())
        self.assertEqual("/v1/actions", h.requests[0]["path"])
        self.assertEqual("Bearer token", h.requests[0]["authorization"])
        self.assertEqual(PDR, receipt.execution_pdr_id)

    def test_missing_execution_context_is_rejected_before_transport(self):
        bad = TrustGatewayActionRequest(
            action_id=ACTION,
            execution_context_id="",
            mission_id="mis_example",
            tool="fs.read:x",
        )
        with self.assertRaises(TrustGatewayContractError):
            bad.to_wire()

    def test_context_mismatch_in_allow_response_fails_closed(self):
        with Harness(lambda _body: (200, {
            "decision": "allow",
            "admission_decision_id": "adm_1",
            "execution_context_id": "ctx_" + "a" * 32,
            "execution_pdr_id": PDR,
            "result": {},
        })) as (_h, url):
            with self.assertRaises(TrustGatewayContractError):
                TrustGatewayClient(url, "token").execute(action())

    def test_revocation_is_denial_not_success(self):
        with Harness(lambda _body: (403, {
            "decision": "deny",
            "error": "authority_revoked",
            "error_code": "AIE-AUTH-003",
        })) as (_h, url):
            with self.assertRaises(TrustGatewayDeniedError) as ctx:
                TrustGatewayClient(url, "token").execute(action())
        self.assertEqual("authority_revoked", ctx.exception.code)
        self.assertEqual("AIE-AUTH-003", ctx.exception.error_code)

    def test_works_correlation_failure_is_unavailable_and_has_no_fallback(self):
        with Harness(lambda _body: (503, {
            "decision": "deny",
            "error": "works_evidence_correlation_failed",
            "error_code": "works_unreachable",
        })) as (h, url):
            with self.assertRaises(TrustGatewayUnavailableError):
                TrustGatewayClient(url, "token").execute(action())
        self.assertEqual(1, len(h.requests))

    def test_needs_approval_is_first_class(self):
        with Harness(lambda _body: (202, {
            "decision": "needs_approval",
            "approvalId": "approval_1",
            "reason": "destructive",
        })) as (_h, url):
            result = TrustGatewayClient(url, "token").execute(action())
        self.assertIsInstance(result, TrustGatewayApprovalRequired)
        self.assertEqual("approval_1", result.approval_id)

    def test_aie_unreachable_fails_closed(self):
        with Harness(lambda _body: (502, {
            "decision": "deny",
            "error": "aie_unreachable",
        })) as (_h, url):
            with self.assertRaises(TrustGatewayUnavailableError):
                TrustGatewayClient(url, "token").execute(action())


if __name__ == "__main__":
    unittest.main()
