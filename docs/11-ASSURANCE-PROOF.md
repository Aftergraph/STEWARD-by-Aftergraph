# Assurance and Proof v0.1

## Sensor / Judge ladder
S0 deterministic invariants/tests  
S1 executable Oracle/current ground truth  
S2 JEV bounded semantic sensor  
S3 calibrated LLM judge  
S4 independent reviewer  
S5 reality readback  
S6 Sentinel exact-subject verification  
S7 Mission Acceptance

Use the cheapest sufficient sensor. Escalate when uncertainty, impact or evaluator limits require it.

## Independence
Agreement among agents is not epistemic quorum. Evidence independence may depend on provider/model, prompt, corpus, toolchain, code version, operator, region and time.

## Exact subject
VerificationVerdict records subject type and immutable version/hash/SHA. Changing the subject makes prior verdicts stale unless the verifier explicitly establishes equivalence.

## External effects
Effect lifecycle: authorize → durable EffectIntent/outbox → provider attempt → receipt/correlation → independent readback → applied/uncertain/failed → compensation if applicable.

Timeout is not success and not necessarily failure. `uncertain` is mandatory where state cannot be established safely.

## Mission acceptance
Node checks and review approvals are inputs. Mission Acceptance evaluates the Mission's desired state and acceptance criteria across relevant evidence/verdicts.
