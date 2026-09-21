# STEWARD Visual Frontier Profile v1.1

## Purpose

This profile binds STEWARD's **renderer implementation and evidence** for the current frontier visual candidate. It does not move visual identity ownership into STEWARD.

- Canonical identity, palette, character law and brand usage remain owned by `Aftergraph/brand`.
- STEWARD owns only the composition/runtime projection that consumes that identity.
- The profile is presentation-only and inherits the truth boundary from `PresenceProjection/1.0`.

## Current bound candidate

The current 3D candidate is:

- provider: Higgsfield 3D Jutsu
- project: `2cefe187-1660-4af9-bfc9-5cadd765d5a3`
- revision: `5`
- armature: `STEWARD_Rig`
- bones: `20`
- proportion profile: `frontier-proportions/1.0`
- material profile: `frontier-material/1.1`
- geometry topology changed: **false**
- armature changed: **false**
- portable light classes: SUN + POINT + SPOT + POINT
- animation clips retained: `idle`, `blink`, `verify`

The rev5 proportion pass deliberately reduces mascot-like center mass without changing character topology or rig identity:

| Ratio | Rev4 | Rev5 |
| --- | ---: | ---: |
| torso / head width | 0.914 | 0.822 |
| torso / head height | 0.967 | 0.851 |
| visor / head width | ~0.690 | 0.745 |
| hand / head width | 0.190 | 0.163 |
| foot / head width | 0.276 | 0.248 |

## Verified runtime asset

The website runtime consumes:

- asset: `/assets/steward-rig-v2.glb`
- SHA-256: `018fb057659975d67a3f6de3dc90a5167bc046d3bf366e3c0a9fe6ec96ecf6a8`
- source commit: `a25fa626979b3f938e9cec232cbaef52771e9db3`
- 53 nodes
- 28 meshes
- 1 skin
- clips: `blink`, `idle`, `verify`

The automatic Higgsfield revision-5 GLB merged animation naming into one clip named `STEWARD_Rig`, so it was **not promoted** to runtime. The runtime v2 asset instead preserves the previously verified multi-clip rig and applies only the rev5 object-scale transforms after proving those mesh nodes are not animation targets.

## Canonical state vocabulary

Static state pack:

`steward.rig-state-assets/4.0`

Manifest:

`/assets/rig-states/rig-state-manifest-v4.json`

All twelve `PresenceProjection/1.0` states are rendered directly from revision 5:

`idle · thinking · planning · executing · inspecting · waiting · blocked · approval · verifying · approving · succeeded · failed`

The repository test suite compares this list directly against
`schemas/presence-projection.schema.json#/properties/displayed_state/enum`.
A semantic state added or removed from PresenceProjection therefore requires the visual profile to change in the same review.

The static renders remain fallbacks/presentation assets. They never become canonical state.

## Material and signal hierarchy

| Role | Rendering intent |
| --- | --- |
| cream shell | mineral/composite, non-metallic |
| structural dark | satin technical structure |
| visor | smoked optical glass |
| halo copper | physical copper without global glow |
| eyes + custody node | restrained signal |
| evidence badge | restrained semantic signal |
| evidence white | non-metallic evidence surface |

State color is secondary to pose:

- normal work states: restrained STEWARD copper/teal
- blocked / failed: restrained red
- approval / approving: amber
- verifying: teal
- succeeded: green/teal

No state changes character anatomy.

## Runtime hierarchy

```
steward-rig-v2.glb
        ↓
Three.js WebGL presence
        ↓
frontier-material/1.1
frontier-proportions/1.0
        ↓
idle / blink / verify
        ↓
rig-state-assets/4.0
        ↓
12 canonical PresenceProjection states
```

The renderer may fail closed from WebGL to a static rig-derived state without changing semantic source state.

## Truth boundary

The visual system always carries:

- `claim_class = projection-only`
- `canonical_truth = false`
- `authority_effect = false`
- `verification_effect = false`

A bright badge, animated ring, `approval` pose or `succeeded` pose cannot create authority, approval, execution truth or verification truth.

## Runtime verification

Before push of source commit `a25fa626979b3f938e9cec232cbaef52771e9db3`:

- GLB structure + SHA evidence: PASS
- 3 animation clips: PASS
- 12/12 state asset SHA integrity: PASS
- TypeScript: PASS
- Vite client build: PASS
- Vite SSR build: PASS
- desktop WebGL: PASS
- mobile + reduced motion: PASS
- forced GLB failure → rev5 idle fallback: PASS
- normal browser console/page errors: 0

## Current delivery observation

Higgsfield reports the rev5 production deployment as `deployed`.

Anonymous public access remains externally blocked:

```text
GET /                                              -> 401 {"error":"unauthenticated"}
GET /assets/steward-rig-v2.glb                    -> 401 {"error":"unauthenticated"}
GET /assets/rig-states/rig-state-manifest-v4.json -> 401 {"error":"unauthenticated"}
```

Repository inspection found no auth middleware or application 401 path. This remains tracked as the external Higgsfield edge/platform blocker in issue #28.

Do not weaken STEWARD source/runtime truth boundaries to work around that external hosting gate.

## Files

- `schemas/visual-frontier-profile.schema.json`
- `fixtures/valid/visual-frontier-profile.json`
- `fixtures/invalid/visual-frontier-profile-authority.json`
- `tests/test_visual_frontier_profile.py`
