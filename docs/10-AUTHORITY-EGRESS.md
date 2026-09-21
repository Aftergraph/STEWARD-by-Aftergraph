# Authority, Delegation and Egress v0.1

## Authority lattice
Child delegation cannot exceed parent authority:
- capabilities_child ⊆ capabilities_parent
- scope_child ⊆ scope_parent
- budget_child ≤ delegated budget
- expiry_child ≤ expiry_parent

## Risk vs authority
Risk classification determines required controls. It does not create authority. High expected utility cannot compensate for missing authority.

## Actor lineage
HumanPrincipal → BotIdentity → AgentInstance → WorkerIdentity → HabitatIdentity/WorkloadIdentity.

Every consequential action preserves rootIntentRef, MissionRef, WorkRef and delegation lineage.

## Egress
Network reachability does not imply allowed data egress. Egress decisions consider destination, method, payload class, sensitivity, purpose, rate, effect class and authority.

Examples:
- public documentation read: network read policy;
- private source clone: sensitive authorized read;
- Git push: external repository mutation;
- email/payment/deploy: consequential external effect.

## Credential brokerage
Secrets remain outside model-visible state when possible. Trust Gateway issues ephemeral credentials/proxies bound to audience and authorized operation.
