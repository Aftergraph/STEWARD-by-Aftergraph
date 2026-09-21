# P2 Frontier Doctor

Status: STEWARD-owned read-only composition aid.

The frontier doctor combines two existing readiness projections:

1. local live binding readiness from `steward.p2.live-readiness/0.1`
2. secret-free production binding evidence from `steward.p2.production-binding/0.1`

It answers one question:

> Is STEWARD ready to **attempt** the governed P2 Golden Mission?

A green answer is deliberately weaker than authority or acceptance.

## Non-goals

The doctor does not:

- deploy Runtime, WORKS, Trust Gateway, AIE, or Sentinel
- install credentials or print secret values
- grant authority
- mutate WORKS state
- invoke the Golden Mission
- create a Sentinel verdict
- claim production P2 PASS

Every report hard-codes:

- `execution_attempted=false`
- `authority_granted=false`
- `mission_accepted=false`

## Usage

Without an observation document:

```bash
python -m steward.p2_frontier
```

This must fail closed and report `production_observation_missing`.

With a secret-free production observation:

```bash
python -m steward.p2_frontier production-binding.json
```

Exit code is 0 only when both the production observation and all local live
bindings are ready. Otherwise it is 2 with machine-readable blockers.

The command may read the presence of `STEWARD_TRUST_GATEWAY_TOKEN`, but never
returns, hashes, logs, or persists the token value.
