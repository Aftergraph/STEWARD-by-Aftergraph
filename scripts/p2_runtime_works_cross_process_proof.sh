#!/usr/bin/env bash
# Cross-process P2 proof: the exact Runtime V2 command talks over real HTTP
# to the exact WORKS V2 owner implementation. This remains staging-only:
# no production endpoint, credential, GitHub mutation, TG/AIE or Sentinel call.
set -euo pipefail

runtime_root="${1:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA}"
works_root="${2:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA}"
expected_runtime="${3:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA}"
expected_works="${4:?usage: $0 RUNTIME_CHECKOUT WORKS_CHECKOUT EXPECTED_RUNTIME_SHA EXPECTED_WORKS_SHA}"

runtime_head="$(git -C "$runtime_root" rev-parse HEAD)"
works_head="$(git -C "$works_root" rev-parse HEAD)"
[[ "$runtime_head" == "$expected_runtime" ]] || { echo "Runtime head mismatch: $runtime_head != $expected_runtime" >&2; exit 1; }
[[ "$works_head" == "$expected_works" ]] || { echo "WORKS head mismatch: $works_head != $expected_works" >&2; exit 1; }

# Refuse accidental inheritance of real external bindings.
for var in WORKS_BASE_URL WORKS_BEARER_TOKEN WORKS_PLATFORM_BRIDGE_SECRET WORKS_API_URL WORKS_GITHUB_TOKEN STEWARD_TRUST_GATEWAY_URL STEWARD_TRUST_GATEWAY_TOKEN; do
  if [[ -n "${!var:-}" ]]; then
    echo "refusing staging proof with external binding in $var" >&2
    exit 1
  fi
done

command -v node >/dev/null
command -v go >/dev/null

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

dispatch_cli="$runtime_root/packages/runtime-host/dist/steward-dispatch-v2-cli.js"
bind_cli="$runtime_root/packages/runtime-host/dist/steward-bind-subject-v2-cli.js"
[[ -s "$dispatch_cli" ]] || { echo "Runtime dispatch command missing after build" >&2; exit 1; }
[[ -s "$bind_cli" ]] || { echo "Runtime subject-binding command missing after build" >&2; exit 1; }

proof_test="$works_root/services/api/steward_runtime_cross_process_test.go"
cleanup() {
  rm -f -- "$proof_test"
}
trap cleanup EXIT

cat > "$proof_test" <<'GOEOF'
package api_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"testing"

	"github.com/JonasAbde/works-execution/packages/executioncontext"
)

type runtimeDispatchOutput struct {
	OK      bool   `json:"ok"`
	Reason  string `json:"reason"`
	Receipt struct {
		RuntimeDispatchID  string `json:"runtimeDispatchId"`
		WorksExecutionID   string `json:"worksExecutionId"`
		WorkID             string `json:"workId"`
		ExecutionContextID string `json:"executionContextId"`
		TraceID            string `json:"traceId"`
		WorkerID           string `json:"workerId"`
	} `json:"receipt"`
}

type runtimeBindOutput struct {
	OK     bool   `json:"ok"`
	Reason string `json:"reason"`
	Receipt struct {
		WorkID           string `json:"workId"`
		WorksExecutionID string `json:"worksExecutionId"`
		AttemptID        string `json:"attemptId"`
		EffectID         string `json:"effectId"`
		CausalID         string `json:"causalId"`
		Subject          string `json:"subject"`
		BoundAt          string `json:"boundAt"`
	} `json:"receipt"`
}

func runRuntimeNode(t *testing.T, cli, base string, payload []byte) ([]byte, error) {
	t.Helper()
	cmd := exec.Command("node", cli)
	cmd.Env = append(os.Environ(),
		"WORKS_BASE_URL="+base,
		"WORKS_BEARER_TOKEN="+dispatchV2PlatformToken,
		"WORKS_PLATFORM_BRIDGE_SECRET="+dispatchV2BridgeSecret,
	)
	cmd.Stdin = bytes.NewReader(payload)
	return cmd.CombinedOutput()
}

