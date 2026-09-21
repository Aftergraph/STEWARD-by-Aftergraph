# STEWARD Actor Personas v0.1

## Purpose

Personas name the human and agent actors that surround a STEWARD system. They exist to make attention, review scope and notification interests explicit, inspectable and contract-bound — not to grant power. A persona is a **projection of intent and interest**, never a source of authority or verification truth.

## Non-negotiables

- `authority_effect` and `verification_effect` are hard-coded `false` in the schema; a persona claiming either is invalid.
- Persona selection is not authorization. A reviewer persona does not merge; a subscriber persona does not verify.
- Merge authority remains with maintainers and AIE. Verification truth remains with Sentinel.
- A persona must declare a `delegation_boundary` in plain language.

## Roles

| Role | Attention | Typical verdicts | Never |
|---|---|---|---|
| `reviewer` | schema/spec/code changes in declared paths | approve, request-changes, comment | merge, mint authority |
| `subscriber` | verdicts, advisories, progress | comment | verify on its own |
| `maintainer` | everything; owns merge decision | approve, request-changes | mint verification truth |
| `observer` | read-only projection | — | any effect |
| `auditor` | evidence, trace integrity | comment | mutate evidence |
| `integrator` | contract changes touching cross-repo boundaries | request-changes, comment | change other owners' contracts unilaterally |

## Attention profile

Interests are bounded enums — `mission-progress`, `verification-verdicts`, `authority-changes`, `policy-changes`, `budget-changes`, `schema-changes`, `spec-changes`, `ci-failures`, `security-advisories`, `release-notes`. `max_daily_attention_minutes` makes the Attention Governor measurable per persona.

## Review scope

Paths are repo-relative and restricted to contract-bearing directories (`schemas/`, `docs/`, `src/`, `scripts/`, `tests/`, `fixtures/`, `adr/`, `.github/`). `max_files_per_review` bounds review size so verdicts stay attributable.

## Reference personas for this repository

- **Contract Reviewer** (`fixtures/valid/actor-persona-reviewer.json`) — human; schemas/ + docs/; 45 min/day; the review counterpart the P2 chain currently lacks.
- **Verification Subscriber** (`fixtures/valid/actor-persona-subscriber.json`) — agent; Sentinel verdicts + security advisories via webhook; 5 min/day; the subscriber role the repo's 0-subscriber state lacks.

## Anti-pattern (invalid)

`fixtures/invalid/actor-persona-self-authorizing.json` — a reviewer persona with `authority_effect: true`. Schema rejects it. A persona that grants itself power is the exact failure mode `.steward.md` names: *selected is not authorized*.

## Relation to owners

- AIE remains the only minter of authority; Trust Gateway remains the only enforcement point; Sentinel remains the only verification truth.
- Personas are downstream: they route attention and structure review, they do not accumulate power.

## Validation

Personas validate through the standard contract suite: `python -m unittest discover -s tests` (see `test_contracts.py`).
