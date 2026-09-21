# Research and Validation Plan v0.1

STEWARD engineering claims are hypotheses until supported by evidence.

## Baseline experiment
Use identical software-engineering missions across:
1. conventional chat/agent baseline;
2. minimal Mission contract;
3. STEWARD reference vertical slice.

Measure verified success rate, first-correct-run, correction/recovery, CPVO, time-to-verified-outcome, human intervention, context use and unauthorized actions.

## Ablation program
baseline → +Mission → +state → +authority → +verification → +evidence → +recovery → +worktree isolation → +context control → +multi-agent coordination → full.

## Failure injection
Mandatory scenarios include model failure, tool timeout, stale branch/head, provider drift, corrupted context, credential revocation, duplicated external effect, worker crash, network partition and verifier disagreement.

## Generalization
A mechanism should be tested across more than one model/provider and across unseen task instances before being described as generalizable.

## Kill criteria
Remove or simplify a mechanism when its measured benefit does not justify latency, token, compute, operational or human-attention cost.
