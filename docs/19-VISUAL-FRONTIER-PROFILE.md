# STEWARD Visual Frontier Profile v1.4

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

## Compact presence

Compact presence is not a second character system. It is a crop of the same revision-5 `STEWARD_Rig` for chat, cards, mobile and status rows.

Contract:

- schema: `steward.compact-presence-assets/1.0`
- manifest: `/assets/compact-presence/manifest-v1.json`
- source scene revision: `5`
- website source commit: `04b075c2ba609c08e8a39ca1936badc3c6153911`
- states: `idle · verifying · succeeded`
- proportion profile: `frontier-proportions/1.0`
- material profile: `frontier-material/1.1`
- geometry changed for compact crops: **false**

The three compact states are a strict subset of `PresenceProjection/1.0`. They must remain the same entity and may differ only through pose, restrained semantic signal and crop. Compact avatars never create a separate role identity.

The former website treatment mixed role and state semantics by presenting `Guide / Sentinel / Verified` as equivalent avatar categories. Revision 5 removes that ambiguity: compact presence is explicitly state-derived.

The website compact-presence section passed desktop and mobile browser QA with no page or console errors before source commit `04b075c2ba609c08e8a39ca1936badc3c6153911`.

## Motion / expression grammar

The runtime now implements the full Brand OS presence contract as a governed procedural layer above the three verified GLB clips.

Ownership remains split correctly:

- motion/character contract owner: `Aftergraph/brand`
- canonical contract id: `steward.presence.v1`
- STEWARD runtime implementation: `steward.motion-runtime/2.0`
- runtime manifest: `/assets/motion/presence-runtime-v2.json`
- runtime manifest SHA-256: `047464f20b75763d14d969fbb14fa16780a7d6dfdb554cb3a90e9e8809e92378`
- website source commit: `4c71ce1322281056c70dd896abefc03936fd43f6`

The baked GLB remains intentionally small and verified:

`idle · blink · verify`

The twelve semantic states are expressed as a procedural layer after `AnimationMixer.update()`. This is safe because the verified GLB writes the complete 20-bone pose channels on every baked clip frame, so the state offsets do not accumulate.

| State | Motion grammar | Accent token |
| --- | --- | --- |
| idle | ambient_breathe | steward_copper |
| thinking | visor_attention | steward_copper |
| planning | ordered_scan | system_blue |
| executing | forward_action | decision_amber |
| inspecting | focus_scan | control_cyan |
| waiting | slow_hold | slate |
| blocked | boundary_stop | decision_amber |
| approval | attention_gate | authority_violet |
| verifying | custody_ring_raise | pine_teal |
| approving | bounded_confirm | authority_violet |
| succeeded | settled_confirm | moss |
| failed | bounded_break | decision_amber |

Runtime signal semantics use canonical Brand OS token values rather than colors inferred from reference artwork.

Hard runtime bounds:

- state transitions: `160–420 ms`
- blink interval: `3.5–5.5 s`
- pointer orientation: at most `6°`
- reduced motion: no continuous motion, zero-duration state transition, preserve final pose and semantic label

The visual QA route accepts `?presence=<state>` only as an explicit visual preview. It does not change canonical state.

Falsification evidence before source commit `4c71ce1322281056c70dd896abefc03936fd43f6`:

- all 12 PresenceProjection states loaded independently: PASS
- exact motion id and accent token for all 12 states: PASS
- verified GLB clips remained `blink,idle,verify`: PASS
- normal executing state changed rendered pixels over time: PASS
- reduced-motion verifying state remained pixel-stable over time: PASS
- auto mode advanced `idle → thinking`: PASS
- console/page/network errors across 12 fixed-state cases: 0

Motion remains a projection. A motion, pose, color or halo pulse cannot create authority, approval, execution truth or verification truth.

## Governed presence inspector

The Blueprint surface now exposes the twelve canonical visual states as interactive controls without creating a second state machine.

Binding:

- surface: `steward.presence-inspector/1.0`
- website source commit: `12131e6fe54d8664bb4bb1977073036fbc50bb6a`
- state source: `motion_runtime.states`
- motion source: `motion_runtime.motions`
- router search key: `presence`
- live hero binding: `StewardThreeHero.mode`
- controls: `12`

Selecting a control updates typed router search state and drives the same WebGL presence runtime used by the hero. The inspector does not own or infer canonical state.

The UI carries the explicit boundary:

> Visual preview only · canonical state is untouched

Browser falsification before source commit `12131e6fe54d8664bb4bb1977073036fbc50bb6a`:

- 12/12 controls selectable: PASS
- URL `presence` state synchronized for all 12 controls: PASS
- inspector selected state synchronized for all 12 controls: PASS
- live WebGL hero `data-presence-state` synchronized for all 12 controls: PASS
- exactly one `aria-pressed=true` control after selection: PASS
- page/console errors: 0
- network errors: 0
- TypeScript: PASS
- Vite client + SSR builds: PASS

The inspector is a presentation and QA surface only. It cannot create authority, approval, execution truth or verification truth.

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
- normal browser console/page errors: 0\n- compact presence asset SHA integrity: PASS\n- compact presence desktop/mobile browser QA: PASS\n- 12-state motion grammar browser QA: PASS\n- reduced-motion pixel stability: PASS\n- normal-motion pixel change: PASS\n- auto-sequence advancement: PASS\n- governed presence inspector 12/12 control sync: PASS

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
