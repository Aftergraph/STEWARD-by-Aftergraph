# P2 Runtime Port

Status: transport-neutral composition port + subprocess transport implemented; Runtime owner bridge is in `Aftergraph/runtime#195`; live deployed proof still pending.

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


## Selected concrete transport

The Runtime owner now has candidate PR `Aftergraph/runtime#195` exposing
`runtime-steward-dispatch`. STEWARD's `SubprocessRuntimeTransport` invokes
that executable with JSON on stdin.

The request contains correlation/work bindings only. WORKS URL and bearer
material remain in the Runtime process environment and are not placed in the
STEWARD dispatch envelope or argv.

This is an executable cross-repo seam, not yet a live deployment claim.


## P2/V2.1 corrected transport

Governance falsification in `Aftergraph/after-graph-governance#185` showed that
legacy `dispatch.acceptance/1.0` cannot be the canonical P2 write path because
it carries an unowned scalar `authority_epoch` and its correlation ID is not
the full materialized execution-context required by TG V2.1.

The P2 target is now Runtime's `runtime-steward-dispatch-v2` bridge
(`Aftergraph/runtime#195`) into WORKS `dispatch.acceptance/2.0`
(`Aftergraph/works-execution#127`).

`RuntimeDispatchV2Request` carries canonical Work, Tenant, Principal,
AuthorityLease, WorkerLease and admission-PDR references but no
`authority_epoch` and no client-selected ctx/trc. `RuntimeV2Port` accepts
only the WORKS-materialized ctx/trc/worker receipt and fails closed on Work
rebinding or malformed correlation.

The old RuntimePort remains compatibility code only; P2 evidence must use the
V2 port.
