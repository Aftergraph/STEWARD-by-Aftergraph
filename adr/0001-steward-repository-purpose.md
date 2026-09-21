# ADR-0001: STEWARD repository purpose

## Status
Proposed / seed decision.

## Context
Aftergraph already contains canonical owners for governance, authority, policy enforcement, durable execution, verification, models, skills and context continuity. A new STEWARD repository risks duplicating these owners if treated as a monolithic platform rewrite.

## Decision
`Aftergraph/steward` is the canonical STEWARD product/integration root and specification repository. It composes existing owners through versioned contracts. It may contain product-facing clients, harness composition and reference orchestration, but must not copy canonical authority, execution or verification truth into new parallel databases/state machines.

## Consequences
Cross-repo contract discipline is mandatory. Integration tests must verify owner boundaries. Existing Studio/FIHIM/WI code is evaluated for migration/reuse rather than silently duplicated.
