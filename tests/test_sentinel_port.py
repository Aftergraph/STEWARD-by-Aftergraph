from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward.ports.sentinel import (
    SentinelContractError,
    SentinelPort,
    SentinelUnavailableError,
    SentinelVerificationRequest,
)


SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def verify_exact_head(self, payload):
        self.calls.append(dict(payload))
        if self.error is not None:
            raise self.error
        return self.response


def request(sha=SHA_A):
    return SentinelVerificationRequest(
        repository="Aftergraph/STEWARD-by-Aftergraph",
        head_sha=sha,
        pull_request=4,
    )


def response(sha=SHA_A, verdict="SHIP"):
    return {
        "repo": "Aftergraph/STEWARD-by-Aftergraph",
        "headSha": sha,
        "verdict": verdict,
        "receipt_id": "receipt-1",
        "evidence": ["evidence-1"],
    }


class SentinelPortTests(unittest.TestCase):
    def test_exact_subject_ship_satisfies_only_current_head(self):
        transport = FakeTransport(response())
        projection = SentinelPort(transport).verify(request())
        self.assertTrue(projection.satisfies(SHA_A))
        self.assertFalse(projection.satisfies(SHA_B))
        self.assertEqual(SHA_A, transport.calls[0]["headSha"])

    def test_new_head_invalidates_prior_subject_verdict(self):
        projection = SentinelPort(FakeTransport(response())).verify(request())
        self.assertEqual("SHIP", projection.verdict)
        self.assertFalse(projection.satisfies(SHA_B))

    def test_verdict_for_different_sha_fails_closed(self):
        with self.assertRaises(SentinelContractError):
            SentinelPort(FakeTransport(response(SHA_B))).verify(request(SHA_A))

    def test_stale_and_do_not_ship_never_satisfy_acceptance(self):
        for verdict in ("STALE", "DO_NOT_SHIP", "BLOCKED"):
            projection = SentinelPort(FakeTransport(response(verdict=verdict))).verify(request())
            self.assertFalse(projection.satisfies(SHA_A), verdict)

    def test_malformed_subject_fails_before_transport(self):
        transport = FakeTransport(response())
        with self.assertRaises(SentinelContractError):
            SentinelPort(transport).verify(request("short"))
        self.assertEqual([], transport.calls)

    def test_missing_verdict_reference_fails_closed(self):
        bad = response()
        bad.pop("receipt_id")
        with self.assertRaises(SentinelContractError):
            SentinelPort(FakeTransport(bad)).verify(request())

    def test_transport_failure_has_no_builder_fallback(self):
        transport = FakeTransport(error=OSError("sentinel down"))
        with self.assertRaises(SentinelUnavailableError):
            SentinelPort(transport).verify(request())
        self.assertEqual(1, len(transport.calls))


if __name__ == "__main__":
    unittest.main()
