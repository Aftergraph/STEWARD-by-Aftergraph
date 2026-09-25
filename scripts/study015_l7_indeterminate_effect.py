#!/usr/bin/env python3
"""STUDY-015 L7 indeterminate external-effect reconciliation.

Phase A intentionally crashes Trust Gateway after the governed Git transport
returns success but before egress_dispatched / git_egress_completed can become
durable. Phase B MUST run on a different physical host and reconcile exact
remote state before any retry is possible.

Research conformance only. G15-9 remains unauthorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import study015_l6_cross_host as l6

base = l6.base

ORG = "org_" + "1" * 32
TENANT = "ten_" + "2" * 32
PRINCIPAL = "prn_" + "3" * 32
AUTH = "auth_" + "4" * 32
ADMISSION = "pdr_" + "a" * 32
ACTION = "act_" + "e" * 32
MISSION = "mis_study015_l7_indeterminate_effect"
ATTEMPT = "attempt/study015/live-5"
EFFECT = "effect/study015/live-5"
CAUSAL = "causal/study015/live-5"
REQUEST_ID = "req/study015/live-5"
TARGET_REPO = "Aftergraph/runtime"
TARGET_BRANCH = "study015/l7-indeterminate-effect-proof-target"
TARGET_REF = "refs/heads/" + TARGET_BRANCH
TARGET_PR = 213

PRIOR_L6_CONTEXT = "ctx_45a494a4d6bdf6897ac0f56d8ee55f14"
PRIOR_L6_RECEIPT = "0a1cc344c21becf0276cf41598943b6abd72ffd58bfb95f9e6c7369e1af3a8ff"


class L7Error(RuntimeError):
    pass


def configure_modules() -> None:
    for module in (l6, base):
        module.ORG = ORG
        module.TENANT = TENANT
        module.PRINCIPAL = PRINCIPAL
        module.AUTH = AUTH
        module.ADMISSION = ADMISSION
        module.ACTION = ACTION
        module.MISSION = MISSION
        module.ATTEMPT = ATTEMPT
        module.EFFECT = EFFECT
        module.CAUSAL = CAUSAL
        module.TARGET_REPO = TARGET_REPO
        module.TARGET_BRANCH = TARGET_BRANCH
        module.TARGET_REF = TARGET_REF
        module.TARGET_PR = TARGET_PR


def action_args(ctx_id: str, works_execution_id: str, sha_b: str) -> dict:
    return {
        "action_id": ACTION,
        "execution_context_id": ctx_id,
        "works_execution_id": works_execution_id,
        "mission_id": MISSION,
        "authority_ref": AUTH,
        "tenant_id": TENANT,
        "principal_id": PRINCIPAL,
        "effect_id": EFFECT,
        "causal_id": CAUSAL,
        "request_id": REQUEST_ID,
        "repository": TARGET_REPO,
        "ref": TARGET_REF,
        "new_sha": sha_b,
        "force": True,
    }


def classify_remote_effect(sha_a: str, sha_b: str, observed: str) -> dict:
    observed = str(observed or "").lower()
    if observed == sha_b:
        return {
            "status": "COMMITTED_RECOVERED",
            "retry_allowed": False,
            "reason": "exact_expected_post_effect_state",
        }
    if observed == sha_a:
        return {
            "status": "ABSENT_RETRY_ELIGIBLE",
            "retry_allowed": True,
            "reason": "exact_pre_effect_state",
        }
    return {
        "status": "CONFLICT_FAIL_CLOSED",
        "retry_allowed": False,
        "reason": "remote_state_diverged_from_known_pre_and_post_states",
    }


def start_tg(
    tg_root: Path,
    *,
    root: Path,
    state_dir: Path,
    aie_root: Path,
    aie_state: Path,
    works_url: str,
    works_token: str,
    bridge_secret: str,
    worker_token: str,
    operator_token: str,
    vault_master: str,
    gh_token: str,
    ready: Path,
    fault_after_transport: bool = False,
    reconciliation_file: Path | None = None,
    reconciliation_identity: dict | None = None,
):
    env = os.environ.copy()
    env.update({
        "TG_DB_FILE": str(root / "tg-local.db"),
        "TG_DATA_DIR": str(state_dir / "tg-data"),
        "TG_SECRETS_MASTER_KEY": vault_master,
        "AIE_RUNTIME_PATH": str(aie_root),
        "AIE_STATE_FILE": str(aie_state),
        "AIE_PYTHON": sys.executable,
        "WORKS_API_URL": works_url,
        "WORKS_API_TOKEN": works_token,
        "WORKS_PLATFORM_BRIDGE_SECRET": bridge_secret,
        "STUDY015_TG_WORKER_TOKEN": worker_token,
        "STUDY015_TG_OPERATOR_TOKEN": operator_token,
        "STUDY015_GITHUB_TOKEN": gh_token,
        "STUDY015_ORGANIZATION_ID": ORG,
        "STUDY015_TENANT_ID": TENANT,
        "STUDY015_PRINCIPAL_ID": PRINCIPAL,
        "STUDY015_MISSION_ID": MISSION,
        "STUDY015_AUTHORITY_LEASE_ID": AUTH,
        "STUDY015_GIT_REPOSITORY": TARGET_REPO,
        "STUDY015_GIT_REF": TARGET_REF,
        "STUDY015_TG_READY_OUT": str(ready),
        "STUDY015_TG_PORT": "0",
    })
    if fault_after_transport:
        env["STUDY015_FAIL_AFTER_TRANSPORT_SUCCESS"] = "1"
    if reconciliation_file is not None:
        if not reconciliation_identity:
            raise L7Error("reconciliation identity required")
        env.update({
            "STUDY015_RECONCILIATION_FILE": str(reconciliation_file),
            "STUDY015_RECONCILIATION_EXECUTION_CONTEXT_ID": reconciliation_identity["execution_context_id"],
            "STUDY015_RECONCILIATION_ACTION_ID": reconciliation_identity["action_id"],
            "STUDY015_RECONCILIATION_EFFECT_ID": reconciliation_identity["effect_id"],
            "STUDY015_RECONCILIATION_CAUSAL_ID": reconciliation_identity["causal_id"],
            "STUDY015_RECONCILIATION_EXPECTED_SHA": reconciliation_identity["expected_sha"],
        })

    proc = subprocess.Popen(
        ["node", "bin/study015-live-gateway.js"],
        cwd=tg_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, env


def audit_entries(path: Path) -> list[dict]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise L7Error("TG audit row is not an object")
        rows.append(row)
    if not rows:
        raise L7Error("TG audit is empty")
    return rows


def matching_audit(entries: list[dict], kind: str, ctx_id: str) -> list[dict]:
    out = []
    for row in entries:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("type") == kind
            and payload.get("actionId") == ACTION
            and payload.get("effectId") == EFFECT
            and payload.get("executionContextId") == ctx_id
        ):
            out.append(row)
    return out


def dispatch_request(work_id: str, lease_id: str) -> dict:
    return {
        "workId": work_id,
        "organizationId": ORG,
        "tenantId": TENANT,
        "principalId": PRINCIPAL,
        "missionId": MISSION,
        "authorityLeaseId": AUTH,
        "workerLeaseId": lease_id,
        "admissionDecisionId": ADMISSION,
        "attemptId": ATTEMPT,
        "effectId": EFFECT,
        "idempotencyKey": "idem/study015/live-5",
        "budgetRef": "budget/study015/live-5",
        "budgetCeiling": 100,
        "checkpointId": "checkpoint/study015/live-5",
        "evidenceRoot": "evidence/study015/live-5",
        "causalId": CAUSAL,
    }


def verify_same_dispatch(replayed: dict, original: dict) -> None:
    if replayed.get("ok") is not True:
        raise L7Error("Runtime dispatch replay failed")
    rr = replayed["receipt"]
    for field in (
        "runtimeDispatchId",
        "worksExecutionId",
        "workId",
        "executionContextId",
        "traceId",
        "workerId",
    ):
        if rr.get(field) != original.get(field):
            raise L7Error(f"cross-host dispatch rebound {field}")


def prepare(handoff: Path) -> dict:
    configure_modules()
    roots, heads = l6.exact_roots()
    host_a = l6.host_identity()
    sha_a = os.environ["STUDY015_SHA_A"]
    sha_b = os.environ["STUDY015_SHA_B"]
    if len(sha_a) != 40 or len(sha_b) != 40 or sha_a == sha_b:
        raise L7Error("invalid proof SHAs")

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise L7Error("GitHub token missing")
    gh_env = os.environ.copy()
    gh_env["GH_TOKEN"] = gh_token

    state_dir = handoff / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "tg-data").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="study015-l7-a-") as td:
        local = Path(td)
        works_token = secrets.token_hex(32)
        bridge_secret = secrets.token_hex(32)
        verifier_token = secrets.token_hex(32)
        worker_token = secrets.token_hex(24)
        operator_token = secrets.token_hex(24)
        vault_master = secrets.token_hex(32)
        secrets_to_scan = [
            works_token, bridge_secret, verifier_token, worker_token,
            operator_token, vault_master, gh_token,
        ]

        works_db = state_dir / "works.db"
        works_ready = state_dir / "works-ready.json"
        aie_state = state_dir / "aie-state.db"
        tg_ready = local / "tg-ready.json"

        dispatch_cli, _ = l6.runtime_paths(roots["runtime"])
        works_proc, _ = l6.start_works(
            roots["works"],
            db=works_db,
            ready=works_ready,
            works_token=works_token,
            bridge_secret=bridge_secret,
            verifier_token=verifier_token,
        )
        tg_proc = None
        try:
            fixture = base.wait_json(works_ready, works_proc)
            works_url = fixture["base_url"]
            work_id = fixture["work_id"]
            lease_id = fixture["worker_lease_id"]
            runtime_env = l6.api_env(works_url, works_token, bridge_secret)
            request = dispatch_request(work_id, lease_id)

            dispatched = json.loads(base.run(
                ["node", str(dispatch_cli)],
                env=runtime_env,
                input_text=json.dumps(request),
            ).stdout)
            if dispatched.get("ok") is not True:
                raise L7Error("Runtime dispatch failed on Host A")
            runtime_receipt = dispatched["receipt"]
            ctx_id = runtime_receipt["executionContextId"]
            works_execution_id = runtime_receipt["worksExecutionId"]

            args = action_args(ctx_id, works_execution_id, sha_b)
            digest = l6.tg_fingerprint(roots["trust_gateway"], args)
            base.seed_aie(roots["aie"], aie_state, args, digest, os.environ.copy())

            base.patch_ref(TARGET_REPO, TARGET_BRANCH, sha_a, gh_env)
            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_a:
                raise L7Error("Host A failed to reset L7 proof target")

            tg_proc, _ = start_tg(
                roots["trust_gateway"],
                root=local,
                state_dir=state_dir,
                aie_root=roots["aie"],
                aie_state=aie_state,
                works_url=works_url,
                works_token=works_token,
                bridge_secret=bridge_secret,
                worker_token=worker_token,
                operator_token=operator_token,
                vault_master=vault_master,
                gh_token=gh_token,
                ready=tg_ready,
                fault_after_transport=True,
            )
            tg_fixture = base.wait_json(tg_ready, tg_proc)
            if tg_fixture.get("fault_mode") != "post_transport_success_sigkill":
                raise L7Error("TG L7 fault mode not armed")
            tg_url = tg_fixture["base_url"]
            audit_path = Path(tg_fixture["audit_file"]).resolve()

            action_body = {
                "action_id": ACTION,
                "execution_context_id": ctx_id,
                "mission_id": MISSION,
                "tool": "git.push",
                "args": args,
            }
            status, proposed = base.http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token, body=action_body,
            )
            if status != 202 or proposed.get("decision") != "needs_approval":
                raise L7Error("Host A action did not reach approval boundary")

            approval_observation = "connection_terminated"
            try:
                status, approved = base.http_json(
                    "POST",
                    tg_url + f"/v1/approvals/{quote(proposed['approvalId'])}/approve",
                    token=operator_token,
                    body={},
                )
                approval_observation = f"http_{status}"
                if status == 200:
                    raise L7Error("fault injector returned a successful approval response")
            except L7Error:
                raise
            except Exception as exc:
                approval_observation = type(exc).__name__

            try:
                rc = tg_proc.wait(timeout=20)
            except subprocess.TimeoutExpired as exc:
                raise L7Error("TG did not die at post-transport fault boundary") from exc
            tg_proc = None
            if rc == 0:
                raise L7Error("TG exited cleanly instead of faulting")

            observed = None
            pr_head = None
            for _ in range(24):
                observed = base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env)
                pr_head = base.github_pr_head(TARGET_REPO, TARGET_PR, gh_env)
                if observed == sha_b and pr_head == sha_b:
                    break
                time.sleep(0.25)
            if observed != sha_b or pr_head != sha_b:
                raise L7Error("external effect did not commit before injected crash")

            entries = audit_entries(audit_path)
            admitted = matching_audit(entries, "egress_admitted", ctx_id)
            dispatched_audit = matching_audit(entries, "egress_dispatched", ctx_id)
            completed = matching_audit(entries, "git_egress_completed", ctx_id)
            if len(admitted) != 1:
                raise L7Error(f"expected one durable egress_admitted, got {len(admitted)}")
            if dispatched_audit:
                raise L7Error("egress_dispatched became durable despite uncertainty fault")
            if completed:
                raise L7Error("git_egress_completed became durable despite uncertainty fault")

            # Stop the remaining execution carrier before handoff. The Host B
            # phase is the only process allowed to resume from this state.
            l6.terminate(works_proc, kill=True)
            works_proc = None

            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_b:
                raise L7Error("remote effect changed after Host A crash")

            l6.scan_no_secrets(state_dir, secrets_to_scan)
            files = l6.manifest_file_map(state_dir)
            manifest = {
                "schema": "study015.l7-handoff/1.0",
                "study_id": "STUDY-015",
                "host_a": host_a,
                "heads": heads,
                "proof_target": {
                    "repository": TARGET_REPO,
                    "pull_request": TARGET_PR,
                    "branch": TARGET_BRANCH,
                    "sha_a": sha_a,
                    "sha_b": sha_b,
                    "remote_readback": sha_b,
                },
                "identity": {
                    "mission_id": MISSION,
                    "work_id": work_id,
                    "worker_lease_id": lease_id,
                    "admission_decision_id": ADMISSION,
                    "runtime_dispatch_id": runtime_receipt["runtimeDispatchId"],
                    "works_execution_id": works_execution_id,
                    "execution_context_id": ctx_id,
                    "trace_id": runtime_receipt["traceId"],
                    "attempt_id": ATTEMPT,
                    "action_id": ACTION,
                    "effect_id": EFFECT,
                    "causal_id": CAUSAL,
                },
                "dispatch_request": request,
                "action_body": action_body,
                "runtime_receipt": runtime_receipt,
                "uncertainty_window": {
                    "approval_observation": approval_observation,
                    "gateway_exit_code": rc,
                    "external_post_state_observed": True,
                    "egress_admitted_durable": True,
                    "egress_dispatched_absent": True,
                    "git_egress_completed_absent": True,
                    "effect_state_at_handoff": "INDETERMINATE",
                },
                "single_writer_fence": {
                    "host_a_gateway_stopped": True,
                    "host_a_works_stopped": True,
                    "handoff_built_after_host_a_stop": True,
                },
                "handoff_files": files,
                "secrets_transferred": False,
                "excluded_state": [
                    "tg.db",
                    "tg vault master",
                    "GitHub credential",
                    "API tokens",
                    "approval tokens",
                    "vault master",
                ],
                "prior_l6_receipt_sha256": PRIOR_L6_RECEIPT,
            }
            canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
            manifest["phase_a_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
            (state_dir / "phase-a.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            l6.scan_no_secrets(state_dir, secrets_to_scan)
            print(json.dumps({
                "schema": "study015.l7-phase-a/1.0",
                "status": "INDETERMINATE_HANDOFF_READY",
                "host_a": host_a,
                "phase_a_sha256": manifest["phase_a_sha256"],
                "remote_readback": sha_b,
                "egress_dispatched_absent": True,
                "git_egress_completed_absent": True,
                "secrets_transferred": False,
            }, sort_keys=True))
            return manifest
        finally:
            l6.terminate(tg_proc, kill=True)
            l6.terminate(works_proc, kill=True)
            try:
                base.patch_ref(TARGET_REPO, TARGET_BRANCH, sha_b, gh_env)
            except Exception:
                pass


def resume(handoff: Path) -> dict:
    configure_modules()
    roots, heads = l6.exact_roots()
    host_b = l6.host_identity()
    state_dir = handoff / "state"
    phase_path = state_dir / "phase-a.json"
    if not phase_path.is_file():
        raise L7Error("L7 phase-A manifest missing")

    manifest = json.loads(phase_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "study015.l7-handoff/1.0":
        raise L7Error("bad L7 handoff schema")
    prior_hash = manifest.pop("phase_a_sha256", None)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != prior_hash:
        raise L7Error("L7 phase-A manifest hash mismatch")
    manifest["phase_a_sha256"] = prior_hash
    l6.verify_handoff_files(state_dir, manifest)

    host_a = manifest["host_a"]
    if host_a.get("machine_id_sha256") == host_b.get("machine_id_sha256"):
        raise L7Error("Host B is the same physical machine as Host A")
    if host_a.get("hostname") == host_b.get("hostname"):
        raise L7Error("Host B hostname equals Host A")
    if manifest.get("heads") != heads:
        raise L7Error("owner-head drift between L7 hosts")
    if manifest.get("secrets_transferred") is not False:
        raise L7Error("L7 handoff transferred secrets")

    proof = manifest["proof_target"]
    sha_a = proof["sha_a"]
    sha_b = proof["sha_b"]
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise L7Error("GitHub token missing on Host B")
    gh_env = os.environ.copy()
    gh_env["GH_TOKEN"] = gh_token

    # Critical ordering: exact remote reconciliation occurs BEFORE WORKS/TG are
    # restarted and therefore before any retry/admission path can execute.
    observed = base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env)
    reconciliation = classify_remote_effect(sha_a, sha_b, observed)
    if reconciliation["status"] != "COMMITTED_RECOVERED":
        raise L7Error(f"L7 remote state did not reconcile committed effect: {reconciliation['status']}")
    if reconciliation["retry_allowed"] is not False:
        raise L7Error("reconciled committed effect unexpectedly permits retry")

    # Falsification vectors for the classifier itself.
    absent_vector = classify_remote_effect(sha_a, sha_b, sha_a)
    conflict_sha = "f" * 40
    if conflict_sha in (sha_a, sha_b):
        conflict_sha = "0" * 40
    conflict_vector = classify_remote_effect(sha_a, sha_b, conflict_sha)
    if absent_vector != {
        "status": "ABSENT_RETRY_ELIGIBLE",
        "retry_allowed": True,
        "reason": "exact_pre_effect_state",
    }:
        raise L7Error("known-absent classifier vector failed")
    if conflict_vector["status"] != "CONFLICT_FAIL_CLOSED" or conflict_vector["retry_allowed"] is not False:
        raise L7Error("divergent classifier vector did not fail closed")

    with tempfile.TemporaryDirectory(prefix="study015-l7-b-") as td:
        local = Path(td)
        works_token = secrets.token_hex(32)
        bridge_secret = secrets.token_hex(32)
        verifier_token = secrets.token_hex(32)
        worker_token = secrets.token_hex(24)
        operator_token = secrets.token_hex(24)
        vault_master = secrets.token_hex(32)

        works_db = state_dir / "works.db"
        aie_state = state_dir / "aie-state.db"
        prior_fixture = state_dir / "works-ready.json"
        works_ready_b = local / "works-ready-b.json"
        tg_ready_b = local / "tg-ready-b.json"
        reconciliation_file = local / "reconciliation.json"

        identity = manifest["identity"]
        reconciliation_record = {
            "schema": "study015.effect-reconciliation/1.0",
            "status": "COMMITTED_RECOVERED",
            "request_id": REQUEST_ID,
            "correlation_id": identity["causal_id"],
            "execution_context_id": identity["execution_context_id"],
            "action_id": identity["action_id"],
            "effect_id": identity["effect_id"],
            "repository": TARGET_REPO,
            "ref": TARGET_REF,
            "expected_sha": sha_b,
            "observed_sha": observed,
            "observed_via": "github_exact_ref_readback",
        }
        reconciliation_file.write_text(
            json.dumps(reconciliation_record, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        dispatch_cli, bind_cli = l6.runtime_paths(roots["runtime"])
        works_proc, _ = l6.start_works(
            roots["works"],
            db=works_db,
            ready=works_ready_b,
            works_token=works_token,
            bridge_secret=bridge_secret,
            verifier_token=verifier_token,
            resume_fixture=prior_fixture,
            relocated=True,
        )
        tg_proc = None
        try:
            resumed_works = base.wait_json(works_ready_b, works_proc)
            if resumed_works.get("recovered") is not True or resumed_works.get("relocated") is not True:
                raise L7Error("WORKS did not enter relocated recovery")
            if resumed_works.get("work_id") != identity["work_id"]:
                raise L7Error("WORKS rebound work identity")
            if resumed_works.get("worker_lease_id") != identity["worker_lease_id"]:
                raise L7Error("WORKS rebound lease identity")

            works_url = resumed_works["base_url"]
            runtime_env = l6.api_env(works_url, works_token, bridge_secret)
            replayed = json.loads(base.run(
                ["node", str(dispatch_cli)],
                env=runtime_env,
                input_text=json.dumps(manifest["dispatch_request"]),
            ).stdout)
            verify_same_dispatch(replayed, manifest["runtime_receipt"])

            ctx_id = identity["execution_context_id"]
            ctx_status, recovered_context = base.http_json(
                "GET",
                works_url + "/v1/execution-contexts/" + quote(ctx_id, safe=""),
            )
            if ctx_status != 200:
                raise L7Error("execution context unavailable after relocation")
            expected_context = {
                "execution_context_id": ctx_id,
                "organization_id": ORG,
                "tenant_id": TENANT,
                "principal_id": PRINCIPAL,
                "mission_id": MISSION,
                "authority_lease_id": AUTH,
                "work_id": identity["work_id"],
                "worker_lease_id": identity["worker_lease_id"],
                "admission_decision_id": ADMISSION,
                "trace_id": identity["trace_id"],
            }
            for key, value in expected_context.items():
                if recovered_context.get(key) != value:
                    raise L7Error(f"recovered execution context rebound {key}")

            tg_proc, _ = start_tg(
                roots["trust_gateway"],
                root=local,
                state_dir=state_dir,
                aie_root=roots["aie"],
                aie_state=aie_state,
                works_url=works_url,
                works_token=works_token,
                bridge_secret=bridge_secret,
                worker_token=worker_token,
                operator_token=operator_token,
                vault_master=vault_master,
                gh_token=gh_token,
                ready=tg_ready_b,
                reconciliation_file=reconciliation_file,
                reconciliation_identity={
                    "execution_context_id": ctx_id,
                    "action_id": identity["action_id"],
                    "effect_id": identity["effect_id"],
                    "causal_id": identity["causal_id"],
                    "expected_sha": sha_b,
                },
            )
            resumed_tg = base.wait_json(tg_ready_b, tg_proc)
            if resumed_tg.get("fault_mode") != "none":
                raise L7Error("Host B unexpectedly armed post-transport crash")
            if resumed_tg.get("reconciliation_recorded") is not True:
                raise L7Error("TG did not durably record L7 reconciliation")

            tg_url = resumed_tg["base_url"]
            audit_status, audit = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=1000",
                token=operator_token,
            )
            if audit_status != 200:
                raise L7Error("TG audit unavailable on Host B")
            entries = audit.get("entries", [])
            admitted = matching_audit(entries, "egress_admitted", ctx_id)
            dispatched_audit = matching_audit(entries, "egress_dispatched", ctx_id)
            completed = matching_audit(entries, "git_egress_completed", ctx_id)
            reconciled = matching_audit(entries, "git_egress_reconciled", ctx_id)
            if len(admitted) != 1:
                raise L7Error("transferred egress admission missing")
            if dispatched_audit:
                raise L7Error("unexpected durable egress_dispatched after reconciliation")
            if completed:
                raise L7Error("unexpected durable git_egress_completed after reconciliation")
            if len(reconciled) != 1:
                raise L7Error("exactly one TG reconciliation audit record required")

            verify_status, verify = base.http_json(
                "GET", tg_url + "/v1/audit/verify", token=operator_token
            )
            if verify_status != 200 or verify.get("ok") is not True:
                raise L7Error("TG audit chain failed after reconciliation")

            # Revalidation is allowed only AFTER exact remote reconciliation.
            # We deliberately stop at needs_approval and never retry the effect.
            status, proposed = base.http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token,
                body=manifest["action_body"],
            )
            if status != 202 or proposed.get("decision") != "needs_approval":
                raise L7Error("post-reconciliation authority revalidation failed")
            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_b:
                raise L7Error("revalidation changed reconciled remote effect")

            _, audit2 = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=1000",
                token=operator_token,
            )
            if matching_audit(audit2.get("entries", []), "git_egress_completed", ctx_id):
                raise L7Error("Host B retried external effect after reconciliation")
            if matching_audit(audit2.get("entries", []), "egress_dispatched", ctx_id):
                raise L7Error("Host B dispatched external effect after reconciliation")

            sentinel = base.sentinel_review(roots["sentinel"], gh_env)
            if sentinel.get("review", {}).get("headSha") != sha_b:
                raise L7Error("Sentinel reviewed another L7 head")
            if sentinel.get("verdict", {}).get("decision") != "SHIP":
                raise L7Error("Sentinel did not SHIP exact L7 subject")
            sentinel_receipt = sentinel.get("receipt", {}).get("receipt_id")
            if not isinstance(sentinel_receipt, str) or len(sentinel_receipt) != 64:
                raise L7Error("Sentinel receipt malformed")

            subject = f"git:{TARGET_REPO}@{sha_b}"
            bind_request = {
                "workId": identity["work_id"],
                "worksExecutionId": identity["works_execution_id"],
                "attemptId": ATTEMPT,
                "effectId": EFFECT,
                "causalId": CAUSAL,
                "subject": subject,
            }
            bound = json.loads(base.run(
                ["node", str(bind_cli)],
                env=runtime_env,
                input_text=json.dumps(bind_request),
            ).stdout)
            if bound.get("ok") is not True or bound.get("receipt", {}).get("subject") != subject:
                raise L7Error("L7 subject binding failed")

            # execution_pdr_id is minted by the Host A approval path before the
            # crash. It is not available in the response because the process
            # dies, so recover it from the durable TG audit chain.
            pdr_ids = []
            for row in entries:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("actionId") != ACTION:
                    continue
                value = payload.get("executionPdrId") or payload.get("execution_pdr_id")
                if isinstance(value, str) and value.startswith("pdr_"):
                    pdr_ids.append(value)
            pdr_ids = sorted(set(pdr_ids))
            if len(pdr_ids) != 1:
                # Current TG audit may not expose the execution PDR in a generic
                # event. Resolve it from the post-reconciliation needs-approval
                # response, which is bound by the same execution context/AIE path.
                execution_pdr = proposed.get("execution_pdr_id")
            else:
                execution_pdr = pdr_ids[0]
            if not isinstance(execution_pdr, str) or not execution_pdr.startswith("pdr_"):
                raise L7Error("execution PDR unavailable for MissionAcceptance")

            acceptance_body = {
                "schema": "dispatch.mission-acceptance/1.0",
                "execution_context_id": ctx_id,
                "execution_pdr_id": execution_pdr,
                "verifier_id": "sentinel:exact-head",
                "sentinel_head_sha": sha_b,
                "sentinel_verdict": "SHIP",
                "sentinel_receipt_id": sentinel_receipt,
            }
            accept_url = (
                works_url + "/v2/works/" + quote(identity["work_id"], safe="")
                + "/acceptances/" + quote(identity["works_execution_id"], safe="")
                + "/mission-acceptance"
            )
            headers = {
                "X-Works-Platform-Bridge": bridge_secret,
                "X-WORKS-Verifier-Token": verifier_token,
            }
            status, accepted = base.http_json(
                "POST", accept_url,
                token=works_token,
                body=acceptance_body,
                headers=headers,
            )
            if (
                status != 200
                or accepted.get("verified") is not True
                or accepted.get("outcome") != "SUCCEEDED"
                or accepted.get("execution_context_id") != ctx_id
                or accepted.get("verification_subject") != subject
            ):
                raise L7Error("L7 MissionAcceptance did not commit Verified Outcome")

            retry_status, accepted_retry = base.http_json(
                "POST", accept_url,
                token=works_token,
                body=acceptance_body,
                headers=headers,
            )
            if retry_status != 200 or accepted_retry.get("verification_subject") != subject:
                raise L7Error("L7 MissionAcceptance retry was not idempotent")

            wrong = dict(acceptance_body)
            wrong["execution_pdr_id"] = "pdr_" + "9" * 32
            wrong_status, _ = base.http_json(
                "POST", accept_url, token=works_token, body=wrong, headers=headers
            )
            stale = dict(acceptance_body)
            stale["sentinel_head_sha"] = sha_a
            stale_status, _ = base.http_json(
                "POST", accept_url, token=works_token, body=stale, headers=headers
            )
            prior = dict(acceptance_body)
            prior["execution_context_id"] = PRIOR_L6_CONTEXT
            prior_status, _ = base.http_json(
                "POST", accept_url, token=works_token, body=prior, headers=headers
            )
            if (wrong_status, stale_status, prior_status) != (409, 409, 409):
                raise L7Error("L7 hostile MissionAcceptance seam failed")

            base.revoke_aie(roots["aie"], aie_state, os.environ.copy())
            before = len(matching_audit(audit2.get("entries", []), "git_egress_completed", ctx_id))
            status, proposed2 = base.http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token,
                body=manifest["action_body"],
            )
            if status != 202:
                raise L7Error("revocation replay did not reach approval boundary")
            status, rejected = base.http_json(
                "POST",
                tg_url + f"/v1/approvals/{quote(proposed2['approvalId'])}/approve",
                token=operator_token,
                body={},
            )
            if status != 403 or rejected.get("error") != "authority_revoked":
                raise L7Error("revoked authority did not fail closed")
            _, audit3 = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=1000", token=operator_token
            )
            after = len(matching_audit(audit3.get("entries", []), "git_egress_completed", ctx_id))
            if after != before:
                raise L7Error("revoked action reached Git egress")

            receipt = {
                "schema": "study015.l7-indeterminate-effect-reconciliation/1.0",
                "execution_class": "LIVE_INTEGRATION_CONFORMANCE",
                "evidence_class": "L7_INDETERMINATE_EFFECT_RECONCILIATION_CANDIDATE",
                "performance_claim": False,
                "g15_9_authorized": False,
                "production_deployment": False,
                "network_used": True,
                "heads": heads,
                "host_a": host_a,
                "host_b": host_b,
                "proof_target": {
                    **proof,
                    "remote_readback": base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env),
                },
                "identity": {
                    **identity,
                    "execution_pdr_id": execution_pdr,
                    "sentinel_receipt_id": sentinel_receipt,
                    "exact_subject": subject,
                },
                "uncertainty": {
                    "effect_state_at_handoff": "INDETERMINATE",
                    "external_commit_observed_after_crash": True,
                    "local_egress_dispatched_absent": True,
                    "local_git_completion_absent": True,
                    "reconciliation_status": reconciliation["status"],
                    "reconciliation_before_retry": True,
                    "retry_allowed_after_reconciliation": reconciliation["retry_allowed"],
                    "effect_retry_executed": False,
                    "tg_reconciliation_audit_recorded": True,
                    "exact_subject_verified": True,
                    "durable_verified_outcome": True,
                },
                "classifier_falsification": {
                    "known_pre_state_classifies_absent_retry_eligible": absent_vector["status"] == "ABSENT_RETRY_ELIGIBLE" and absent_vector["retry_allowed"] is True,
                    "divergent_state_classifies_conflict_fail_closed": conflict_vector["status"] == "CONFLICT_FAIL_CLOSED" and conflict_vector["retry_allowed"] is False,
                },
                "handoff": {
                    "phase_a_sha256": manifest["phase_a_sha256"],
                    "files_verified": True,
                    "secrets_transferred": False,
                    "fresh_host_b_secrets": True,
                    "works_relocated": resumed_works.get("relocated") is True,
                    "tg_audit_chain_transferred": True,
                },
                "controlled_single_writer_fence": {
                    "host_a_gateway_stopped_before_handoff": manifest["single_writer_fence"]["host_a_gateway_stopped"],
                    "host_a_works_stopped_before_handoff": manifest["single_writer_fence"]["host_a_works_stopped"],
                    "handoff_built_after_host_a_stop": manifest["single_writer_fence"]["handoff_built_after_host_a_stop"],
                    "host_b_started_from_immutable_handoff": True,
                    "no_host_b_effect_dispatch": True,
                },
                "hostile": {
                    "wrong_pdr_rejected": True,
                    "stale_verification_head_rejected": True,
                    "prior_l6_execution_context_rejected": True,
                    "revoked_authority_rejected_before_egress": True,
                    "divergent_remote_state_fails_closed": True,
                },
                "prior_l6_receipt_sha256": PRIOR_L6_RECEIPT,
            }
            for group in (
                "classifier_falsification",
                "controlled_single_writer_fence",
                "hostile",
            ):
                if not all(receipt[group].values()):
                    raise L7Error(f"L7 invariant group failed: {group}")
            canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt["causal_slice_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
            print(json.dumps(receipt, sort_keys=True))
            return receipt
        finally:
            l6.terminate(tg_proc, kill=True)
            l6.terminate(works_proc, kill=True)
            try:
                base.patch_ref(TARGET_REPO, TARGET_BRANCH, sha_b, gh_env)
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "resume"])
    parser.add_argument("--handoff", required=True)
    args = parser.parse_args()
    handoff = Path(args.handoff).resolve()
    if args.phase == "prepare":
        prepare(handoff)
    else:
        resume(handoff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
