# Infrastructure Topology Plan v0.1

## Principle
SUBSTRATE provides infrastructure primitives. HABITAT assembles a bounded environment from those primitives. Neither owns Mission, authority or verification semantics.

## Fabrics
1. **Compute Fabric** — local CPU/GPU, VDS, cloud pools, browser workers, future edge/robot compute.
2. **Network Fabric** — connectivity, segmentation, service identity, ingress/egress paths.
3. **Identity Fabric** — principal, bot, agent, worker, workload and machine identities.
4. **Data Fabric** — object/CAS, relational state, append logs, caches, indexes, snapshots.
5. **Event Fabric** — durable machine/system events; distinct from user-facing FLOW.
6. **Secret Fabric** — vault + credential broker; credentials are scoped and short-lived.
7. **Service Fabric** — discovery, health, routing, internal service connectivity.
8. **Cache Fabric** — prefix/result/index caches; cache is never semantic truth.
9. **Delivery Fabric** — build artifacts, SBOM, signatures, deployment and rollback mechanics.
10. **Observability Fabric** — traces, metrics, logs, profiles, SLOs.
11. **Resilience Fabric** — replication, backup, failover, restore and disaster recovery.
12. **Placement/Scheduling Fabric** — maps Work requirements to eligible compute/environment providers.

## Minimum infrastructure for P0/P1
- PostgreSQL-class durable relational store for STEWARD-owned metadata/projections.
- Object/CAS storage for artifact and evidence bytes.
- Durable queue/event transport compatible with WORKS lifecycle.
- OpenTelemetry-compatible trace export.
- Secret broker through Trust Gateway rather than app-managed master keys.
- Local/container sandbox provider plus browser/computer provider.
- Git repository cache/worktree manager.
- Search/index backend supporting exact + lexical + vector/hybrid retrieval.

## Environment classes
- E0 ephemeral turn/tool environment
- E1 attempt-scoped
- E2 Mission-scoped
- E3 Project-scoped
- E4 Bot-scoped persistent workspace
- E5 attached device/edge environment

## Habitat lifecycle
REQUEST → PROVISION → ATTEST → COLD → AUTHORITY RESOLUTION → ACTIVATE → RUN → CHECKPOINT → EXPORT → SUSPEND/DESTROY.

A cold Habitat may contain code/files/tools but must not gain consequential credentials or unrestricted egress until activation is authorized.

## Resilience rule
Failover restores state, not permission. Authority is revalidated after restore/resume.
