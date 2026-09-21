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
    DispatchAcceptanceV2Request,
    VerificationSubjectBindingRequest,
    WorksClient,
    WorksContractError,
    WorksStaleAuthorityError,
    WorksUnavailableError,
)


CTX = "ctx_" + "a" * 32
TRACE = "trc_" + "b" * 32

WORK_ID = "wrk_" + "c" * 32
V2_CTX = "ctx_" + "d" * 32
V2_TRACE = "trc_" + "e" * 32


def dispatch_v2_request() -> DispatchAcceptanceV2Request:
    return DispatchAcceptanceV2Request(
        organization_id="org_" + "1" * 32,
        tenant_id="ten_" + "2" * 32,
        principal_id="prn_" + "3" * 32,
        mission_id="mis_steward_p2",
        authority_lease_id="auth_" + "4" * 32,
        worker_lease_id="lse_" + "5" * 32,
        admission_decision_id="pdr_" + "6" * 32,
        runtime_dispatch_id="rtd_v2_01",
        attempt_id="att_v2_01",
        effect_id="eff_v2_01",
        idempotency_key="idem_v2_01",
        budget_ref="budget_v2_01",
        budget_ceiling=100,
        checkpoint_id="checkpoint_v2_01",
        evidence_root="evidence_v2_01",
        causal_id="cause_v2_01",
    )


def acceptance_v2(req: DispatchAcceptanceV2Request, work_id: str = WORK_ID) -> dict:
    return {
        "schema": "dispatch.acceptance/2.0",
        "work_id": work_id,
        "works_execution_id": "wexec/idem_v2_01",
        "request": req.to_wire(),
        "execution_context": {
            "schema": "execution-context/1.0",
            "execution_context_id": V2_CTX,
            "organization_id": req.organization_id,
            "tenant_id": req.tenant_id,
            "principal_id": req.principal_id,
            "mission_id": req.mission_id,
            "authority_lease_id": req.authority_lease_id,
            "work_id": work_id,
            "worker_id": "wrkr_" + "7" * 32,
            "worker_lease_id": req.worker_lease_id,
            "admission_decision_id": req.admission_decision_id,
            "trace_id": V2_TRACE,
        },
        "outcome": "ACCEPTED",
        "verified": False,
    }




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
                        "bridge": self.headers.get("X-Works-Platform-Bridge"),
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

    def test_accept_dispatch_v2_uses_platform_boundary_and_works_mints_context(self):
        req = dispatch_v2_request()
        with Harness(lambda _m, _p, _body: (200, acceptance_v2(req))) as (h, url):
            result = WorksClient(
                url,
                "worker-token",
                platform_token="platform-token",
                bridge_secret="bridge-secret",
            ).accept_dispatch_v2(WORK_ID, req)
        sent = h.requests[0]
        self.assertEqual("/v2/works/" + WORK_ID + "/accept", sent["path"])
        self.assertEqual("Bearer platform-token", sent["authorization"])
        self.assertEqual("bridge-secret", sent["bridge"])
        self.assertEqual("dispatch.acceptance/2.0", sent["body"]["schema"])
        self.assertNotIn("authority_epoch", sent["body"])
        self.assertNotIn("execution_context_id", sent["body"])
        self.assertNotIn("trace_id", sent["body"])
        self.assertNotIn("verification_subject", sent["body"])
        self.assertEqual(V2_CTX, result.execution_context["execution_context_id"])
        self.assertEqual(V2_TRACE, result.execution_context["trace_id"])

    def test_v2_requires_separate_platform_credentials(self):
        req = dispatch_v2_request()
        with Harness(lambda *_: (500, {})) as (h, url):
            with self.assertRaises(WorksContractError):
                WorksClient(url, "worker-token").accept_dispatch_v2(WORK_ID, req)
        self.assertEqual([], h.requests)

    def test_v2_rejects_invalid_server_minted_context(self):
        req = dispatch_v2_request()
        bad = acceptance_v2(req)
        bad["execution_context"] = dict(bad["execution_context"])
        bad["execution_context"]["execution_context_id"] = "client_chosen"
        with Harness(lambda *_: (200, bad)) as (_h, url):
            with self.assertRaises(WorksContractError):
                WorksClient(
                    url,
                    "worker-token",
                    platform_token="platform-token",
                    bridge_secret="bridge-secret",
                ).accept_dispatch_v2(WORK_ID, req)

    def test_verification_subject_binding_uses_exact_encoded_execution_id(self):
        req = VerificationSubjectBindingRequest(
            attempt_id="att_v2_01",
            effect_id="eff_v2_01",
            causal_id="cause_v2_01",
            subject="git:Aftergraph/STEWARD-by-Aftergraph@" + "f" * 40,
        )
        execution_id = "wexec/idem/v2_01"

        def responder(_method, path, body):
            self.assertEqual(
                "/v2/works/"
                + WORK_ID
                + "/acceptances/wexec%2Fidem%2Fv2_01/verification-subject",
                path,
            )
            self.assertEqual(req.to_wire(), body)
            return 200, {
                "schema": "dispatch.verification-subject/1.0",
                "work_id": WORK_ID,
                "works_execution_id": execution_id,
                "attempt_id": req.attempt_id,
                "effect_id": req.effect_id,
                "causal_id": req.causal_id,
                "subject": req.subject,
                "bound_at": "2026-09-21T08:00:00Z",
            }

        with Harness(responder) as (h, url):
            result = WorksClient(
                url,
                "worker-token",
                platform_token="platform-token",
                bridge_secret="bridge-secret",
            ).bind_verification_subject(WORK_ID, execution_id, req)
        self.assertEqual(execution_id, result["works_execution_id"])
        self.assertEqual("Bearer platform-token", h.requests[0]["authorization"])
        self.assertEqual("bridge-secret", h.requests[0]["bridge"])

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
