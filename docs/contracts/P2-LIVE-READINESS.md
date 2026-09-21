# P2 live owner readiness gate

The composed Golden Mission MUST NOT run unless every consequential owner
binding is present and locally resolvable.

Run:

```bash
python -m steward.p2_live_readiness
```

Exit `0` means every declared binding is ready. Exit `2` means the mission is
blocked before dispatch. The JSON output uses
`steward.p2.live-readiness/0.1` and records no token or credential values.

Required deployment bindings:

| Binding | Owner |
|---|---|
| `STEWARD_RUNTIME_COMMAND` | Runtime V2 dispatch/subject bridge |
| `STEWARD_TRUST_GATEWAY_URL` | Trust Gateway V2.1 action surface |
| `STEWARD_TRUST_GATEWAY_TOKEN` | deployment secret provider |
| `STEWARD_HABITAT_COMMAND` | Habitat/worktree provider |
| `STEWARD_SENTINEL_COMMAND` | independent Sentinel verifier |

Readiness is necessary, not sufficient. A READY report does not prove a
successful mission, current authority, effect application, or verification.
