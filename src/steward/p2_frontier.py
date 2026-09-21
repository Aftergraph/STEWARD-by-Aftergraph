"""Aggregate STEWARD P2 readiness without executing or authorizing owners.

The frontier doctor composes two existing read-only projections:

* local live binding readiness
* secret-free production binding evidence

A green result means only "ready to attempt the governed Golden Mission". It
never grants authority, accepts a mission, deploys an owner, or performs work.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .p2_live_readiness import LiveReadinessReport, inspect_live_readiness
from .p2_production_binding import (
    ProductionBindingContractError,
    ProductionBindingObservation,
    ProductionBindingReport,
    evaluate_production_binding,
    load_observation,
)


@dataclass(frozen=True)
class P2FrontierReport:
    schema: str
    state: str
    blockers: tuple[str, ...]
    live_readiness: LiveReadinessReport
    production_binding: ProductionBindingReport | None

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "state": self.state,
            "blockers": list(self.blockers),
            "live_readiness": {
                "schema": self.live_readiness.schema,
                "state": self.live_readiness.state,
                "checks": [
                    {
                        "name": check.name,
                        "ready": check.ready,
                        "reason": check.reason,
                    }
                    for check in self.live_readiness.checks
                ],
            },
            "production_binding": (
                self.production_binding.to_wire()
                if self.production_binding is not None
                else None
            ),
            "ready_to_attempt_golden_mission": self.state == "READY_TO_ATTEMPT",
            "execution_attempted": False,
            "authority_granted": False,
            "mission_accepted": False,
        }


def inspect_p2_frontier(
    observation: ProductionBindingObservation | None,
    environment: Mapping[str, str] | None = None,
    *,
    production_error: str | None = None,
) -> P2FrontierReport:
    """Project the current P2 frontier without mutating any canonical owner."""

    live = inspect_live_readiness(environment)
    blockers: list[str] = []

    for check in live.checks:
        if not check.ready:
            blockers.append(f"live:{check.name}:{check.reason}")

    binding: ProductionBindingReport | None = None
    if production_error is not None:
        blockers.append(f"production_observation_invalid:{production_error}")
    elif observation is None:
        blockers.append("production_observation_missing")
    else:
        binding = evaluate_production_binding(observation)
        blockers.extend(f"production:{item}" for item in binding.blockers)

    return P2FrontierReport(
        schema="steward.p2.frontier/0.1",
        state="READY_TO_ATTEMPT" if not blockers else "BLOCKED",
        blockers=tuple(blockers),
        live_readiness=live,
        production_binding=binding,
    )


def _load_for_frontier(path: str | Path) -> tuple[ProductionBindingObservation | None, str | None]:
    try:
        return load_observation(path), None
    except (OSError, json.JSONDecodeError, ProductionBindingContractError) as exc:
        return None, str(exc)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        report = inspect_p2_frontier(
            None,
            production_error="usage: python -m steward.p2_frontier [production-observation.json]",
        )
    elif args:
        observation, error = _load_for_frontier(args[0])
        report = inspect_p2_frontier(observation, production_error=error)
    else:
        report = inspect_p2_frontier(None)

    print(json.dumps(report.to_wire(), indent=2, sort_keys=True))
    return 0 if report.state == "READY_TO_ATTEMPT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
