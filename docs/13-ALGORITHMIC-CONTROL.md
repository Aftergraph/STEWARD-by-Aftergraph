# Algorithmic Control Stack v0.1

## Global objective
STEWARD chooses among authorized policies/actions to maximize expected verified value while accounting for compute, money, latency, human attention and epistemic uncertainty.

Conceptually:

`argmax_{pi in authorized} E[ sum gamma^t * (VerifiedValue - λc Cost - λl Latency - λh HumanAttention - λu Uncertainty) ]`

Authority is a feasibility constraint, not a soft penalty.

## Controllers
- **Verified Mission Control** — constrained MPC/POMDP-style next-action control under partial observability.
- **Context Fidelity Allocator** — submodular/knapsack context selection with redundancy penalties and source rehydration.
- **JEV Decision Kernel** — bounded Bayesian decision selection with task-specific loss matrix and escalation thresholds.
- **Verified Capability Router** — contextual bandit/UCB/Thompson-style model/provider/tool routing using quality, latency, cost and failure probability.
- **Parallelism Governor** — Amdahl/critical-path/marginal-value logic for agent-count and topology decisions.
- **Collision Scheduler** — conflict graph over resources, Git scopes, artifacts and effect targets.
- **Evidence Fusion Controller** — Bayesian/likelihood evidence combination with correlation discounts for shared provenance.
- **Completion Controller** — acceptance predicates plus sequential evidence; no fixed-step completion assumption.
- **Habitat Placement Optimizer** — constrained assignment/min-cost flow for locality, hardware, cost, attestation and residency.
- **Trace Guard** — causal trace analysis with robust anomaly/drift statistics.
- **Harness Ratchet** — paired/holdout evaluation of bounded harness changes.
- **Attention Governor** — expected value of human interruption.
- **Experiment Director** — Bayesian experimental design / information gain for research.

## Performance accounting
Mission latency is decomposed into queue, context, reasoning, tool, synchronization, effect, readback and verification time. Cost includes model/API, compute, storage/network, human attention, verification and recovery.

Primary economic metric: Cost per Verified Outcome (CPVO). Value-oriented complement: Verified Value / Total Resource Cost.
