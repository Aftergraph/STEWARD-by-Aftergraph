# Git and Worktree Contract v0.1

## Role
Git provides versioned code lineage. Worktrees provide isolated mutable source workspaces. WORKS remains execution truth; Git does not replace Work/Attempt/Checkpoint semantics.

## Required baseline
Before mutating source code record repository identity, remote, base commit, branch, exact starting HEAD, upstream state, dirty/untracked state, existing worktrees and relevant PR/CI state.

## Default isolation
One independently mutating parallel Work unit should receive one isolated Git worktree by default. Read-only agents may share immutable source snapshots.

## WorktreeRef
Fields: id, repositoryRef, path, baseCommit, branchRef, headCommit, ownerWorkRef, ownerAgentRef, state, createdAt.

States: PROVISIONING, READY, ACTIVE, DIRTY, BLOCKED, COMMITTED, MERGED, ABANDONED, RELEASED.

## Integration
Parallel contributor outputs are combined in an IntegrationWorktree. Integration performs apply/rebase/cherry-pick/merge as appropriate, resolves conflicts, builds and runs integration/regression tests, producing an integrated exact SHA.

## Review and verification
ReviewWorktree: fresh exact-head checkout, normally read-only, for peer review.  
VerificationWorktree: fresh exact-subject environment used by independent verification/Sentinel.

## Subject invalidation
Review, test and verification evidence tied to SHA A does not automatically apply to SHA B. Commit, rebase, merge or generated-source changes may invalidate subject-bound evidence.

## Governed Git effects
Local edit is internal Habitat mutation. Push, PR creation/update, remote branch deletion, force push, merge, tag and release are external governed effects with egress and authority checks.

## Credential rule
Agents do not receive reusable organization Git tokens. Credentials are short-lived, scoped to principal/Mission/Work/repository/branch/operation/audience and brokered through Trust Gateway.

## Cleanup
A worktree is not destroyed while unpersisted changes exist without an explicit disposition. Cleanup records resulting commit/artifact/abandonment state.
