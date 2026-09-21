# P2 owner candidate lock

This file records the exact open owner candidates used by the staging
WORKS write/readback job. It is deliberately separate from
`contracts/p2-baseline-lock.json`: the baseline is frozen main-owner truth,
while this lock names unmerged candidates under review.

At capture time:

| Owner | Review | Exact candidate | State |
| --- | --- | --- | --- |
| WORKS | `Aftergraph/works-execution#127` | `b8016384a3ffd99acb9834676180811fabb6a12e` | open |
| Runtime | `Aftergraph/runtime#195` | `0dac1f4194adb50d5b49d4648e47fb956b352106` | open |
| Governance | `Aftergraph/after-graph-governance#185` | issue disposition pending | open |

The CI job checks out the exact WORKS candidate and runs the owner-backed
dispatch/context/replay and HTTP E2E tests in an ephemeral staging fixture.
It does not call production services, grant authority, or certify a Golden
Mission. A candidate head move invalidates this lock and requires a new
readback.
