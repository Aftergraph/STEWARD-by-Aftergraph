#!/usr/bin/env bash
# P2 owner-backed cross-process gate:
# Runtime -> WORKS execution-context -> Trust Gateway V2.1 -> AIE live
# revalidation -> WORKS execution-PDR correlation, plus revocation fail-closed.
#
# Staging only: no production service, no Git mutation, no live Sentinel.
set -euo pipefail

runtime_root="${1:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT TG_CHECKOUT AIE_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA EXPECTED_TG_SHA EXPECTED_AIE_SHA}"
works_root="${2:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT TG_CHECKOUT AIE_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA EXPECTED_TG_SHA EXPECTED_AIE_SHA}"
tg_root="${3:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT TG_CHECKOUT AIE_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA EXPECTED_TG_SHA EXPECTED_AIE_SHA}"
aie_root="${4:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT TG_CHECKOUT AIE_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA EXPECTED_TG_SHA EXPECTED_AIE_SHA}"
expected_runtime="${5:?missing expected Runtime SHA}"
expected_works="${6:?missing expected WORKS SHA}"
expected_tg="${7:?missing expected Trust Gateway SHA}"
expected_aie="${8:?missing expected AIE SHA}"

for pair in \
  "$runtime_root:$expected_runtime:Runtime" \
  "$works_root:$expected_works:WORKS" \
  "$tg_root:$expected_tg:Trust-Gateway" \
  "$aie_root:$expected_aie:AIE"; do
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
    echo "refusing staging proof with inherited external binding in $var" >&2
    exit 1
  fi
done

command -v node >/dev/null
command -v python3 >/dev/null
command -v go >/dev/null

