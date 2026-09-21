#!/usr/bin/env bash
# P2 same-causal remote proof:
# Runtime -> WORKS -> TG V2.1 -> AIE action-time revalidation -> WORKS PDR
# correlation -> governed remote Git egress -> exact remote readback -> Sentinel
# -> Runtime/WORKS exact subject binding -> STEWARD owner-acceptance readiness.
#
# Proof-only on a dedicated branch. No production deployment is claimed.
set -euo pipefail

runtime_root="${1:?missing Runtime checkout}"
works_root="${2:?missing WORKS checkout}"
tg_root="${3:?missing Trust Gateway checkout}"
aie_root="${4:?missing AIE checkout}"
expected_runtime="${5:?missing Runtime SHA}"
expected_works="${6:?missing WORKS SHA}"
expected_tg="${7:?missing Trust Gateway SHA}"
expected_aie="${8:?missing AIE SHA}"
sentinel_root="${9:?missing Sentinel checkout}"
expected_sentinel="${10:?missing Sentinel SHA}"
steward_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${P2_GITHUB_TOKEN:?P2_GITHUB_TOKEN required}"
: "${P2_TARGET_REPO:?P2_TARGET_REPO required}"
: "${P2_TARGET_PR:?P2_TARGET_PR required}"
: "${P2_TARGET_BRANCH:?P2_TARGET_BRANCH required}"
: "${P2_SHA_A:?P2_SHA_A required}"
: "${P2_SHA_B:?P2_SHA_B required}"

for pair in \
  "$runtime_root:$expected_runtime:Runtime" \
  "$works_root:$expected_works:WORKS" \
  "$tg_root:$expected_tg:Trust-Gateway" \
  "$aie_root:$expected_aie:AIE" \
  "$sentinel_root:$expected_sentinel:Sentinel"; do
  root="${pair%%:*}"
  rest="${pair#*:}"
  expected="${rest%%:*}"
  label="${rest##*:}"
  actual="$(git -C "$root" rev-parse HEAD)"
  [[ "$actual" == "$expected" ]] || {
    echo "$label exact-head mismatch: got $actual want $expected" >&2
    exit 1
  }
done

for var in WORKS_API_URL WORKS_API_TOKEN WORKS_BASE_URL WORKS_BEARER_TOKEN \
  WORKS_PLATFORM_BRIDGE_SECRET AIE_RUNTIME_PATH AIE_STATE_FILE \
  STEWARD_TRUST_GATEWAY_URL STEWARD_TRUST_GATEWAY_TOKEN; do
  if [[ -n "${!var:-}" ]]; then
    echo "refusing proof with inherited external binding in $var" >&2
    exit 1
  fi
done

command -v node >/dev/null
command -v python3 >/dev/null
command -v go >/dev/null
command -v gh >/dev/null

dispatch_cli="$runtime_root/packages/runtime-host/dist/steward-dispatch-v2-cli.js"
bind_cli="$runtime_root/packages/runtime-host/dist/steward-bind-subject-v2-cli.js"
if [[ ! -s "$dispatch_cli" || ! -s "$bind_cli" ]]; then
  pnpm_run() {
    if command -v pnpm >/dev/null 2>&1; then
      pnpm "$@"
    elif command -v corepack >/dev/null 2>&1; then
      corepack pnpm "$@"
    elif command -v npx >/dev/null 2>&1; then
      npx --yes pnpm@11.20.0 "$@"
    else
      echo "pnpm unavailable" >&2
      return 1
    fi
  }
  (
    cd "$runtime_root"
    pnpm_run install --frozen-lockfile
    pnpm_run --filter @aftergraph/runtime-host build
  )
fi
[[ -s "$dispatch_cli" ]] || { echo "Runtime V2 dispatch CLI missing" >&2; exit 1; }
[[ -s "$bind_cli" ]] || { echo "Runtime V2 subject-binding CLI missing" >&2; exit 1; }

proof_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/steward-p2-remote-causal.XXXXXX")"
proof_test="$works_root/services/api/steward_remote_same_causal_test.go"
cleanup() {
  rm -f -- "$proof_test"
  rm -rf -- "$proof_root"
}
trap cleanup EXIT

cat > "$proof_root/remote_effect_harness.js" <<'NODEEOF'
'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const tgRoot = process.env.STEWARD_TG_ROOT;
const aieRoot = process.env.STEWARD_AIE_ROOT;
const stateFile = process.env.STEWARD_AIE_STATE;
const sentinelRoot = process.env.STEWARD_SENTINEL_ROOT;
const token = process.env.P2_GITHUB_TOKEN;
const targetRepo = process.env.P2_TARGET_REPO;
const targetPR = process.env.P2_TARGET_PR;
const targetBranch = process.env.P2_TARGET_BRANCH;
const shaA = process.env.P2_SHA_A;
const shaB = process.env.P2_SHA_B;
if (!tgRoot || !aieRoot || !stateFile || !sentinelRoot || !token ||
    !targetRepo || !targetPR || !targetBranch || !shaA || !shaB) {
  throw new Error('remote proof configuration missing');
}

const { authorizeV21Action } = require(path.join(tgRoot, 'src/gateway/platform-execution.js'));
const { actionFingerprint } = require(path.join(tgRoot, 'src/gateway/aie-client.js'));
const { open } = require(path.join(tgRoot, 'src/gateway/db.js'));
const { SecretsVault } = require(path.join(tgRoot, 'src/gateway/secrets-vault.js'));
const { CredentialHandleStore } = require(path.join(tgRoot, 'src/gateway/credential-handles.js'));
const { createGovernedEgressBroker } = require(path.join(tgRoot, 'src/gateway/governed-egress.js'));
const { GovernedGitEgress } = require(path.join(tgRoot, 'src/gateway/git-egress.js'));
const { createPinnedTransport } = require(path.join(tgRoot, 'src/gateway/pinned-transport.js'));

const input = JSON.parse(process.env.STEWARD_TG_INPUT || '{}');
const botName = 'worker';
const tool = 'git.push';
const ref = 'refs/heads/' + targetBranch;
const args = { repository: targetRepo, ref, new_sha: shaB, force: true };
const diges