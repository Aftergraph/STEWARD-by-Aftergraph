# P2 Runtime Port

Status: transport-neutral composition port implemented; production Runtime transport still pending.

Baseline owner: `Aftergraph/runtime@4bff0be654c9e32f62317295d43d7e918139f3e9`.

## Discovery

The locked Runtime baseline owns orchestration/dispatch and exposes `runtime.dispatch-seal/0.1` in `packages/job-runtime/src/dispatch-seal.ts`. It also owns managed execution correlation and checkpoint/recovery primitives. The repository's `runtime-host` CLI is a long-lived host bootstrap surface and explicitly says production must inject real Trust Gateway authority; it is not a STEWARD production RPC contract.

Therefore STEWARD must not invent a Runtime HTTP endpoint or silently execute locally when Runtime is unavailable.

## Port

`RuntimePort` accepts a deployment-provided transport and emits the frozen dispatch-seal field shape without `runtimeDispatchId`, `executionContextId`, `traceId`, or `verified`.

Runtime owns dispatch identity. WORKS owns durable acceptance and execution-context correlation. STEWARD consumes the resulting receipt only as correlation/projection state.

## Proof boundary

The unit tests prove:
- STEWARD does not mint Runtime/WORKS-owned IDs;
- malformed returned correlation fails closed;
- a transport failure cannot trigger a local/direct-to-WORKS fallback;
- invalid budget/authority minima fail before transport.

This is not yet evidence of a live Runtime transport. That remains tracked in `Aftergraph/runtime#194` and the STEWARD P2 tracker.
