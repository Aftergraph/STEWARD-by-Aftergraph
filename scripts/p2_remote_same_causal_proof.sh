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
      const out = spawnSync('python3', [
        bridge, '--state', stateFile, '--action-id', input.actionId,
        '--expected-binding', digest,
      ], { encoding: 'utf8', env: process.env, maxBuffer: 256 * 1024 });
      let parsed = null;
      try { parsed = JSON.parse((out.stdout || '').trim()); } catch {}
      if (out.status !== 0 || !parsed?.ok ||
          parsed.authority_lease_id !== input.authorityLeaseId) {
        return { ok: false, reason: parsed?.code || 'aie_revalidation_failed' };
      }
      return { ok: true, version: parsed.authority_lease_id };
    }

    const audit = [];
    let transportCalls = 0;
    const broker = createGovernedEgressBroker({
      handleStore: store,
      authorityCheck: async () => revalidate(),
      approvalCheck: async () => ({ ok: true, expiresAt: now + 5 * 60 * 1000 }),
      destinationPolicy: [{
        host: 'api.github.com', schemes: ['https'], ports: [443],
        methods: ['PATCH'], pathPrefixes: [apiPath],
      }],
      audit: (event) => audit.push(event),
      commitGuard: async ({ request }) => (
        request.executionContextId === input.executionContextId &&
        request.actionId === input.actionId &&
        request.effectId === input.effectId &&
        request.effectClass === 'git.mutate' &&
        request.git?.repository === targetRepo &&
        request.git?.ref === ref
      ) ? { ok: true, permitId: 'permit/p2-remote-same-causal' } : { ok: false },
      credentialInjector: ({ secret, request }) => ({
        ...request,
        http: {
          ...request.http,
          headers: { ...request.http.headers, authorization: 'Bearer ' + secret },
        },
      }),
      transport: async (request, context) => {
        transportCalls += 1;
        return createPinnedTransport()(request, context);
      },
    });

    const git = new GovernedGitEgress({ broker, audit: (event) => audit.push(event) });
    const mutation = await git.execute({
      operation: 'push',
      repository: targetRepo,
      ref,
      newSha: shaB,
      force: true,
      requestId: 'req_p2_remote_same_causal_1',
      correlationId: input.executionContextId,
      executionContextId: input.executionContextId,
      actionId: input.actionId,
      effectId: input.effectId,
      tenantId: input.tenantId,
      principalId: input.principalId,
      missionId: input.missionId,
      authorityRef: input.authorityLeaseId,
      credentialHandle: handle.handleId,
    });
    assert.equal(mutation.result.status, 200);
    assert.equal(transportCalls, 1);
    assert.equal(JSON.stringify(audit).includes(token), false);

    const observed = JSON.parse(run('gh', [
      'api', 'repos/' + targetRepo + '/git/ref/heads/' + targetBranch,
    ]).stdout).object.sha;
    assert.equal(observed, shaB);
    const prHead = JSON.parse(run('gh', [
      'api', 'repos/' + targetRepo + '/pulls/' + targetPR,
    ]).stdout).head.sha;
    assert.equal(prHead, shaB);

    const sentinelB = sentinelReview();
    assert.equal(sentinelB.review.headSha, shaB);
    assert.equal(sentinelB.verdict.decision, 'SHIP');
    assert.match(sentinelB.receipt.receipt_id, /^[a-f0-9]{64}$/);

    const revoke = [
      'import sys',
      'from pathlib import Path',
      'aie_root, db_path, authority_id = sys.argv[1:]',
      'sys.path.insert(0, str(Path(aie_root) / "src"))',
      'from aie_runtime.engine import AdmissionEngine',
      'from aie_runtime.persistent_state import PersistentState',
      'state = PersistentState(db_path=db_path)',
      'engine = AdmissionEngine(state=state, policy=lambda _: True)',
      'engine.revoke(authority_id)',
      'state.save_all()',
      'state._conn.close()',
    ].join('\n');
    py(revoke, [aieRoot, stateFile, input.authorityLeaseId]);

    let rejected = false;
    try {
      await git.execute({
        operation: 'push',
        repository: targetRepo,
        ref,
        newSha: shaA,
        force: true,
        requestId: 'req_p2_remote_same_causal_2',
        correlationId: input.executionContextId,
        executionContextId: input.executionContextId,
        actionId: input.actionId,
        effectId: input.effectId,
        tenantId: input.tenantId,
        principalId: input.principalId,
        missionId: input.missionId,
        authorityRef: input.authorityLeaseId,
        credentialHandle: handle.handleId,
      });
    } catch (err) {
      rejected = /authority_revoked/.test(String(err?.code || err?.message || err));
    }
    assert.equal(rejected, true);
    assert.equal(transportCalls, 1);

    process.stdout.write(JSON.stringify({
      ok: true,
      execution_context_id: input.executionContextId,
      authority_lease_id: input.authorityLeaseId,
      execution_pdr_id: pdrId,
      works_correlation: allowed.correlation.receipt.status,
      aie_revalidation_evidence: evidenceCount,
      repository: targetRepo,
      git_sha: shaB,
      verification_subject: 'git:' + targetRepo + '@' + shaB,
      sentinel_a_head: sentinelA.review.headSha,
      sentinel_a_verdict: sentinelA.verdict.decision,
      sentinel_b_head: sentinelB.review.headSha,
      sentinel_b_verdict: sentinelB.verdict.decision,
      sentinel_b_receipt_id: sentinelB.receipt.receipt_id,
      credential_surrogation: true,
      remote_readback: true,
      revocation_fail_closed: true,
      transport_calls_after_revocation: transportCalls,
    }) + '\n');
  } finally {
    try { db.close(); } catch {}
    fs.rmSync(dir, { recursive: true, force: true });
  }
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exitCode = 1;
});
NODEEOF

