from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.adapters.works import (
    DispatchAcceptanceRequest,
    WorksClient,
    WorksContractError,
    WorksStaleAuthorityError,
    WorksUnavailableError,
)


CTX = "ctx_" + "a" * 32
TRACE = "trc_" + "b" * 32


def dispatch_request() -> DispatchAcceptanceRequest:
    return DispatchAcceptanceRequest(
        mission_id="mis_steward_p2",
        authority_ref="auth_" + "1" * 32,
        authority_epoch=7,
        runtime_dispatch_id="rtd_01",
        attempt_id="att_01",
        effect_id="eff_01",
        idempotency_key="idem_01",
        budget_ref="budget_01",
        budget_ceiling=100,
        checkpoint_id="checkpoint_01",
        evidence_root="evidence_01",
        verification_subject="git:sha256:candidate",
        causal_id="cause_01",
    )


def acceptance(req: DispatchAcceptanceRequest) -> dict:
    return {
        "works_execution_id": "wex_01",
        **req.to_wire(),
        "outcome": "ACCEPTED",
        "verified": False,
        "execution_context_id": CTX,
        "trace_id": TRACE,
    }


class Harness:
    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _run(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else None
                outer.requests.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "body": body,
                        "authorization": self.headers.get("Authorization"),
                    }
                )
                status, payload = outer.responder(self.command, self.path, body)
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            do_GET = _run
            do_POST = _run

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


class WorksAdapterTests(unittest.TestCase):
    def test_accept_dispatch_never_sends_works_owned_correlation_ids(self):
        req = dispatch_request()
        with Harness(lambda _m, _p, body: (200, acceptance(req))) as (h, url):
            result = WorksClient(url, "token").accept_dispatch("wrk_01", req)
        sent = h.requests[0]["body"]
        self.assertNotIn("execution_context_id", sent)
        self.assertNotIn("trace_id", sent)
        self.assertEqual(CTX, result.execution_context_id)
        self.assertEqual(TRACE, result.trace_id)
        self.assertEqual("Bearer token", h.requests[0]["authorization"])

    def test_invalid_server_minted_context_id_fails_closed(self):
        req = dispatch_request()
        bad = acceptance(req)
        bad["execution_context_id"] = "client_chosen"
        with Harness(lambda *_: (200, bad)) as (_h, url):
            with self.assertRaises(WorksContractError):
                WorksClient(url, "token").accept_dispatch("wrk_01", req)

    def test_stale_authority_is_typed_failure(self):
        req = dispatch_request()
        def responder(*_):
            return 409, {"error": "dispatch_stale_authority", "detail": "epoch advanced"}
        with Harness(responder) as (_h, url):
            with self.assertRaises(WorksStaleAuthorityError):
                WorksClient(url, "token").accept_dispatch("wrk_01", req)

    def test_unwired_acceptance_surface_is_fail_closed(self):
        req = dispatch_request()
        def responder(*_):
            return 503, {"error": "dispatch_accept_unavailable", "detail": "resolver missing"}
        with Harness(responder) as (_h, url):
            with self.assertRaises(WorksUnavailableError):
                WorksClient(url, "token").accept_dispatch("wrk_01", req)

    def test_response_cannot_change_verification_subject(self):
        req = dispatch_request()
        bad = acceptance(req)
        bad["verification_subject"] = "git:sha256:other"
        with Harness(lambda *_: (200, bad)) as (_h, url):
            with self.assertRaises(WorksContractError):
                WorksClient(url, "token").accept_dispatch("wrk_01", req)

    def test_event_cursor_uses_canonical_rest_surface(self):
        def responder(_m, path, _body):
            self.assertEqual("/v1/works/wrk_01/events?after=12&limit=25", path)
            return 200, {"events": []}
        with Harness(responder) as (_h, url):
            result = WorksClient(url, "token").list_events("wrk_01", after=12, limit=25)
        self.assertEqual({"events": []}, result)

    def test_request_rejects_negative_contract_minimums(self):
        data = dispatch_request().__dict__ | {"authority_epoch": -1}
        with self.assertRaises(WorksContractError):
            DispatchAcceptanceRequest(**data).to_wire()


if __name__ == "__main__":
    unittest.main()
