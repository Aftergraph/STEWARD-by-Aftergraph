# Presence Projection Contract v0

## Purpose

STEWARD may render a character, WebGL scene, Lottie signal, badge, text label, or other interface projection of system state. That projection is **not** authority, execution truth, or verification truth.

This document defines the composition boundary. Visual identity, palette, character law, and motion grammar remain owned by `Aftergraph/brand`. Normative authority remains owned by AIE. Policy enforcement remains owned by Trust Gateway. Durable work remains owned by WORKS. Runtime lifecycle remains owned by Runtime. Independent verification remains owned by Sentinel.

## Invariants

1. A presence projection has `claim_class = projection-only`.
2. `canonical_truth`, `authority_effect`, and `verification_effect` are always false.
3. The projection must carry the canonical source owner and source identifier that caused the visible state.
4. `succeeded` is legal only when backed by a verification verdict identifier.
5. `verifying` is sourced from Sentinel verification state, not from an agent's self-report.
6. A stale projection must remain distinguishable from fresh state; clients should stop animating it as live activity once `stale_after` is exceeded.
7. Reduced-motion rendering preserves semantic state and labels while removing continuous motion.
8. The UI may fail closed to a static or textual state without changing the underlying system state.

## Data flow

```
canonical owner state
        ↓
projection adapter
        ↓
PresenceProjection/1.0
        ↓
web / mobile / 3D / Lottie / accessibility surface
```

The adapter is intentionally one-way. A character pose or animation cannot grant permission, advance WORKS, approve an action, or manufacture a Sentinel verdict.

## State mapping

The presentation vocabulary is:

`idle · thinking · planning · executing · inspecting · waiting · blocked · approval · verifying · approving · succeeded · failed`

These labels are product vocabulary only. Canonical state machines remain in their owning repositories. Clients must not reverse-map a visual state into a canonical write.

## Exact-subject behavior

When a projection describes code or another exact-subject artifact, `subject.exact_subject_sha` should be carried. If the subject changes, subject-bound visual receipts are stale just like other exact-subject evidence.

## Failure behavior

If the source cannot be resolved, clients render an explicit unavailable/stale state rather than guessing from prior animation. If WebGL, Rive, Lottie, or another renderer fails, clients may fall back to static identity and text while preserving the same source metadata.

## Schema and fixtures

- `schemas/presence-projection.schema.json`
- `fixtures/valid/presence-projection.json`
- `fixtures/invalid/presence-projection-succeeded-without-verdict.json`