cat > "$proof_test" <<'GOEOF'
package api_test

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

type remoteRuntimeDispatch struct {
	OK bool `json:"ok"`
	Receipt struct {
		WorksExecutionID   string `json:"worksExecutionId"`
		ExecutionContextID string `json:"executionContextId"`
		TraceID            string `json:"traceId"`
		WorkID             string `json:"workId"`
	} `json:"receipt"`
}

type remoteEffectProof struct {
	OK                      bool   `json:"ok"`
	ExecutionContextID      string `json:"execution_context_id"`
	AuthorityLeaseID        string `json:"authority_lease_id"`
	ExecutionPDRID          string `json:"execution_pdr_id"`
	WorksCorrelation        string `json:"works_correlation"`
	AIERevalidationEvidence int    `json:"aie_revalidation_evidence"`
	Repository              string `json:"repository"`
	GitSHA                  string `json:"git_sha"`
	VerificationSubject     string `json:"verification_subject"`
	SentinelAHead           string `json:"sentinel_a_head"`
	SentinelAVerdict        string `json:"sentinel_a_verdict"`
	SentinelBHead           string `json:"sentinel_b_head"`
	SentinelBVerdict        string `json:"sentinel_b_verdict"`
	SentinelBReceiptID      string `json:"sentinel_b_receipt_id"`
	CredentialSurrogation   bool   `json:"credential_surrogation"`
	RemoteReadback          bool   `json:"remote_readback"`
	RevocationFailClosed    bool   `json:"revocation_fail_closed"`
	TransportCallsAfterRevocation int `json:"transport_calls_after_revocation"`
}

type remoteBindResult struct {
	OK bool `json:"ok"`
	Receipt struct {
		Subject string `json:"subject"`
	} `json:"receipt"`
}

