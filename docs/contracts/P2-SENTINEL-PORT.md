# P2 Sentinel exact-subject projection port

Status: transport-neutral consumer implemented; live independent verification pending.

Baseline owner: `Aftergraph/sentinel@eb51f824af2279ee3eee5daa8572bd54a34b3ca8`.

## Existing owner semantics

The locked Sentinel baseline already defines the behavior STEWARD needs:

- the product/build contract binds a verdict to the **exact commit**;
- `currentHead !== verifiedHead → STALE`;
- a model/agent may produce findings but may not issue `SHIP`;
- GitHub check-runs are keyed by `repo + PR + headSha`;
- when a PR head moves, the older check is explicitly superseded/stale;
- `sentinel.receipt/0.1` carries `repo`, `prNumber`, `headSha`,
  verdict and a content-addressed `receipt_id`;
- Sentinel's local receipt ledger is a claim log, not platform L1/L2 evidence.

## STEWARD boundary

STEWARD therefore consumes a read-only exact-subject projection. It cannot mint
or upgrade a verdict.

No new Sentinel HTTP endpoint is invented in this repository. `SentinelPort`
takes an injected deployment transport and enforces:

```text
requested exact SHA A
   ↓
independent Sentinel transport
   ↓
returned subject MUST == SHA A
   ↓
SHIP      -> may satisfy the Sentinel portion of acceptance
STALE     -> never satisfies
BLOCKED   -> never satisfies
DO_NOT_SHIP -> never satisfies
```

A later SHA B makes a prior projection for A unusable even if A was SHIP.

## Proof boundary

The unit tests prove exact-subject projection/invalidation semantics in STEWARD.
They do not prove that a live Sentinel worker independently verified the code.
P2 requires a live exact-SHA evidence run before MissionAcceptance.
