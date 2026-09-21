# Organization, Queue and Steering Contract v0.1

## MUSTER
Chooses the role/team topology needed for a Mission. Team selection does not spawn agents automatically and never grants authority.

## CHORUS
Coordinates independent actors with WorkIntent, WorkClaim, collision detection, deduplication, handoffs and shared tactical state.

Claim scopes may be repository, branch, path, symbol, artifact, dataset, provider resource or external effect target.

WorkClaim is a coordination lease, not an AuthorityGrant.

## Parallelism Governor
Before spawning additional agents, estimate serial fraction, critical path, coordination overhead, duplicate probability, join latency and verifier cost. Spawn only where expected marginal verified progress exceeds added cost/risk.

## Queue
Durable scheduler categories: ready, waiting, blocked, delayed, retry, background. Scheduling accounts for critical-path importance, deadlines, expected verified value, unblock value, resource cost, fairness and risk controls.

## TODO
TODO is a human/agent planning projection. A TODO becomes executable only after LOOM compiles it into a MissionNode/Work path.

## STEER
Typed steer kinds include correction, constraint, context, priority, pause, resume, cancel and takeover. Steer is applied at a safe interruption/revalidation boundary, not as arbitrary mutation of canonical state.
