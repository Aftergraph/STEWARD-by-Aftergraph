# STEWARD Visual Frontier Profile v1

## Purpose

This profile binds STEWARD's **renderer implementation and evidence** for the current frontier visual candidate. It does not move visual identity ownership into STEWARD.

- Canonical identity, palette, character law and brand usage remain owned by `Aftergraph/brand`.
- STEWARD owns only the composition/runtime projection that consumes that identity.
- The profile is presentation-only and inherits the truth boundary from `PresenceProjection/1.0`.

## Current bound candidate

The current observed 3D candidate is:

- provider: Higgsfield 3D Jutsu
- project: `2cefe187-1660-4af9-bfc9-5cadd765d5a3`
- revision: `4`
- armature: `STEWARD_Rig`
- bones: `20`
- geometry changed by the frontier pass: **false**
- material profile: `frontier-material/1.1`
- portable light classes: SUN + POINT + SPOT + POINT
- animation clips retained: `idle`, `blink`, `verify`
- static state pack: `steward.rig-state-assets/3.0`

The state pack contains:

`idle · thinking · planning · executing · verifying · succeeded`

All state renders derive from the same rig revision. They are fallbacks/presentation assets, never canonical state.

## Frontier material hierarchy

Revision 4 deliberately separates functional surface roles:

| Role | Rendering intent |
| --- | --- |
| cream shell | mineral/composite, non-metallic |
| structural dark | satin technical structure |
| visor | smoked optical glass |
| halo copper | physical copper without global glow |
| eyes + custody node | restrained copper signal |
| evidence badge | restrained pine-teal signal |
| evidence white | non-metallic evidence surface |

This is an implementation profile, not a new source of brand truth. If the canonical Brand OS changes, the renderer profile must be regenerated/reverified rather than overriding Brand OS.

## Runtime hierarchy

```
verified rig GLB
        ↓
Three.js WebGL presence
        ↓
frontier-material/1.1
        ↓
idle / blink / verify
        ↓
rig-state-assets/3.0 fallback
```

The renderer may fail closed from WebGL to a static rig-derived state without changing semantic source state.

## Truth boundary

The visual system always carries:

- `claim_class = projection-only`
- `canonical_truth = false`
- `authority_effect = false`
- `verification_effect = false`

A visually bright badge, animated ring, or `succeeded` pose cannot create authority or verification.

## Current delivery observation

The STEWARD Higgsfield website source has a frontier presentation commit:

`12f1a3a46c47c95403f1c545368a3b48568e4657`

Higgsfield reports the production deployment as `deployed`, but anonymous requests to
`https://steward-by-aftergraph.higgsfield.app/` currently return:

```json
{"error":"unauthenticated"}
```

with HTTP 401.

Repository inspection found no auth middleware or 401 path in STEWARD's site source. Treat public accessibility as an **external Higgsfield platform/edge blocker**, not as evidence that the renderer failed.

Do not weaken source/runtime truth boundaries to work around that external hosting gate.

## Files

- `schemas/visual-frontier-profile.schema.json`
- `fixtures/valid/visual-frontier-profile.json`
- `fixtures/invalid/visual-frontier-profile-authority.json`
- `tests/test_visual_frontier_profile.py`
