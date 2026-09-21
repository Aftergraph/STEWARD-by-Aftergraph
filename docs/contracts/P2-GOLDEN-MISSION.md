# P2 composed Golden Mission gate

Status: executable composition candidate; **not live P2 proof**.

This slice composes the existing owner ports into one fail-closed lifecycle:

```text
STEWARD request
  -> Runtime V2 dispatch
  -> WORKS materialized execution context
  -> isolated Habitat worktree
  -> Trust Gateway / AIE action-time decision
  -> observed candidate Git SHA
  -> Runtime / WORKS one-time exact-subject binding
  -> Sentinel exact-head verdict
  -> Mission accepted only for current-subject SHIP
```

## Ownership

- Runtime still owns dispatch.
- WORKS still owns durable execution context and subject binding.
- Trust Gateway and AIE still own effect-time enforcement and authority.
- The injected Habitat provider still owns worktree execution.
- Sentinel still owns the independent verdict.
- STEWARD owns only causal composition and the read-only acceptance projection.

## Executable negative gates

- `needs_approval` stops before candidate capture, subject binding and Sentinel.
- a non-`SHIP` verdict cannot accept the Mission.
- a verdict for another SHA fails closed.
- every cross-owner receipt is checked against the original Work, context and
  immutable Git subject.

Passing these repository tests proves composition semantics only. P2 remains
open until the same chain runs against live WORKS, Runtime, Trust Gateway/AIE,
Habitat/Git and Sentinel services and emits a complete evidence bundle.
