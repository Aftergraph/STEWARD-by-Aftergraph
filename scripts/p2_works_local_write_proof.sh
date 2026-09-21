#!/usr/bin/env bash
# P2 local write proof for the canonical WORKS owner.
#
# This is deliberately a staging-only proof. The selected WORKS tests use
# httptest + SQLite under Go testing temp directories; they do not call a
# production endpoint, provider, GitHub mutation, or customer data source.
set -euo pipefail

works_root="${1:?usage: $0 WORKS_CHECKOUT EXPECTED_WORKS_SHA}"
expected_head="${2:?usage: $0 WORKS_CHECKOUT EXPECTED_WORKS_SHA}"

if [[ ! -d "$works_root/.git" ]]; then
  echo "WORKS checkout is not a git repository: $works_root" >&2
  exit 1
fi

actual_head="$(git -C "$works_root" rev-parse HEAD)"
if [[ "$actual_head" != "$expected_head" ]]; then
  echo "WORKS exact-head mismatch: got $actual_head want $expected_head" >&2
  exit 1
fi

# Never inherit a production binding into this local write proof.
for var in   WORKS_API WORKS_API_URL WORKS_DB WORKS_GITHUB_TOKEN WORKS_WEBHOOK_SECRET   WORKS_PLATFORM_BRIDGE_SECRET WORKS_API_TOKEN WORKS_ENROLL_SECRET; do
  if [[ -n "${!var:-}" ]]; then
    echo "refusing to run with external WORKS binding in $var" >&2
    exit 1
  fi
done

proof_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/steward-p2-works-write.XXXXXX")"
cleanup() {
  rm -rf -- "$proof_root"
}
trap cleanup EXIT

# A marker makes the write/cleanup boundary observable without persisting an
# artifact. The actual durable writes happen inside the owner-backed tests.
marker="$proof_root/write-marker"
printf 'steward-p2-local-write:%s\n' "${GITHUB_RUN_ID:-local}" > "$marker"
test -s "$marker"

set -o pipefail
(
  cd "$works_root"
  go test ./services/api \
    -run '^TestDispatchV2(MaterializesResolvableExecutionContext|SubjectBindingIsExactOnceAndIdempotent|ReplayReturnsSameCorrelation)$' \
    -count=1 -v
) | tee "$proof_root/dispatch-v2.log"

(
  cd "$works_root"
  go test -tags=e2e ./e2e \
    -run '^TestE2E_WorkSucceeds$' \
    -count=1 -v
) | tee "$proof_root/e2e.log"

grep -q 'PASS' "$proof_root/dispatch-v2.log"
grep -q 'PASS' "$proof_root/e2e.log"

printf '{"schema":"steward.p2.local-works-write-proof/0.1","works_head":"%s","dispatch_v2_write_readback":"PASS","http_e2e_work_write_readback":"PASS","production_binding":"absent"}\n' "$actual_head" | tee "$proof_root/result.json"

rm -f -- "$marker" "$proof_root/dispatch-v2.log" "$proof_root/e2e.log" "$proof_root/result.json"
rmdir -- "$proof_root"
trap - EXIT
test ! -e "$proof_root"
printf 'P2_LOCAL_WORKS_WRITE_PROOF=PASS\n'
