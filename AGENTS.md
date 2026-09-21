# Agent instructions

All agents working in this repository must read `.steward.md` first.

## Repository behavior
- Work on an explicit Mission/Work unit.
- Pin a base SHA before mutation.
- Use a dedicated worktree for independently mutating parallel work.
- Do not push, merge, tag, release, publish, send, purchase, or mutate external systems without the applicable governed effect path.
- Do not claim verification from self-review.
- If HEAD changes after review/verification, mark subject-bound evidence stale and rerun required gates.

## Documentation rule
Architecture terms are defined in `docs/02-DEFINITIONS.md`. Introduce new terms only with an ownership definition and a reason existing terms are insufficient.
