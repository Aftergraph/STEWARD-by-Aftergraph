# P2 Git Worktree Habitat primitive

Status: executable local isolation primitive implemented; live WORKS/Runtime binding pending.

## Role

Git worktrees are a Habitat filesystem isolation primitive. They are not:
- Work truth;
- authority;
- evidence;
- verification;
- merge permission.

STEWARD may provision and inspect a local worktree. The binding must later be
correlated into canonical WORKS Work/Attempt state.

## Contract

`WorktreeSpec` requires:
- an existing Git repository root;
- exact 40-hex `base_commit`;
- target path;
- `work_id`;
- `attempt_id`;
- optional validated branch name.

Provisioning performs no network operation. It validates the exact base commit,
uses `git worktree add`, then independently reads back the new worktree HEAD.
A mismatch fails closed and the worktree is removed.

Default mode is detached HEAD. A named branch is created only when explicitly
requested.

Release refuses a dirty worktree unless `force=True`, preserving the law:

```
worktree cleanup != permission to lose unpersisted work
```

## Isolation proof

Tests use real Git repositories and real `git worktree` operations. They prove
that a mutation in one independently provisioned worktree does not mutate a
second worktree based on the same exact commit.

## Production proof boundary

This primitive does not yet demonstrate:
- the worktree lease persisted in WORKS;
- provisioning by the production Runtime/Habitat executor;
- TG-governed Git remote egress;
- exact candidate SHA passed to Sentinel.

Those remain P2 integration gates.
