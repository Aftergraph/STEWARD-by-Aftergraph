import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.runtime import (
    RuntimeContractError,
    RuntimeRejectedError,
    SubprocessRuntimeTransport,
)
from steward.ports.runtime_subject import (
    RuntimeSubjectBindingPort,
    RuntimeSubjectBindingRequest,
)


SUBJECT = (
    "git:Aftergraph/STEWARD-by-Aftergraph@"
    + "b" * 40
)


def request():
    return RuntimeSubjectBindingRequest(
        work_id="wrk_" + "1" * 32,
        works_execution_id="wexec/idem/v2/1",
        attempt_id="attempt/1",
        effect_id="effect/1",
        causal_id="causal/1",
        subject=SUBJECT,
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
        "workId": "wrk_" + "1" * 32,
        "worksExecutionId": "wexec/idem/v2/1",
        "attemptId": "attempt/1",
        "effectId": "effect/1",
        "causalId": "causal/1",
        "subject": SUBJECT,
        "boundAt": "2026-09-21T07:00:00Z",
    }


class RuntimeSubjectBindingPortTests(unittest.TestCase):
    def test_exact_observed_subject_is_forwarded_through_runtime(self):
        transport = FakeTransport(receipt())
        got = RuntimeSubjectBindingPort(transport).bind(request())
        self.assertEqual(SUBJECT, got.subject)
        self.assertEqual("2026-09-21T07:00:00Z", got.bound_at)
        self.assertEqual(SUBJECT, transport.calls[0]["subject"])

    def test_branch_placeholder_fails_before_transport(self):
        transport = FakeTransport(receipt())
        bad = RuntimeSubjectBindingRequest(
            **(request().__dict__ | {
                "subject": "git:Aftergraph/STEWARD-by-Aftergraph@main"
            })
        )
        with self.assertRaises(RuntimeContractError):
            RuntimeSubjectBindingPort(transport).bind(bad)
        self.assertEqual([], transport.calls)

    def test_runtime_cannot_silently_rebind_subject(self):
        transport = FakeTransport(
            receipt() | {
                "subject":
                    "git:Aftergraph/STEWARD-by-Aftergraph@" + "c" * 40
            }
        )
        with self.assertRaises(RuntimeContractError):
            RuntimeSubjectBindingPort(transport).bind(request())

    def test_subprocess_path_keeps_credentials_out_of_payload(self):
        script = (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "assert 'WORKS_BEARER_TOKEN' not in req;"
            "assert 'WORKS_BASE_URL' not in req;"
            "assert 'WORKS_PLATFORM_BRIDGE_SECRET' not in req;"
            "print(json.dumps({'ok':True,'receipt':{"
            "'workId':req['workId'],"
            "'worksExecutionId':req['worksExecutionId'],"
            "'attemptId':req['attemptId'],"
            "'effectId':req['effectId'],"
            "'causalId':req['causalId'],"
            "'subject':req['subject'],"
            "'boundAt':'2026-09-21T07:00:00Z'}}))"
        )
        transport = SubprocessRuntimeTransport(
            (sys.executable, "-c", script),
            environment={
                "WORKS_BASE_URL": "https://works.invalid",
                "WORKS_BEARER_TOKEN": "secret-token",
                "WORKS_PLATFORM_BRIDGE_SECRET": "bridge-secret",
            },
        )
        got = RuntimeSubjectBindingPort(transport).bind(request())
        self.assertEqual(SUBJECT, got.subject)

    def test_runtime_rejection_is_typed_and_not_bypassed(self):
        encoded = json.dumps({"ok": False, "reason": "works_unavailable"})
        script = (
            "import json,sys;"
            "json.load(sys.stdin);"
            f"print({encoded!r});"
            "sys.exit(1)"
        )
        transport = SubprocessRuntimeTransport((sys.executable, "-c", script))
        with self.assertRaises(RuntimeRejectedError):
            RuntimeSubjectBindingPort(transport).bind(request())


if __name__ == "__main__":
    unittest.main()
