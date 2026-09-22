from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "steward.p2.owner-evidence-manifest/1.0"
OWNERS = {
    "Aftergraph/runtime",
    "Aftergraph/works-execution",
    "Aftergraph/trust-gateway",
    "Aftergraph/aie",
    "Aftergraph/sentinel",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX256 = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise SystemExit(f"P2_OWNER_EVIDENCE_MANIFEST=FAIL:{message}")


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage")
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("schema") != SCHEMA:
        fail("schema")
    if data.get("verified_scope") != "owner-native-ci":
        fail("verified_scope")
    if data.get("live_end_to_end") is not False:
        fail("live_end_to_end_must_be_false")
    if data.get("causal_chain") is not False:
        fail("causal_chain_must_be_false")

    receipts = data.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != len(OWNERS):
        fail("receipt_count")
    seen = set()
    for receipt in receipts:
        owner = receipt.get("owner")
        if owner not in OWNERS or owner in seen:
            fail("owner_set")
        seen.add(owner)
        if receipt.get("result") != "PASS":
            fail(f"{owner}:result")
        if not SHA40.fullmatch(str(receipt.get("head_sha", ""))):
            fail(f"{owner}:head_sha")
        if not isinstance(receipt.get("run_id"), int):
            fail(f"{owner}:run_id")
        if not isinstance(receipt.get("job_id"), int):
            fail(f"{owner}:job_id")
        if not isinstance(receipt.get("artifact_id"), int):
            fail(f"{owner}:artifact_id")
        if not SHA256.fullmatch(str(receipt.get("artifact_digest", ""))):
            fail(f"{owner}:artifact_digest")
        if not HEX256.fullmatch(str(receipt.get("receipt_content_sha256", ""))):
            fail(f"{owner}:receipt_content_sha256")

    remaining = data.get("remaining_live_requirements")
    if not isinstance(remaining, list) or not remaining:
        fail("remaining_live_requirements")

    supplied = data.get("content_sha256")
    if not HEX256.fullmatch(str(supplied or "")):
        fail("content_sha256_format")
    canonical_payload = {k: v for k, v in data.items() if k != "content_sha256"}
    canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode()
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != supplied:
        fail("content_sha256_mismatch")

    print(json.dumps({
        "schema": SCHEMA,
        "owners_verified": len(seen),
        "causal_chain": False,
        "live_end_to_end": False,
        "content_sha256": actual,
        "result": "PASS",
    }, sort_keys=True))
    print("P2_OWNER_EVIDENCE_MANIFEST=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
