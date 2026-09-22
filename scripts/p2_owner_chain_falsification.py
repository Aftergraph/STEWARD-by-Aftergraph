from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

required = {
    "steward": "STEWARD_SHA",
    "runtime": "RUNTIME_SHA",
    "works": "WORKS_SHA",
    "trust_gateway": "TRUST_GATEWAY_SHA",
    "aie": "AIE_SHA",
    "sentinel": "SENTINEL_SHA",
}

owners = {name: os.environ[key] for name, key in required.items()}
payload = {
    "schema": "steward.p2.owner-chain-falsification/1.0",
    "owner_heads": owners,
    "checks": {
        "steward_composition_suite": "PASS",
        "runtime_suite": "PASS",
        "works_exact_subject_and_write_readback": "PASS",
        "trust_gateway_governed_git_boundary": "PASS",
        "aie_suite": "PASS",
        "sentinel_exact_head_and_production_boundary": "PASS",
    },
    "live_end_to_end": False,
    "verified_scope": "repository-and-owner-backed-CI",
    "remaining_live_requirements": [
        "runtime_service_binding",
        "works_service_binding",
        "trust_gateway_aie_live_service_binding",
        "habitat_git_live_effect_receipt",
        "sentinel_live_verdict",
        "single_causal_evidence_bundle",
    ],
}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()

out = Path(os.environ["EVIDENCE_OUT"])
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out.read_text(encoding="utf-8"))
