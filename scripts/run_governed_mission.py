"""Autonomous governed mission runner.

Usage:
    python scripts/run_governed_mission.py --correlation correlation.json

The correlation file must carry WORKS-minted identity:
    {"execution_context_id": "ctx_<32 hex>", "trace_id": "trc_<32 hex>"}

Exit codes:
    0  mission ACCEPTED (greenlight)
    1  mission completed but was not accepted (fail-closed refusal)
    2  correlation or contract error (mission refused to start)
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from steward_reference.mission_workflow import (  # noqa: E402
    GovernedMissionWorkflow,
    MissionCorrelationError,
    load_correlation,
)
from steward_reference.sentinel_delegation import AieMint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one autonomous governed mission")
    parser.add_argument(
        "--correlation",
        type=Path,
        required=True,
        help="JSON file with WORKS-minted execution_context_id and trace_id",
    )
    parser.add_argument(
        "--grant",
        type=Path,
        default=ROOT / "fixtures" / "valid" / "delegated-authority-merge-agent.json",
        help="Delegated authority grant for the agent persona",
    )
    parser.add_argument("--persona", default="persona-merge-agent-v1")
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()

    try:
        correlation = load_correlation(args.correlation)
    except (MissionCorrelationError, json.JSONDecodeError) as exc:
        print(f"STEWARD_MISSION=REFUSED_TO_START ({exc})", file=sys.stderr)
        return 2

    grant = json.loads(args.grant.read_text(encoding="utf-8"))
    mission_id = f"mission-{uuid.uuid4().hex[:12]}"

    workflow = GovernedMissionWorkflow(
        mission_id=mission_id,
        persona_id=args.persona,
        grant=grant,
        correlation=correlation,
        mint=AieMint(mint_ref="org-aftergraph/repo-steward"),
    )
    bundle = workflow.run(now=datetime.now(timezone.utc))

    rendered = json.dumps(bundle, indent=2)
    if args.evidence_out:
        args.evidence_out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)

    if bundle["outcome"]["accepted"]:
        print(f"STEWARD_MISSION=ACCEPTED id={mission_id}")
        return 0
    print(f"STEWARD_MISSION=NOT_ACCEPTED id={mission_id}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
