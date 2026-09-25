import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_study015_causal_probe_preserves_identity_and_fails_closed():
    proc = subprocess.run(
        [sys.executable, "scripts/study015_causal_probe.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout.strip().splitlines()[-1])
    assert receipt["schema"] == "study015.causal-composition/1.0"
    assert receipt["component"] == "steward-composition"
    assert receipt["network_used"] is False
    assert len(receipt["source_head"]) == 40
    assert len(receipt["component_probe_root_sha256"]) == 64
    assert all(receipt["seams"].values())
    assert all(receipt["hostile"].values())
    assert set(receipt["component_heads"]) == {
        "aie", "trust-gateway", "works-execution", "runtime", "sentinel"
    }