func TestStewardRemoteSameCausalP2(t *testing.T) {
	runtimeCLI := os.Getenv("STEWARD_RUNTIME_DISPATCH_CLI")
	bindCLI := os.Getenv("STEWARD_RUNTIME_BIND_CLI")
	nodeHarness := os.Getenv("STEWARD_REMOTE_NODE_HARNESS")
	tgRoot := os.Getenv("STEWARD_TG_ROOT")
	aieRoot := os.Getenv("STEWARD_AIE_ROOT")
	stewardRoot := os.Getenv("STEWARD_CURRENT_ROOT")
	if runtimeCLI == "" || bindCLI == "" || nodeHarness == "" || tgRoot == "" || aieRoot == "" || stewardRoot == "" {
		t.Fatal("proof paths missing")
	}

	base, workID, leaseID := setupDispatchV2Work(t)
	dispatchReq := map[string]any{
		"workId": workID,
		"organizationId": "org_11111111111111111111111111111111",
		"tenantId": "ten_22222222222222222222222222222222",
		"principalId": "prn_33333333333333333333333333333333",
		"missionId": "mis_example",
		"authorityLeaseId": "auth_44444444444444444444444444444444",
		"workerLeaseId": leaseID,
		"admissionDecisionId": "pdr_55555555555555555555555555555555",
		"attemptId": "attempt/tg-aie/remote-1",
		"effectId": "effect/tg-aie/remote-1",
		"idempotencyKey": "idem/p2/tg-aie/remote-1",
		"budgetRef": "budget/1",
		"budgetCeiling": 100,
		"checkpointId": "checkpoint/tg-aie/remote-1",
		"evidenceRoot": "evidence/tg-aie/remote-1",
		"causalId": "causal/tg-aie/remote-1",
	}
	raw, _ := json.Marshal(dispatchReq)
	cmd := exec.Command("node", runtimeCLI)
	cmd.Env = append(os.Environ(),
		"WORKS_BASE_URL="+base,
		"WORKS_BEARER_TOKEN="+dispatchV2PlatformToken,
		"WORKS_PLATFORM_BRIDGE_SECRET="+dispatchV2BridgeSecret,
	)
	cmd.Stdin = bytes.NewReader(raw)
	out, err := cmd.CombinedOutput()
	if err != nil { t.Fatalf("Runtime dispatch failed: %v output=%s", err, out) }

	var dispatch remoteRuntimeDispatch
	if err := json.Unmarshal(out, &dispatch); err != nil { t.Fatal(err) }
	if !dispatch.OK || dispatch.Receipt.ExecutionContextID == "" || dispatch.Receipt.WorkID != workID {
		t.Fatalf("bad Runtime receipt: %+v", dispatch)
	}

	proofDir := t.TempDir()
	stateFile := filepath.Join(proofDir, "aie-state.db")
	actionID := "act_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	tgInput := map[string]any{
		"actionId": actionID,
		"executionContextId": dispatch.Receipt.ExecutionContextID,
		"organizationId": dispatchReq["organizationId"],
		"tenantId": dispatchReq["tenantId"],
		"principalId": dispatchReq["principalId"],
		"missionId": dispatchReq["missionId"],
		"authorityLeaseId": dispatchReq["authorityLeaseId"],
		"effectId": dispatchReq["effectId"],
	}
	inputRaw, _ := json.Marshal(tgInput)

	tgCmd := exec.Command("node", nodeHarness)
	tgCmd.Env = append(os.Environ(),
		"WORKS_API_URL="+base,
		"WORKS_API_TOKEN="+dispatchV2PlatformToken,
		"WORKS_PLATFORM_BRIDGE_SECRET="+dispatchV2BridgeSecret,
		"AIE_RUNTIME_PATH="+aieRoot,
		"AIE_STATE_FILE="+stateFile,
		"AIE_PYTHON=python3",
		"STEWARD_TG_ROOT="+tgRoot,
		"STEWARD_AIE_ROOT="+aieRoot,
		"STEWARD_AIE_STATE="+stateFile,
		"STEWARD_TG_INPUT="+string(inputRaw),
	)
	tgOut, err := tgCmd.CombinedOutput()
	if err != nil { t.Fatalf("remote TG/AIE effect failed: %v output=%s", err, tgOut) }

	lines := strings.Split(strings.TrimSpace(string(tgOut)), "\n")
	var proof remoteEffectProof
	if err := json.Unmarshal([]byte(lines[len(lines)-1]), &proof); err != nil {
		t.Fatalf("decode remote proof: %v output=%s", err, tgOut)
	}
	if !proof.OK ||
		proof.ExecutionContextID != dispatch.Receipt.ExecutionContextID ||
		proof.AuthorityLeaseID != dispatchReq["authorityLeaseId"] ||
		proof.ExecutionPDRID == "" ||
		proof.AIERevalidationEvidence < 1 ||
		proof.SentinelBVerdict != "SHIP" ||
		proof.SentinelBHead != proof.GitSHA ||
		len(proof.SentinelBReceiptID) != 64 ||
		!proof.CredentialSurrogation ||
		!proof.RemoteReadback ||
		!proof.RevocationFailClosed ||
		proof.TransportCallsAfterRevocation != 1 {
		t.Fatalf("incomplete same-causal proof: %+v", proof)
	}
	if proof.WorksCorrelation != "recorded" && proof.WorksCorrelation != "already_recorded" {
		t.Fatalf("unexpected WORKS correlation: %s", proof.WorksCorrelation)
	}

	bindReq := map[string]any{
		"workId": workID,
		"worksExecutionId": dispatch.Receipt.WorksExecutionID,
		"attemptId": dispatchReq["attemptId"],
		"effectId": dispatchReq["effectId"],
		"causalId": dispatchReq["causalId"],
		"subject": proof.VerificationSubject,
	}
	bindRaw, _ := json.Marshal(bindReq)
	bindCmd := exec.Command("node", bindCLI)
	bindCmd.Env = append(os.Environ(),
		"WORKS_BASE_URL="+base,
		"WORKS_BEARER_TOKEN="+dispatchV2PlatformToken,
		"WORKS_PLATFORM_BRIDGE_SECRET="+dispatchV2BridgeSecret,
	)
	bindCmd.Stdin = bytes.NewReader(bindRaw)
	bindOut, err := bindCmd.CombinedOutput()
	if err != nil { t.Fatalf("Runtime subject binding failed: %v output=%s", err, bindOut) }

	var bound remoteBindResult
	if err := json.Unmarshal(bindOut, &bound); err != nil { t.Fatal(err) }
	if !bound.OK || bound.Receipt.Subject != proof.VerificationSubject {
		t.Fatalf("subject binding mismatch: %+v", bound)
	}

	readiness := `
import json, sys
from pathlib import Path
root, work_id, wexec, ctx, action_id, auth, pdr, repo, sha, subject, s_head, s_verdict, s_receipt = sys.argv[1:]
sys.path.insert(0, str(Path(root) / "src"))
from steward.p2_mission_acceptance import P2ExecutionEvidence, P2EffectVerificationEvidence, project_owner_acceptance_readiness
execution = P2ExecutionEvidence(work_id=work_id, works_execution_id=wexec, execution_context_id=ctx, action_id=action_id, authority_lease_id=auth, execution_pdr_id=pdr)
effect = P2EffectVerificationEvidence(work_id=work_id, works_execution_id=wexec, execution_context_id=ctx, action_id=action_id, authority_lease_id=auth, execution_pdr_id=pdr, repository=repo, observed_sha=sha, bound_subject=subject, sentinel_head_sha=s_head, sentinel_verdict=s_verdict, sentinel_receipt_id=s_receipt, remote_readback=True, credential_surrogation=True, action_time_revalidation=True, revocation_fail_closed=True)
out = project_owner_acceptance_readiness(execution, effect)
assert out.ready_for_owner_acceptance
print(json.dumps({"ready_for_owner_acceptance": True, "verification_subject": out.verification_subject, "sentinel_receipt_id": out.sentinel_receipt_id}))
`
	readyCmd := exec.Command(
		"python3", "-c", readiness,
		stewardRoot,
		workID,
		dispatch.Receipt.WorksExecutionID,
		dispatch.Receipt.ExecutionContextID,
		actionID,
		dispatchReq["authorityLeaseId"].(string),
		proof.ExecutionPDRID,
		proof.Repository,
		proof.GitSHA,
		proof.VerificationSubject,
		proof.SentinelBHead,
		proof.SentinelBVerdict,
		proof.SentinelBReceiptID,
	)
	readyOut, err := readyCmd.CombinedOutput()
	if err != nil { t.Fatalf("owner acceptance readiness failed: %v output=%s", err, readyOut) }
	if !strings.Contains(string(readyOut), `"ready_for_owner_acceptance": true`) {
		t.Fatalf("missing readiness proof: %s", readyOut)
	}

	t.Logf("REMOTE-SAME-CAUSAL PASS work=%s ctx=%s action=%s pdr=%s subject=%s sentinel=%s",
		workID, dispatch.Receipt.ExecutionContextID, actionID, proof.ExecutionPDRID,
		proof.VerificationSubject, proof.SentinelBReceiptID)
}
GOEOF

