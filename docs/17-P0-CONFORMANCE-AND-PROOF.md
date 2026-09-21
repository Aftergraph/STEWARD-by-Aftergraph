# P0 Conformance and Proof Plan v0.2

P0 is not considered proven because documents exist. It requires executable checks.

## Executable proof gates
1. Every JSON contract is valid Draft 2020-12 JSON Schema.
2. Positive fixtures validate against their declared contracts.
3. Negative fixtures are rejected for safety-relevant omissions.
4. Worktree isolation is demonstrated in a temporary Git repository.
5. Verification is bound to exact commit identity: a verdict for SHA A is stale after mutation to SHA B.
6. Core semantic invariants are executable tests: selected != authorized; completed != verified; delegated capability cannot exceed parent capability.
7. `git fsck --full` reports no repository corruption.
8. A Git bundle can reproduce the exact repository history and pass the same validation/tests after a clean clone.

## Current scope
These tests prove the specification seed and local reference semantics only. They do not prove production integration with AIE, Trust Gateway, WORKS, Sentinel, Runtime, GitHub, or provider infrastructure. Those are P1/P2 integration gates.

## Reproduce
```bash
make prove
```

A separate proof artifact should record exact commit SHA, tree SHA, commands, results and package hashes after each release candidate is cut.
