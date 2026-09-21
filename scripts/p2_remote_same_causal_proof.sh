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
const digest = actionFingerprint({ bot: botName, tool, args });

function py(script, argv = []) {
  const out = spawnSync(process.env.AIE_PYTHON || 'python3', ['-c', script, ...argv], {
    encoding: 'utf8', env: process.env, maxBuffer: 256 * 1024,
  });
  if (out.status !== 0) {
    throw new Error('python helper failed status=' + out.status + ' stdout=' + out.stdout + ' stderr=' + out.stderr);
  }
  return (out.stdout || '').trim();
}

function run(command, argv = [], options = {}) {
  const out = spawnSync(command, argv, {
    encoding: 'utf8', env: process.env, maxBuffer: 2 * 1024 * 1024, ...options,
  });
  if (out.status !== 0) {
    throw new Error(command + ' failed status=' + out.status + ' stdout=' + out.stdout + ' stderr=' + out.stderr);
  }
  return out;
}

function sentinelReview() {
  const out = run('node', [
    path.join(sentinelRoot, 'bin', 'sentinel.js'),
    'review', '--pr', targetPR, '--repo', targetRepo,
    '--format', 'json', '--no-ledger',
  ]);
  return JSON.parse(out.stdout);
}

const seed = [
'import sys',
'from datetime import datetime, timedelta, timezone',
'from pathlib import Path',
'aie_root, db_path, action_id, principal_id, mission_id, authority_id, digest, repo, ref = sys.argv[1:]',
'sys.path.insert(0, str(Path(aie_root) / "src"))',
'from aie_runtime.engine import ActionRequest, AdmissionEngine, AuthorityLease, Mission, Principal',
'from aie_runtime.persistent_state import PersistentState',
'now = datetime.now(timezone.utc)',
'state = PersistentState(db_path=db_path)',
'state.principals[principal_id] = Principal(principal_id, "agent", "ref:steward-remote-p2")',
'state.missions[mission_id] = Mission(mission_id, "RUNNING")',
'state.leases[authority_id] = AuthorityLease(id=authority_id, principal_id=principal_id, mission_id=mission_id, capabilities={"git.push"}, resource_prefixes=("repo:" + repo,), expires_at=now + timedelta(minutes=10), budget_remaining=10, revoked=False)',
'engine = AdmissionEngine(state, policy=lambda _: True)',
'engine.admit(ActionRequest(action_id, principal_id, mission_id, authority_id, "git.push", "repo:" + repo + "#" + ref, 1, extensions=({"namespace":"urn:aftergraph:tg-action:v1","sha256":digest},)))',
'state.save_all()',
'state._conn.close()',
].join('\n');

py(seed, [
  aieRoot, stateFile, input.actionId, input.principalId, input.missionId,
  input.authorityLeaseId, digest, targetRepo, ref,
]);

const pdrId = 'pdr_88888888888888888888888888888888';
const deps = {
  resolvePlatformIdentity: () => ({
    status: 200,
    body: {
      organization_id: input.organizationId,
      tenant_id: input.tenantId,
      principal_id: input.principalId,
    },
  }),
  createExecutionDecision: (record) => ({ id: pdrId, ...record }),
};

(async () => {
  const sentinelA = sentinelReview();
  assert.equal(sentinelA.review.headSha, shaA);

  const allowed = await authorizeV21Action({
    req: {},
    gw: {},
    body: {
      action_id: input.actionId,
      execution_context_id: input.executionContextId,
      mission_id: input.missionId,
    },
    bot: { name: botName },
    tool,
    args,
    deps,
  });

  assert.equal(allowed.legacy, false);
  assert.equal(allowed.context.execution_context_id, input.executionContextId);
  assert.equal(allowed.context.authority_lease_id, input.authorityLeaseId);
  assert.equal(allowed.revalidation.action_id, input.actionId);
  assert.equal(allowed.revalidation.authority_lease_id, input.authorityLeaseId);
  assert.equal(allowed.pdr.id, pdrId);
  assert.equal(allowed.correlation.ok, true);
  assert.ok(['recorded', 'already_recorded'].includes(allowed.correlation.receipt.status));

  const evidenceCount = Number(py(
    "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(sum('action.revalidated' in r[0] for r in c.execute('SELECT data FROM evidence'))); c.close()",
    [stateFile],
  ));
  assert.ok(evidenceCount >= 1);

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'steward-p2-remote-'));
  const db = open(path.join(dir, 'gateway.db'));
  try {
    const vault = new SecretsVault({ db, enabled: true, master: 'p2-remote-proof-ephemeral-master' });
    vault.setSecret(input.tenantId, 'github-proof-token', token);
    const now = Date.now();
    const store = new CredentialHandleStore({ db, vault, now: () => Date.now() });
    const apiPath = '/repos/' + targetRepo + '/git/refs/heads/' + targetBranch;
    const handle = store.issue({
      tenant: input.tenantId,
      secretKey: 'github-proof-token',
      principalId: input.principalId,
      missionId: input.missionId,
      authorityRef: input.authorityLeaseId,
      purpose: 'git_push',
      credentialClass: 'github_actions_ephemeral_token',
      allowedDestinations: ['api.github.com'],
      allowedMethods: ['PATCH'],
      allowedPathPrefixes: [apiPath],
      scopeRefs: ['repo:' + targetRepo, 'ref:' + ref],
      expiresAt: now + 5 * 60 * 1000,
    });

    const bridge = path.join(aieRoot, 'scripts', 'aie_revalidate_bridge.py');
    function revalidate() {
      con