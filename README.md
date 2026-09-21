# STEWARD

**Status:** architecture/specification seed v0.1 — September 2026  
**Organization:** Aftergraph  
**Purpose:** canonical product/integration root for STEWARD, the persistent governed intelligence system.

STEWARD turns human intent into durable Missions, coordinates heterogeneous intelligence and computers, executes through governed environments, produces artifacts/effects, verifies outcomes, learns from evidence, and remains steerable and revocable throughout the lifecycle.

## Core thesis

> Capability may accelerate only as fast as evidence, alignment, authority and verification can keep up.

STEWARD is not the canonical owner of authority, execution truth, or verification truth. It composes existing Aftergraph owners.

## Canonical external owners

| Concern | Canonical owner |
|---|---|
| Governance / topology / contracts | `Aftergraph/after-graph-governance` |
| Authority / delegation / budget / revocation | `Aftergraph/aie` |
| Policy enforcement / approvals / credential brokerage / egress | `Aftergraph/trust-gateway` |
| Durable work / attempts / leases / checkpoints / effects | `Aftergraph/works-execution` |
| Runtime lifecycle / orchestration integration | `Aftergraph/runtime` |
| Independent exact-subject verification | `Aftergraph/sentinel` |
| Models | `Aftergraph/model-registry` |
| Skills | `Aftergraph/skills-vault` + `Aftergraph/skill-abi` |
| Context continuity | `Aftergraph/context-continuity` |
| Research / benchmarks | `Aftergraph/intelligence-systems-research` |
| Brand | `Aftergraph/brand` |

## What this repository owns

- STEWARD product identity and system composition.
- Canonical STEWARD architecture/specification.
- Cross-repo integration contracts and adapters.
- Harness composition profiles and reference orchestration logic.
- Project/Thread/Composer/Command semantics at the STEWARD boundary.
- Reference clients and product surfaces as they are consolidated.
- Conformance tests for STEWARD integration behavior.

## What this repository must not duplicate

Authority, Trust Gateway policy enforcement, WORKS execution truth, Sentinel verification truth, Model Registry, Skills Vault, or infrastructure-provider ownership.

## Documents

Start with:

1. `docs/00-MASTER-ARCHITECTURE.md`
2. `docs/01-CHARTER-AND-SCOPE.md`
3. `docs/02-DEFINITIONS.md`
4. `docs/03-COMPONENT-OWNERSHIP.md`
5. `docs/04-INFRASTRUCTURE-TOPOLOGY.md`
6. `docs/14-IMPLEMENTATION-PLAN.md`
7. `docs/18-PRESENCE-PROJECTION.md`

## Validation

```bash
python scripts/validate_repo.py
```

## License

MIT — see [LICENSE](LICENSE).

## Research posture

This repository is an implementation/specification seed, not evidence of novelty. Claims about novelty or superiority require the Aftergraph research protocol, prior-art review, reproducible experiments, cost/performance accounting, and independent verification.