(
  cd "$works_root"
  STEWARD_RUNTIME_DISPATCH_CLI="$dispatch_cli" \
  STEWARD_RUNTIME_BIND_CLI="$bind_cli" \
  STEWARD_REMOTE_NODE_HARNESS="$proof_root/remote_effect_harness.js" \
  STEWARD_TG_ROOT="$tg_root" \
  STEWARD_AIE_ROOT="$aie_root" \
  STEWARD_CURRENT_ROOT="$steward_root" \
  go test ./services/api -run '^TestStewardRemoteSameCausalP2$' -count=1 -v
)

printf '{"schema":"steward.p2.remote-same-causal/0.1","runtime_head":"%s","works_head":"%s","trust_gateway_head":"%s","aie_head":"%s","sentinel_head":"%s","runtime_to_works":"PASS","tg_v21":"PASS","aie_action_time_revalidation":"PASS","works_pdr_correlation":"PASS","governed_remote_git_egress":"PASS","credential_surrogation":"PASS","remote_exact_sha_readback":"PASS","post_effect_subject_binding":"PASS","current_subject_sentinel_ship":"PASS","revocation_fail_closed":"PASS","same_causal_owner_acceptance_readiness":"PASS","isolated_worktree_binding":"absent","production_deployment":"absent"}\n' \
  "$expected_runtime" "$expected_works" "$expected_tg" "$expected_aie" "$expected_sentinel"
eadback":"PASS","post_effect_subject_binding":"PASS","current_subject_sentinel_ship":"PASS","revocation_fail_closed":"PASS","same_causal_owner_acceptance_readiness":"PASS","isolated_worktree_binding":"absent","production_deployment":"absent"}\n' \
  "$expected_runtime" "$expected_works" "$expected_tg" "$expected_aie" "$expected_sentinel"
