# Harness and Habitat Contract v0.1

## Harness
A Harness is the dynamically assembled execution envelope around an AgentInstance.

Evolvable functional modules:
- Agent Loop
- Tool Use
- Observation Management
- Context Management
- Completion Detection

Supporting layers:
- Guides/instructions
- Memory access
- Permission interface
- Sensors/evaluators
- Retry/recovery
- Budgets/limits
- Observability

Harness may evolve only within governed module scopes; authority/enforcement/verification owners are protected boundaries.

## Habitat
Habitat is the bounded computer/environment used to execute Work.

Environment capabilities may include filesystem, shell, Python/runtime, browser, desktop/computer use, container, VM, CPU/GPU, network and mounted capabilities.

## CapabilityMount
A mount references Skills, Tools, CRAFT operations, protocol bridges, connectors, artifacts or feeds. Availability does not equal authorization.

## Internal/external boundary
Open-ended computation is allowed inside appropriately isolated Habitat. Consequential external mutations cross the Trust Gateway using typed EffectContracts and delegated authority.

## Self-build
An agent may create a temporary local tool for a Mission, test it and use it inside its authorized environment. Reusable promotion requires security/evaluation/conformance before Catalog/Skills admission.