# Build the exact Runtime command if the prior cross-process proof has not
# already done so in this checkout.
dispatch_cli="$runtime_root/packages/runtime-host/dist/steward-dispatch-v2-cli.js"
if [[ ! -s "$dispatch_cli" ]]; then
  pnpm_run() {
    if command -v pnpm >/dev/null 2>&1; then
      pnpm "$@"
    elif command -v corepack >/dev/null 2>&1; then
      corepack pnpm "$@"
    elif command -v npx >/dev/null 2>&1; then
      npx --yes pnpm@11.20.0 "$@"
    else
      echo "pnpm unavailable: no pnpm, corepack or npx" >&2
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

proof_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/steward-p2-tg-aie.XXXXXX")"
proof_test="$works_root/services/api/steward_tg_aie_cross_process_test.go"
cleanup() {
  rm -f -- "$proof_test"
  rm -rf -- "$proof_root"
}
trap cleanup EXIT

cat > "$proof_root/tg_aie_harness.js" <<'NODEEOF'
'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const tgRoot = process.env.STEWARD_TG_ROOT;
const aieRoot = process.env.STEWARD_AIE_ROOT;
const stateFile = process.env.STEWARD_AIE_STATE;
if (!tgRoot || !aieRoot || !stateFile) throw new Error('proof roots/state missing');

const { authorizeV21Action } = require(path.join(tgRoot, 'src/gateway/platform-execution.js'));
const { actionFingerprint } = require(path.join(tgRoot, 'src/gateway/aie-client.js'));

const input = JSON.parse(process.env.STEWARD_TG_INPUT || '{}');
const tool = 'fs.read:/data/file.txt';
const botName = 'worker';
const args = null;
const digest = actionFingerprint({ bot: botName, tool, args });

function py(script, argv = []) {
  const out = spawnSync(process.env.AIE_PYTHON || 'python3', ['-c', script, ...argv], {
    encoding: 'utf8',
    env: process.env,
    maxBuffer: 256 * 1024,
  });
  if (out.status !== 0) {
    throw new Error(`python helper failed status=${out.status} stdout=${out.stdout} stderr=${out.stderr}`);
  }
  return (out.stdout || '').trim();
}

const seed = String.raw`
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

aie_root, db_path, action_id, principal_id, mission_id, authority_id, digest = sys.argv[1:]
sys.path.insert(0, str(Path(aie_root) / "src"))
from aie_runtime.engine import ActionRequest, AdmissionEngine, AuthorityLease, Mission, Principal
from aie_runtime.persistent_state import PersistentState

now = datetime.now(timezone.utc)
state = PersistentState(db_path=db_path)
state.principals[principal_id] = Principal(principal_id, "agent", "ref:steward-proof")
state.missions[mission_id] = Mission(mission_id, "RUNNING")
state.leases[authority_id] = AuthorityLease(
    id=authority_id,
    principal_id=principal_id,
    mission_id=mission_id,
    capabilities={"fs.read"},
    resource_prefixes=("/data/",),
    expires_at=now + timedelta(hours=1),
    budget_remaining=10,
    revoked=False,
)
engine = AdmissionEngine(state, policy=lambda _: True)
engine.admit(ActionRequest(
    action_id,
    principal_id,
    mission_id,
    authority_id,
    "fs.read",
    "/data/file.txt",
    0,
    extensions=({"namespace":"urn:aftergraph:tg-action:v1","sha256":digest},),
))
state.save_all()
state._conn.close()
`;

py(seed, [
  aieRoot,
  stateFile,
  input.actionId,
  input.principalId,
  input.missionId,
  input.authorityLeaseId,
  digest,
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
  assert.ok(evidenceCount >= 1, 'AIE action.revalidated evidence was not persisted');

  const revoke = String.raw`
import sys
from pathlib import Path
aie_root, db_path, authority_id = sys.argv[1:]
sys.path.insert(0, str(Path(aie_root) / "src"))
from aie_runtime.persistent_state import PersistentState
state = PersistentState(db_path=db_path)
state.leases[authority_id].revoked = True
state.save_all()
state._conn.close()
`;
  py(revoke, [aieRoot, stateFile, input.authorityLeaseId]);

  let revoked = false;
  try {
    await authorizeV21Action({
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
  } catch (err) {
    revoked = err && err.code === 'authority_revoked';
  }
  assert.equal(revoked, true, 'revoked AIE authority did not fail closed before PDR');

  process.stdout.write(JSON.stringify({
    ok: true,
    execution_context_id: input.executionContextId,
    authority_lease_id: input.authorityLeaseId,
    execution_pdr_id: pdrId,
    works_correlation: allowed.correlation.receipt.status,
    aie_revalidation_evidence: evidenceCount,
    revocation_fail_closed: true,
  }) + '\n');
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
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

type stewardRuntimeDispatch struct {
	OK bool `json:"ok"`
	Receipt struct {
		WorksExecutionID   string `json:"worksExecutionId"`
		ExecutionContextID string `json:"executionContextId"`
		TraceID            string `json:"traceId"`
		WorkID             string `json:"workId"`
	} `json:"receipt"`
}

type tgAIEProof struct {
	OK                      bool   `json:"ok"`
	ExecutionContextID      string `json:"execution_context_id"`
	AuthorityLeaseID        string `json:"authority_lease_id"`
	ExecutionPDRID          string `json:"execution_pdr_id"`
	WorksCorrelation        string `json:"works_correlation"`
	AIERevalidationEvidence int    `json:"aie_revalidation_evidence"`
	RevocationFailClosed    bool   `json:"revocation_fail_closed"`
}

func TestStewardTGAIECrossProcessV21(t *testing.T) {
	runtimeCLI := os.Getenv("STEWARD_RUNTIME_DISPATCH_CLI")
	nodeHarness := os.Getenv("STEWARD_TG_NODE_HARNESS")
	tgRoot := os.Getenv("STEWARD_TG_ROOT")
	aieRoot := os.Getenv("STEWARD_AIE_ROOT")
	if runtimeCLI == "" || nodeHarness == "" || tgRoot == "" || aieRoot == "" {
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
		"attemptId": "attempt/tg-aie/1",
		"effectId": "effect/tg-aie/1",
		"idempotencyKey": "idem/p2/tg-aie/1",
		"budgetRef": "budget/1",
		"budgetCeiling": 100,
		"checkpointId": "checkpoint/tg-aie/1",
		"evidenceRoot": "evidence/tg-aie/1",
		"causalId": "causal/tg-aie/1",
	}
	raw, err := json.Marshal(dispatchReq)
	if err != nil { t.Fatal(err) }

	cmd := exec.Command("node", runtimeCLI)
	cmd.Env = append(os.Environ(),
		"WORKS_BASE_URL="+base,
		"WORKS_BEARER_TOKEN="+dispatchV2PlatformToken,
		"WORKS_PLATFORM_BRIDGE_SECRET="+dispatchV2BridgeSecret,
	)
	cmd.Stdin = bytes.NewReader(raw)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("Runtime dispatch failed: %v output=%s", err, out)
	}
	var dispatch stewardRuntimeDispatch
	if err := json.Unmarshal(out, &dispatch); err != nil {
		t.Fatalf("decode Runtime output: %v output=%s", err, out)
	}
	if !dispatch.OK || dispatch.Receipt.ExecutionContextID == "" || dispatch.Receipt.WorkID != workID {
		t.Fatalf("bad Runtime receipt: %+v", dispatch)
	}

	stateFile := filepath.Join(t.TempDir(), "aie-state.db")
	actionID := "act_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	tgInput := map[string]any{
		"actionId": actionID,
		"executionContextId": dispatch.Receipt.ExecutionContextID,
		"organizationId": dispatchReq["organizationId"],
		"tenantId": dispatchReq["tenantId"],
		"principalId": dispatchReq["principalId"],
		"missionId": dispatchReq["missionId"],
		"authorityLeaseId": dispatchReq["authorityLeaseId"],
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
	if err != nil {
		t.Fatalf("TG/AIE proof failed: %v output=%s", err, tgOut)
	}

	lines := strings.Split(strings.TrimSpace(string(tgOut)), "\n")
	var proof tgAIEProof
	if err := json.Unmarshal([]byte(lines[len(lines)-1]), &proof); err != nil {
		t.Fatalf("decode TG/AIE output: %v output=%s", err, tgOut)
	}
	if !proof.OK ||
		proof.ExecutionContextID != dispatch.Receipt.ExecutionContextID ||
		proof.AuthorityLeaseID != dispatchReq["authorityLeaseId"] ||
		proof.ExecutionPDRID == "" ||
		proof.AIERevalidationEvidence < 1 ||
		!proof.RevocationFailClosed {
		t.Fatalf("incomplete TG/AIE proof: %+v", proof)
	}
	if proof.WorksCorrelation != "recorded" && proof.WorksCorrelation != "already_recorded" {
		t.Fatalf("unexpected WORKS correlation: %q", proof.WorksCorrelation)
	}

	t.Logf("TG/AIE proof: %s", tgOut)
}
GOEOF

(
  cd "$works_root"
  STEWARD_RUNTIME_DISPATCH_CLI="$dispatch_cli" \
  STEWARD_TG_NODE_HARNESS="$proof_root/tg_aie_harness.js" \
  STEWARD_TG_ROOT="$tg_root" \
  STEWARD_AIE_ROOT="$aie_root" \
  go test ./services/api -run '^TestStewardTGAIECrossProcessV21$' -count=1 -v
)

printf '{"schema":"steward.p2.tg-aie-cross-process/0.1","runtime_head":"%s","works_head":"%s","trust_gateway_head":"%s","aie_head":"%s","runtime_to_works":"PASS","works_context_readback":"PASS","tg_v21":"PASS","aie_live_revalidation":"PASS","works_pdr_correlation":"PASS","revocation_fail_closed":"PASS","production_binding":"absent"}\n' \
  "$expected_runtime" "$expected_works" "$expected_tg" "$expected_aie"