func TestStewardRuntimeCrossProcessV2(t *testing.T) {
	dispatchCLI := os.Getenv("STEWARD_RUNTIME_DISPATCH_CLI")
	bindCLI := os.Getenv("STEWARD_RUNTIME_BIND_CLI")
	if dispatchCLI == "" || bindCLI == "" {
		t.Fatal("runtime CLI paths are required")
	}

	base, workID, leaseID := setupDispatchV2Work(t)
	request := map[string]any{
		"workId": workID,
		"organizationId": "org_11111111111111111111111111111111",
		"tenantId": "ten_22222222222222222222222222222222",
		"principalId": "prn_33333333333333333333333333333333",
		"missionId": "mis_example",
		"authorityLeaseId": "auth_44444444444444444444444444444444",
		"workerLeaseId": leaseID,
		"admissionDecisionId": "pdr_55555555555555555555555555555555",
		"attemptId": "attempt/1",
		"effectId": "effect/1",
		"idempotencyKey": "idem/v2/runtime-works-cross-process/1",
		"budgetRef": "budget/1",
		"budgetCeiling": 100,
		"checkpointId": "checkpoint/1",
		"evidenceRoot": "evidence/1",
		"causalId": "causal/1",
	}
	raw, err := json.Marshal(request)
	if err != nil {
		t.Fatal(err)
	}

	out, err := runRuntimeNode(t, dispatchCLI, base, raw)
	if err != nil {
		t.Fatalf("runtime dispatch failed: %v output=%s", err, out)
	}
	var dispatch runtimeDispatchOutput
	if err := json.Unmarshal(out, &dispatch); err != nil {
		t.Fatalf("decode runtime dispatch: %v output=%s", err, out)
	}
	if !dispatch.OK {
		t.Fatalf("runtime dispatch not ok: reason=%s output=%s", dispatch.Reason, out)
	}
	if dispatch.Receipt.WorkID != workID || dispatch.Receipt.WorksExecutionID == "" ||
		dispatch.Receipt.ExecutionContextID == "" || dispatch.Receipt.TraceID == "" ||
		dispatch.Receipt.WorkerID == "" || dispatch.Receipt.RuntimeDispatchID == "" {
		t.Fatalf("incomplete runtime receipt: %+v", dispatch.Receipt)
	}

	// Owner readback: the ctx returned through Runtime must exist as canonical
	// WORKS execution-context/1.0 state, not only in Runtime output.
	resp, err := http.Get(base + "/v1/execution-contexts/" + dispatch.Receipt.ExecutionContextID)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("execution-context readback status=%d body=%s", resp.StatusCode, body)
	}
	var ctx executioncontext.Context
	if err := json.Unmarshal(body, &ctx); err != nil {
		t.Fatal(err)
	}
	if ctx.ID != dispatch.Receipt.ExecutionContextID || ctx.TraceID != dispatch.Receipt.TraceID ||
		ctx.WorkID != workID || ctx.WorkerLeaseID != leaseID ||
		ctx.AuthorityLeaseID != "auth_44444444444444444444444444444444" {
		t.Fatalf("canonical WORKS context mismatch: %+v", ctx)
	}

	subject := "git:Aftergraph/STEWARD-by-Aftergraph@" + strings.Repeat("b", 40)
	bindRequest := map[string]any{
		"workId": workID,
		"worksExecutionId": dispatch.Receipt.WorksExecutionID,
		"attemptId": "attempt/1",
		"effectId": "effect/1",
		"causalId": "causal/1",
		"subject": subject,
	}
	bindRaw, err := json.Marshal(bindRequest)
	if err != nil {
		t.Fatal(err)
	}
	bindOut, err := runRuntimeNode(t, bindCLI, base, bindRaw)
	if err != nil {
		t.Fatalf("runtime subject bind failed: %v output=%s", err, bindOut)
	}
	var bound runtimeBindOutput
	if err := json.Unmarshal(bindOut, &bound); err != nil {
		t.Fatalf("decode subject binding: %v output=%s", err, bindOut)
	}
	if !bound.OK || bound.Receipt.WorkID != workID ||
		bound.Receipt.WorksExecutionID != dispatch.Receipt.WorksExecutionID ||
		bound.Receipt.Subject != subject || bound.Receipt.BoundAt == "" {
		t.Fatalf("bad subject-binding receipt: %+v output=%s", bound, bindOut)
	}

	// Same-subject replay must be idempotent.
	replayOut, err := runRuntimeNode(t, bindCLI, base, bindRaw)
	if err != nil {
		t.Fatalf("subject replay failed: %v output=%s", err, replayOut)
	}
	var replay runtimeBindOutput
	if err := json.Unmarshal(replayOut, &replay); err != nil {
		t.Fatal(err)
	}
	if !replay.OK || replay.Receipt.BoundAt != bound.Receipt.BoundAt {
		t.Fatalf("subject replay not idempotent: first=%+v replay=%+v", bound.Receipt, replay.Receipt)
	}

	// A different immutable subject must fail closed through the real Runtime
	// command and the WORKS durable binding.
	conflict := map[string]any{}
	for k, v := range bindRequest {
		conflict[k] = v
	}
	conflict["subject"] = "git:Aftergraph/STEWARD-by-Aftergraph@" + strings.Repeat("c", 40)
	conflictRaw, _ := json.Marshal(conflict)
	conflictOut, conflictErr := runRuntimeNode(t, bindCLI, base, conflictRaw)
	if conflictErr == nil {
		t.Fatalf("different-subject rebinding unexpectedly succeeded: %s", conflictOut)
	}
	var rejected runtimeBindOutput
	if err := json.Unmarshal(conflictOut, &rejected); err != nil {
		t.Fatalf("decode rejection: %v output=%s", err, conflictOut)
	}
	if rejected.OK {
		t.Fatalf("different-subject rebinding returned ok: %s", conflictOut)
	}

	fmt.Println("P2_RUNTIME_WORKS_CROSS_PROCESS=PASS")
}
GOEOF

(
  cd "$works_root"
  STEWARD_RUNTIME_DISPATCH_CLI="$dispatch_cli"   STEWARD_RUNTIME_BIND_CLI="$bind_cli"   go test ./services/api -run '^TestStewardRuntimeCrossProcessV2$' -count=1 -v
)

printf '{"schema":"steward.p2.runtime-works-cross-process/0.1","runtime_head":"%s","works_head":"%s","runtime_command_built":"PASS","runtime_to_works_http":"PASS","works_context_readback":"PASS","subject_binding":"PASS","conflicting_subject_rejected":"PASS","production_binding":"absent"}\n' "$runtime_head" "$works_head"
