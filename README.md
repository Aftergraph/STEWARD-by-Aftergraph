# STEWARD by Aftergraph

STEWARD is Aftergraph's product/composition layer for persistent, proactive, governed and verifiable intelligent work.

> Perceive → understand → specify → reason → plan → organize → authorize → execute → verify → learn → wake.

## Ownership

STEWARD composes canonical Aftergraph owners rather than duplicating them:

- governance/topology/contracts → `Aftergraph/after-graph-governance`
- authority/delegation/revocation → `Aftergraph/aie`
- enforcement/credentials/egress → `Aftergraph/trust-gateway`
- durable Work/leases/checkpoints/effects → `Aftergraph/works-execution`
- orchestration/dispatch → `Aftergraph/runtime`
- independent verification → `Aftergraph/sentinel`

## Current milestone

P2 productionization has started. The first implemented adapter is the canonical WORKS dispatch-acceptance client, bound to the locked P2 baseline in `contracts/p2-baseline-lock.json`.

Run the current conformance suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

A green repository test run is implementation evidence, not a claim of end-to-end institutional verification.
