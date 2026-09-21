# P2 production binding readiness

Status: **candidate composition contract — no production deployment claimed**

The live P2 proof now closes the same-causal execution and verification chain on
the Aftergraph VDS, including isolated Work/Attempt binding and durable WORKS
MissionAcceptance. Its machine boundary still says:

```json
{"production_deployment":"absent"}
```

This document defines the next gate without moving deployment ownership into
STEWARD.

## Ownership

Each canonical owner remains responsible for its own production installation and
exact-state evidence:

| Owner | Exact candidate | Production role |
|---|---|---|
| Runtime | `3a1018406f570f04fa40c86d649fe4e8b43db129` | orchestration/dispatch |
| WORKS | `2365e7aab195fa9ec7bf3e2e56076731a72dbf39` | durable execution + MissionAcceptance |
| Trust Gateway | `e7a693ea895ae0412f754eea5a291fc8ed3779a3` | action-time enforcement + governed egress |
| AIE | `4e3514b936d2d65433b6c51901afb56908abd545` | authority/revalidation |
| Sentinel | `eb51f824af2279ee3eee5daa8572bd54a34b3ca8` | independent exact-subject verification |

STEWARD only verifies that the observed deployed identities and cross-owner
bindings are complete. A green readiness report does not grant authority, deploy
anything, or mark a Mission accepted.

## Secret-safe observation contract

The input contract is `steward.p2.production-binding/0.1`.

It contains only:

- canonical owner/repository name;
- expected and observed exact commit SHA;
- deployment mode (`service`, `module`, or `cli`);
- active/invocable state;
- non-secret deployment and health/invocation evidence references;
- cross-plane booleans for the bindings already proved in the same-causal run.

Fields whose names look like tokens, secrets, passwords, credentials, or keys
are rejected. Credential values belong only in owner-controlled secret stores.

The checked-in example is deliberately **UNBOUND** and must fail closed until
real production observations replace every placeholder.

## Required cross-plane production evidence

A production-ready observation requires all of the following simultaneously:

1. every owner is present and active at the exact candidate SHA;
2. WORKS uses durable state rather than the ephemeral test server;
3. Trust Gateway production adapter runtime is enabled with reviewed governance;
4. AIE action-time revalidation is exercised live;
5. governed Git uses credential surrogation rather than exposing repository
   credentials to the worker/model;
6. the remote Git subject is read back independently;
7. Sentinel is invoked independently against the current exact subject.

The successful VDS integration run `35624499386` is evidence that these
contracts compose, but it is not production-deployment evidence because the
owner processes and stores used by the proof are test-scoped.

## Doctor

Given a secret-free observation:

```bash
PYTHONPATH=src python -m steward.p2_production_binding observation.json
```

Exit codes:

- `0` — exact production bindings are observed and the composition is ready to
  attempt a production Golden Mission;
- `2` — missing/drifted/inactive binding or malformed/secret-bearing evidence.

A successful output still includes:

```json
{"authority_granted":false,"mission_accepted":false}
```

Those truths belong to AIE/TG and WORKS/Sentinel respectively.

## Activation order

The safe activation order for a future authorized deployment is:

```text
exact owner deploy/readback
    ↓
WORKS durable store health
    ↓
AIE production authority state
    ↓
TG production adapter + pinned transport + Vault
    ↓
Runtime production caller binding
    ↓
independent Sentinel invocation/receipt path
    ↓
production-binding doctor READY
    ↓
one bounded production Golden Mission
    ↓
WORKS durable MissionAcceptance readback
```

No merge, service restart, secret installation, or production action is
authorized by this document.
