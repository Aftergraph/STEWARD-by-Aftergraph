# P2 WORKS Adapter Contract

Status: implemented conformance slice; not yet a live cross-repo P2 PASS.

Baseline owner: `Aftergraph/works-execution@ab8c1d2a6cc322b3d730b1514b1141b8ee65310c`.

STEWARD consumes existing WORKS ownership. It does not create a second execution state machine.

## Boundary

`WorksClient.accept_dispatch()` targets `POST /v1/works/{id}/accept` and the frozen `contract:dispatch.acceptance/1.0` shape.

The request deliberately cannot carry `execution_context_id` or `trace_id`. The canonical WORKS handler uses a request type without those fields and `DisallowUnknownFields`; WORKS mints the winning correlation pair at durable acceptance.

The adapter also validates that the response preserves `mission_id`, `runtime_dispatch_id`, `idempotency_key`, and `verification_subject` and returns syntactically valid WORKS-owned correlation IDs.

## Fail-closed behavior

- `409 dispatch_stale_authority` → typed stale-authority failure.
- `503 dispatch_accept_unavailable` → typed unavailable failure.
- malformed/missing correlation → local contract failure; no optimistic fallback.
- changed verification subject → contract failure.

## Proof boundary

The repository tests prove STEWARD does not mint WORKS-owned correlation fields and rejects malformed/falsified responses under a deterministic HTTP harness. They do **not** prove a live Runtime→WORKS→AIE integration yet. That requires the cross-repo P2 evidence run.
