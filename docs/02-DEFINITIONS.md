# STEWARD Definitions v0.1

## Intent and work
- **Goal** — durable desired direction; the WHY.
- **Mission** — bounded desired state with acceptance, risk, budget and authority context; the WHAT.
- **MissionGraph** — typed executable dependency graph; the HOW.
- **MissionNode** — one graph work unit with preconditions, capabilities, effect expectations and evidence obligations.
- **Work** — durable execution object owned by WORKS for one schedulable unit.
- **Attempt** — one concrete execution attempt of Work.
- **TODO** — human/agent planning projection; not execution truth.
- **Queue** — scheduler state for ready/waiting/blocked/retry/background Work.
- **SteerEvent** — typed correction/control input applied at a safe interruption point.

## People and actors
- **Principal** — human or organizational authority source.
- **BotIdentity** — persistent STEWARD/Bot persona identity; not a human identity.
- **AgentInstance** — instantiated cognitive worker with bounded context/harness.
- **WorkerIdentity** — execution identity attached to leased Work.
- **WorkloadIdentity** — environment/runtime identity used for machine-to-machine access.

## Project and conversation
- **Project** — persistent organizational/context namespace for related goals, missions, threads, resources and memory.
- **Thread** — interaction or coordination lineage; conversation is not the system database.
- **Library** — federated user-facing discovery projection over reusable content/resources.
- **Catalog** — federated discovery of operational capabilities.

## Context and memory
- **Observation** — sourced input from user, tool, world or system before epistemic acceptance.
- **THREAD** — selected active working memory.
- **RECALL** — retrieval orchestration across memory/content sources.
- **VERITY** — epistemic reconciliation of freshness, contradiction, provenance and confidence.
- **CHRONICLE** — episodic trajectory memory of what happened.
- **PROFILE** — durable preferences/context about a principal or organization.
- **BRAIN** — promoted semantic knowledge; revisable and never authority.
- **SKILL** — procedural intelligence with capability requirements and an evaluation contract.

## Code and Git
- **RepositoryRef** — identity/reference to a live source-control repository.
- **BranchRef** — movable Git ref; not immutable subject identity.
- **CommitSHA** — immutable Git subject identity used for exact code verification.
- **WorktreeRef** — identity and lineage of an isolated mutable Git worktree leased to Work/Agent.
- **IntegrationWorktree** — isolated worktree for combining parallel contributor changes.
- **ReviewWorktree** — fresh, normally read-only worktree for exact-head review.
- **VerificationWorktree** — fresh environment/worktree for independent exact-subject verification.
- **GitExecutionContext** — WORKS linkage among Work, repo, base, worktree, branch, current HEAD, changeset and PR.

## Execution and output
- **Habitat** — dynamically assembled least-privilege execution environment.
- **Harness** — execution/cognition envelope around an AgentInstance: loop, tools, context, completion, recovery, sensors.
- **EffectIntent** — durable description of a proposed consequential external mutation.
- **Effect** — actual external-world mutation attempt/result.
- **Artifact** — durable, versioned work object with content identity and provenance.
- **Deliverable** — selected/package of artifacts presented as a Mission output.

## Assurance and learning
- **Evidence** — information that supports or refutes a claim.
- **Oracle** — executable/reference mechanism capable of recomputing ground truth for a bounded claim/task.
- **VerificationVerdict** — verifier conclusion tied to an exact subject/version.
- **VerifiedOutcome** — Mission outcome that satisfied acceptance under required verification.
- **ExperienceTrajectory** — state/action/observation/outcome sequence used for analysis/evaluation/learning.
- **RATCHET** — governed mechanism converting recurring verified failures/successes into bounded improvement candidates.
