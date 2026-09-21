# Component and Ownership Model v0.1

| Component | Logical responsibility | Canonical state owner | STEWARD role |
|---|---|---|---|
| Surface / Composer / Projects | human interaction and workspace projection | STEWARD | owner |
| Context Engine | recall/retrieval/frame composition | STEWARD + referenced sources | owner of composition, not source data |
| Memory Fabric | working/project/personal/episodic memory | STEWARD/context-continuity as integrated | composition/integration |
| BRAIN | promoted semantic knowledge | designated Brain store | consumer/promoter through policy |
| LOOM | Goal→Mission→Graph compilation | Mission contract owner | compiler |
| COMPASS | intelligence/capability/resource allocation | STEWARD | owner |
| MUSTER/CHORUS/CONDUCTOR | team topology, claims, coordination, schedule intent | STEWARD + WORKS claims | coordinator |
| HARNESS | per-agent loop/tool/context/completion envelope | STEWARD | owner of profile/composition |
| HABITAT | environment specification/composition | runtime/substrate providers | requester/composer |
| Authority | normative permission/delegation/budget/revocation | AIE | client |
| Enforcement | approvals/credentials/egress/policy enforcement | Trust Gateway | client |
| Durable Work | Work, attempts, leases, checkpoints, effects | WORKS | client/orchestrator |
| Verification | independent exact-subject verdict | Sentinel | requester/consumer |
| Model capability truth | model metadata/version | Model Registry | consumer/router |
| Skills | skill packages/contracts | Skills Vault / Skill ABI | consumer/activation |
| TRACE | causal lineage across components | federated trace fabric | producer/consumer |
| BENCH | distributional evaluation | research/bench systems | consumer/producer |
| EVOLVE | improvement candidate lifecycle | STEWARD + governance gates | proposer/orchestrator |

## Repository role
`Aftergraph/steward` should be the product/integration root. It must reference external canonical owners rather than copy their state machines into local stores.

## UI migration rule
Existing Studio/FIHIM/WI interfaces are migration/integration sources until an explicit governance decision assigns canonical STEWARD UI ownership. No silent duplicate source of truth is introduced here.
