# Implementation Plan v0.1

## P-1 — System reality and ownership baseline
- Verify every referenced Aftergraph repository and current canonical owner.
- Freeze naming collisions and deprecated AVC ownership.
- Produce machine-readable ownership/topology registry.
- Define required cross-repo contract versions.
- Establish integration test environment and exact-head evidence format.

**Exit:** no ambiguous canonical truth owner for any P0 component.

## P0 — Contract skeleton
- IntentEnvelope / CommandEnvelope.
- ProjectRef / ThreadRef / MissionRef.
- WorkClaim and coordination contracts.
- HabitatSpec / HarnessProfile.
- GitExecutionContext / WorktreeRef.
- EffectContract / ArtifactRef / EvidenceRef.
- Projection event envelope.
- Trace correlation envelope.
- Generate conformance fixtures and JSON schemas.

**Exit:** schemas validate and ownership boundary tests pass without needing a full product UI.

## P1 — Single-agent governed vertical slice
Natural-language goal → Project → Mission → one coding Work node → isolated Worktree → test → exact SHA → Sentinel → verified result.

Use one model/provider, one repository, one sandbox class and deterministic approval policy. Avoid multi-agent complexity until the vertical slice is measured.

**Exit:** repeatable end-to-end run with no authority/evidence shortcuts and full trace.

**Reference proof now present:** `scripts/run_p1_reference.py` executes a local conformance slice using a real temporary Git repository, isolated builder worktree, deterministic failing-then-passing test, exact candidate commit, fresh detached verification worktree, exact-SHA verdict binding, trace, and Mission Acceptance. This is not yet production integration with AIE/TG/WORKS/Runtime/Sentinel.


## P2 — Git/worktree engineering fabric
- Worktree manager with lease/recovery/cleanup.
- Git reality baseline.
- Integration/Review/Verification worktree classes.
- Commit/PR/merge effect contracts.
- exact-head invalidation tests.

**Exit:** parallel code changes integrate without shared mutable checkout and stale-verdict regressions are caught.

## P3 — Context + Memory + Retrieval
- THREAD/RECALL/VERITY/FRAME pipeline.
- Project Memory + Chronicle.
- exact/lexical/vector/hybrid retrieval.
- context budgeter and source rehydration.
- memory control permissions and deletion/retention paths.

## P4 — Multi-agent organization
- MUSTER, CHORUS, WorkClaims and collision graph.
- Parallelism Governor.
- shared tactical state + typed handoffs.
- event-driven joins and WAKE.

**Exit:** measurable benefit over single-agent baseline after coordination cost.

## P5 — Background + Proactive
- durable background Work.
- Routines/WAKE.
- typed STEER/control propagation.
- Attention Governor and Suggestions.

## P6 — Assurance stack
- deterministic sensors + executable Oracles.
- calibrated Jev/LLM judges where hard tests are impossible.
- independent verifier integration.
- Mission Acceptance.

## P7 — Learning / Verified RSI
- trajectory store and contrastive diagnosis.
- bounded harness/skill/routing candidates.
- replay, benchmark-disjoint holdout, shadow and guarded promotion.
- protected invariant tests.

## P8 — Multi-channel product
- Web/mobile/CLI/messaging/voice sharing Command/Projection/Flow contracts.
- Artifact Canvas, Live Computer, Needs You and project workspaces.

## Measurement gates
At each phase record VSR, FCR, CRR, CPVO, time-to-verified-outcome, human minutes, retries, unauthorized-action count, context tokens, compute/cost and control-plane tax.
