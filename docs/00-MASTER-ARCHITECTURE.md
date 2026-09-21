# STEWARD Master Architecture v0.1

```text
HUMAN / WORLD
    |
    v
+--------------------------------------------------------------------------------------------------+
| SURFACE / CHANNELS / FLOW                                                                        |
| Web | Mobile | CLI/TUI | IDE/ACP | Messaging | Voice | API                                      |
| Composer | Search | Command ABI | Artifact Canvas | Live Computer | Needs You                   |
+----------------------------------------------+---------------------------------------------------+
                                               | IntentEnvelope / CommandEnvelope
                                               v
+--------------------------------------------------------------------------------------------------+
| PROJECT WORKSPACE                                                                                |
| Project -> Goals | Missions | Threads | Memory | Library | Artifacts | Routines | Decisions      |
|          -> Repositories | PRs | Worktree views | Connections | Environments | Evidence          |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| INIT / ACTUAL-STATE BASELINE                                                                     |
| Project/Mission/Actor | active Work/TODO | tools/skills | provider health                        |
| Git: fetch | repo | branch | exact HEAD | upstream | dirty | worktrees | PR head/base | CI        |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| CONTEXT ENGINE                                                                                   |
| SIGHTLINE -> OBSERVATION -> RECALL -> RETRIEVE -> VERITY -> ELICIT -> SPEC -> FRAME              |
| exact/BM25/vector/hybrid | owned index | live fetch | project library                            |
+-------------------------+------------------------------------+-----------------------------------+
                          |                                    |
                          v                                    v
+-----------------------------------------------+   +----------------------------------------------+
| MEMORY FABRIC                                 |   | CONTEXT FIDELITY ALLOCATOR                   |
| THREAD / SESSION / PROJECT MEMORY             |   | relevance + freshness + provenance          |
| -> CHRONICLE / PROFILE / TOPICS               |   | - redundancy under context budget           |
| -> CONSOLIDATE -> BRAIN / SKILLS              |   | compress for navigation; rehydrate decision |
+-------------------------+---------------------+   +---------------------------+------------------+
                          \_____________________________________________________/
                                                    |
                                                    v
+--------------------------------------------------------------------------------------------------+
| STEWARD MIND                                                                                     |
| REASON: deterministic | JEV | ML | LLM | symbolic/causal                                        |
| META-CONTROL <-> PACE <-> SIMSPACE | DOMAIN MODEL | OPPORTUNITY                                  |
| LOOM: Goal -> Mission -> Graph                                                                    |
| COMPASS: intelligence/model/provider/retrieval/skill/tool/verifier/compute/environment/topology  |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| PROVIDER / MODEL FABRIC                                                                          |
| Model Registry -> capability match -> Verified Capability Router -> provider binding             |
| quality | latency | cost | privacy | modality | tools | health | region | cache/fallback          |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| STEWARD ORGANIZATION                                                                            |
| MUSTER -> PARALLELISM GOVERNOR -> CHORUS -> COMPOSITION SAFETY -> CONDUCTOR                      |
| CHORUS: intent board | WorkClaims | collision graph | dedup | handoff | shared tactical state    |
| Git claims: repo | path | symbol | branch | worktree | generated output                          |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| TODO / QUEUE / STEER                                                                             |
| TODO planning projection | durable ready/waiting/blocked/retry/background queue                  |
| STEER -> steering queue -> priority gate -> safe interruption/replan                             |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| HARNESS                                                                                          |
| Guides | Agent Loop | Tool Use | Observation Mgmt | Context Mgmt | Completion Detection           |
| recovery | retry | budgets | sensors | checkpoints | observability | progressive skill loading     |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| HABITAT PREPARATION                                                                               |
| Workspace | Artifact mounts | sandbox/container/VM/browser/desktop/CPU/GPU                        |
| WORKTREE MANAGER: validate base SHA -> git worktree add -> branch bind -> lease -> cleanup       |
| Capability mounts: CRAFT | DISCOVER | MEDIA | SKILLS | TOOLS | MCP/A2A/ACP | CONNECT | FEEDS    |
+----------------------------------------------+---------------------------------------------------+
                                               | proposed capability/effect
                                               v
+--------------------------------------------------------------------------------------------------+
| ACTOR IDENTITY / ALIGN / INSTITUTION                                                              |
| Human -> Bot -> AgentInstance -> Worker -> Habitat/Workload identity                               |
| ALIGN -> CHARTER -> AIE -> TRUST GATEWAY                                                          |
| risk | authority | delegation | attenuation | budget | expiry | approval | credentials | egress   |
+----------------------------------------------+---------------------------------------------------+
                                               | authorized activation
                                               v
+--------------------------------------------------------------------------------------------------+
| ACTIVE HABITAT / CRAFT                                                                            |
| BASELINE -> DESIGN SEARCH -> PROBE -> BUILD -> DEBUG -> TEST -> REVIEW -> RELEASE -> SELF-BUILD  |
| GIT ENGINE: status/diff/log/blame/commit/bisect/cherry-pick/rebase/merge/revert/conflicts/PR      |
| DISCOVER: frontier map -> hypothesis -> experiments -> ablation -> falsification                  |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| WORKS -- DURABLE EXECUTION TRUTH                                                                  |
| Work | WorkerLease | ComputeLease | EnvironmentLease | Attempt | Checkpoint | Progress             |
| EffectIntent | Idempotency | Outbox | ArtifactRef | EvidenceRef | Recovery | Quittance              |
| GitExecutionContext: repo/base/worktree/branch/startHead/currentHead/changeSet/commits/PR         |
| FOREGROUND <-> BACKGROUND                                                                         |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| SUBSTRATE                                                                                         |
| Compute | Network | Identity | Data | Event | Secret | Service | Cache | Delivery | Observability  |
| Resilience | Placement/Scheduling     LOCAL | EDGE | VDS | CLOUD | GPU | Browser Pool | Device     |
+----------------------------------------------+---------------------------------------------------+
                                               |
                     +-------------------------+---------------------------+
                     |                                                     |
                     v                                                     v
+-----------------------------------------------+      +--------------------------------------------+
| CONSEQUENTIAL EFFECT                          |      | INTERNAL OUTPUT                            |
| EffectIntent -> outbox -> provider mutation   |      | text/code/files -> DELIVER                |
| -> receipt -> WORLD -> independent READBACK   |      | -> synthesize/package -> Deliverable      |
| -> applied / uncertain / failed / compensate  |      | -> ARTIFACT FABRIC                        |
+--------------------------+--------------------+      +---------------------+----------------------+
                           \_______________________________________________/
                                               |
                                               v
+--------------------------------------------------------------------------------------------------+
| GIT REMOTE / INTEGRATION / EXACT SUBJECT                                                         |
| local commit -> governed push/PR/merge/tag -> remote readback                                    |
| contributor worktrees -> IntegrationWorktree -> integrated SHA                                   |
| exact PR HEAD -> ReviewWorktree -> VerificationWorktree                                           |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| ASSURANCE                                                                                         |
| S0 invariant -> S1 executable ORACLE -> S2 JEV -> S3 calibrated LLM judge                         |
| -> S4 independent reviewer -> S5 reality readback -> S6 SENTINEL -> S7 Mission Acceptance        |
| Verification binds to exact subject SHA/version                                                    |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| VERIFIED OUTCOME -> VALUE / BENCH / CALIBRATE / CHRONICLE                                         |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| LEARN / EVOLVE / VERIFIED RSI                                                                     |
| trajectory -> contrast success/failure -> deficiency -> bounded candidate                         |
| -> replay -> benchmark-disjoint holdout -> ALIGN -> shadow -> guarded -> promoted                 |
| targets: memory | brain | skill | harness | routing | topology | debug/review heuristics | model  |
+----------------------------------------------+---------------------------------------------------+
                                               v
+--------------------------------------------------------------------------------------------------+
| WARD -> WAKE -> ROUTINES / LOOP -> OPPORTUNITY -> SUGGESTION -> ATTENTION -> PROJECTION / FLOW   |
|                                             \______________________________________________ -> APP |
+--------------------------------------------------------------------------------------------------+
```

## Cross-cutting planes

```text
GOVERNANCE | ACTOR IDENTITY | TRACE | CONTROL | METER | CUSTODY | EGRESS | CATALOG | PROJECTION | ALIGN
```

## Canonical Git path

```text
Mission
 -> WorkClaims
 -> Base SHA
 -> isolated contributor Worktree(s)
 -> changes/tests
 -> commit(s)
 -> IntegrationWorktree
 -> integrated exact SHA
 -> ReviewWorktree
 -> VerificationWorktree
 -> Sentinel
 -> governed push/PR/merge/release
 -> remote readback
 -> Verified Outcome
 -> Learn
```
