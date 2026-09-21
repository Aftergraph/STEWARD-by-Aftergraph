# STEWARD Delegated Autonomy v0.1

## Purpose

Personas name actors. Delegated autonomy defines how an agent persona may **act**. The boundary is fixed: an agent is never authorized by its own selection. Authorization is the positive outcome of a resolvable chain — a grant that exists, is active, attenuates its parent, and for verification capabilities is bound to Sentinel.

> Selected is not authorized. Predicted is not observed. Completed is not verified. An agent acting without a valid grant is unauthorized by definition, and a grant is invalid until every condition resolves positively.

## The autonomy ladder

```text
LEVEL 0  Persona            named actor, attention + review interests, zero authority
LEVEL 1  Grantee             persona referenced by an active delegated-authority grant
LEVEL 2  Bounded actor       grant attenuated against parent capabilities; DENY on escalation
LEVEL 3  Bound verifier       verify:* capabilities require a Sentinel verification_binding
LEVEL 4  Governed autonomous effect-chain: ALLOW receipt -> effect -> Sentinel verdict -> acceptance
```

Each level is a resolvable predicate, not a label. `resolve_action` computes the level per action, per instant.

## The decision algorithm

`src/steward_reference/delegated_authority.py` implements fail-closed resolution:

1. **Structural validity** — `validate_grant`: identifiers present, `expires_at > granted_at`, `revoked_at > granted_at`, verification bindings point at Sentinel. Malformed grants raise; callers deny.
2. **Attenuation** — `is_attenuated`: `capabilities ⊆ parent_capabilities`. Escalation (e.g. `repo:admin` under a read-only parent) denies every requested capability, not just the excess.
3. **Capability match** — the requested capability must be in the grant. Unlisted capability denies with `capability_not_granted`.
4. **Temporal state** — `grant_state` resolves `active | revoked | expired` at an instant. The expiry boundary is exact: at `expires_at - 1s` active, at `expires_at` expired.
5. **Verification binding** — `verify:exact-subject` requires a Sentinel binding, a subject SHA, and SHA match with the bound subject. `verify:projection` requires the Sentinel binding alone. An agent may never self-verify.

Every denial returns a typed receipt with a machine-readable reason: `invalid_grant`, `escalation`, `capability_not_granted`, `grant_expired`, `grant_revoked`, `verification_requires_sentinel_binding`, `exact_subject_verification_requires_subject_sha`, `subject_mismatch`. Refusals are auditable evidence, not silent failures.

## Division of enforcement

Attenuation is **algorithmic, not schema-structural**: JSON Schema cannot express a subset relation between two arrays, so `delegated-authority.schema.json` validates shape and the `if/then` verification binding, while `resolve_action` enforces attenuation and temporality. Both layers must pass; neither alone authorizes.

| Concern | Enforced by |
|---|---|
| Grant shape, required fields | JSON Schema |
| `verify:*` requires `verification_binding` | JSON Schema (`if/then`) |
| Revocation requires `revoked_at` | JSON Schema (`if/then`) |
| Attenuation (child ⊆ parent) | Algorithm (`is_attenuated`) |
| Temporal state at instant | Algorithm (`grant_state`) |
| Subject SHA binding | Algorithm (`resolve_action`) |

## Level 4: the governed agent

`src/steward_reference/governed_agent.py` composes the ladder into a real effect chain:

```text
persona + grant
   -> attempt_merge: resolve pr:merge at instant
      ALLOW -> real git merge in isolated repository, exact SHAs recorded
      DENY  -> effect.blocked; subject untouched; no git.merge event
   -> verify_independently: resolve verify:exact-subject against result SHA
      merge agent without verify capability -> DENY (cannot self-verify)
      bound verifier -> ALLOW only for the bound subject SHA
   -> accept_mission: ACCEPTED only if merged AND externally verified
   -> evidence bundle: ordered, attributable audit trace
```

The agent's audit trace events — `authority.resolve`, `effect.blocked`, `git.merge`, `verification.claim`, `mission.acceptance` — each carry sequence number, timestamp, actor, decision and detail. An allowed merge alone never yields acceptance: the full chain requires the external verdict too.

## What agents may and may not do

| Capability | Valid grant allows | No grant / invalid grant |
|---|---|---|
| `pr:merge` | merge within grant window, attenuated set | DENY |
| `repo:admin` | only if in attenuated set of parent | DENY (escalation) |
| `verify:exact-subject` | only with Sentinel binding + matching SHA | DENY |
| `verify:projection` | only with Sentinel binding | DENY |

## Relation to canonical owners

- **AIE** remains the only minter of authority: grants reference `authority_source.owner = aie`. STEWARD resolves and records; it never mints.
- **Sentinel** remains the only verification truth: `verification_binding.verifier_owner` is `const: sentinel`.
- **Trust Gateway** remains the enforcement plane in production; this module is the reference semantics that TG enforces at effect time.
- **WORKS** records the durable attempt; an ALLOW receipt without a WORKS attempt is still not an effect.

## Reference fixtures

| Fixture | Proves |
|---|---|
| `valid/delegated-authority-merge-agent.json` | attenuated merge window from AIE |
| `valid/delegated-authority-verifier.json` | Sentinel-bound exact-subject verification |
| `invalid/delegated-authority-escalation.json` | schema-valid, algorithm-denied escalation |
| `invalid/delegated-authority-expired.json` | temporal denial at the boundary |
| `invalid/delegated-authority-verify-without-sentinel.json` | schema rejection of unbound verification |

## Validation

```bash
python -m unittest discover -s tests   # 47 tests incl. delegated authority + governed agent chains
```

## Production gate

This is reference semantics. The production chain — AIE-minted grant, TG enforcement at effect time, Sentinel verdict binding, WORKS attempt correlation — is P2 scope (#2). No ALLOW receipt from this module is execution truth until that chain exists.
