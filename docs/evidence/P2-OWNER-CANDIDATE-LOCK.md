# P2 owner candidate lock

This file records the exact open owner candidates used by the staging
WORKS write/readback job. It is deliberately separate from
`contracts/p2-baseline-lock.json`: the baseline is frozen main-owner truth,
while this lock names unmerged candidates under review.

At capture time:

| Owner | Review | Exact candidate | State |
| --- | --- | --- | --- |
| WORKS | `Aftergraph/works-execution#127` | `64cabe65bf210b2c65b525750acb45fc6d53894d` | open |
| Runtime | `Aftergraph/runtime#195` | `d9c5efb3a74222326ec71b06d5c2df2d4215d68f` | open |
| Governance | `Aftergraph/after-graph-governance#185` | issue disposition pending | open |

The CI job checks out the exact WORKS candidate and runs the owner-backed
dispatch/context/replay and HTTP E2E tests in an ephemeral staging fixture.
It does not call production services, grant authority, or certify a Golden
Mission. A candidate head move invalidates this lock and requires a new
readback.
