# Initial API / Contract Surface v0.1

These are logical contract families, not commitments to deploy one service per noun.

## Ingress
- `IntentEnvelope`
- `CommandEnvelope`
- `SteerEvent`

## Project/context
- `ProjectRef`
- `ThreadRef`
- `ContextRef`
- `MemoryCandidate`

## Mission/coordination
- `MissionRef`
- `MissionNodeContract`
- `WorkIntent`
- `WorkClaim`
- `TeamState`

## Harness/environment
- `HarnessProfile`
- `HabitatSpec`
- `CapabilityMount`
- `ProviderBinding`

## Git
- `RepositoryRef`
- `WorktreeRef`
- `GitExecutionContext`
- `GitEffectIntent`

## Output/assurance
- `ArtifactRef`
- `EffectIntent`
- `Observation`
- `EvidenceRef`
- `VerificationVerdictRef`
- `MissionAcceptanceRef`

## Telemetry
- `TraceContext`
- `ProjectionEvent`
- `MeterSample`

Contract fields should use opaque IDs/refs rather than duplicating canonical objects owned by other repositories.
