# P2 Git worktree + exact-subject port

Status: composition binding implemented; live Habitat/Git effect proof pending.

## Ownership

STEWARD does not create a second sandbox/worktree subsystem. The port consumes an
injected Habitat/worker-sandbox provider and validates the minimum contract
required by the P2 coding slice.

Relevant existing Aftergraph assets discovered before implementing this port:

- `Aftergraph/skills-vault` defines the `using-git-worktrees` procedure:
  inspect state, avoid implementation on main, create an isolated worktree,
  prove intended base SHA and cleanliness, then record branch/path/base.
- `Aftergraph/intelligence-systems-research` already has a
  `WorkerSandbox` abstraction and a `HermesWorktreeSandbox` B0 backend with
  worktree-per-task isolation.

Those assets are reused as semantic/provider inputs. STEWARD owns only the
composition binding needed to connect a canonical Work/Attempt to the resulting
immutable Git subject.

## Contract

```text
Work + Attempt + repository + exact base SHA
    ↓
Habitat/sandbox provider
    ↓
isolated == true
clean == true
same Work + Attempt
same exact base SHA
    ↓
implementation
    ↓
candidate exact 40-hex SHA
    ↓
verificationSubject = candidate SHA
```

A branch is a navigation reference only. It is never verification truth.

## Fail-closed cases

- dirty workspace;
- provider cannot attest isolation;
- wrong Work or Attempt;
- wrong base SHA;
- candidate captured from another worktree;
- branch/ref supplied where an exact commit is required;
- provider unavailable.

There is no fallback to an unisolated workspace.

## Proof boundary

The STEWARD tests prove the composition contract and SHA/Work/Attempt binding.
They do not yet prove a live governed Git mutation. P2 still requires a real
Worktree effect through Runtime + WORKS + Trust Gateway/AIE, followed by exact
candidate-SHA verification in Sentinel.
