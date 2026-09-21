# P2 Trust Gateway execution port

Status: V2.1 client implemented; live cross-repo evidence pending.

Baseline owner: `Aftergraph/trust-gateway@8a2c8d66a67d036227c77904844f105b39723f58`.

## Canonical path discovered

The locked Trust Gateway baseline exposes `POST /v1/actions`. When the request
contains `execution_context_id`, the server executes the Platform V2.1 path:

```text
TG current identity
  ↓
WORKS execution-context/1.0
  ↓
identity + mission binding
  ↓
AIE live revalidate(action_id)
  ↓
authority_lease_id == immutable WORKS context
  ↓
TG execution-phase PDR
  ↓
durable PDR correlation back into WORKS
  ↓
tool dispatch
```

This corrects an earlier abstraction that could be read as STEWARD calling AIE
directly. STEWARD must use the canonical execution path; Trust Gateway is the
execution-side enforcing plane and performs the live AIE revalidation.

## No legacy path

The underlying TG server still supports legacy requests without
`execution_context_id` during migration. `TrustGatewayClient` intentionally
does not: `action_id`, `execution_context_id`, `mission_id` and `tool` are
mandatory before network dispatch.

## Approval

HTTP 202 `needs_approval` is represented as a first-class
`TrustGatewayApprovalRequired`, not as success and not as a denial.
Approval authorizes another authorization attempt; the TG baseline repeats the
V2.1 authority chain after approval before dispatch.

## Proof boundary

The local tests prove the STEWARD port:
- always sends the V2.1 context-bound action envelope;
- cannot silently use the legacy execution path;
- rejects mismatched context/PDR responses;
- treats AIE revocation/unavailability and WORKS correlation failure as fail-closed;
- preserves `needs_approval` as a distinct state.

They do not prove a live AIE/TG/WORKS deployment yet.
