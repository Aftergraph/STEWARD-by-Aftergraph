#!/usr/bin/env python3
"""STUDY-015 L6 cross-host causal failover.

Two-phase durability/conformance proof; never a performance experiment.
Phase A commits one governed external effect on Host A and exports only
non-secret durable state. Phase B MUST run on another physical host, verify the
handoff hashes, re-issue all secrets, recover the same causal identity, and
finish exact-head verification + MissionAcceptance without a duplicate effect.

G15-9 remains unauthorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import study015_l5_durable_recovery as base

ORG = "org_" + "1" * 32
TENANT = "ten_" + "2" * 32
PRINCIPAL = "prn_" + "3" * 32
AUTH = "auth_" + "4" * 32
ADMISSION = "pdr_" + "8" * 32
ACTION = "act_" + "d" * 32
MISSION = "mis_study015_l6_cross_host"
ATTEMPT = "attempt/study015/live-4"
EFFECT = "effect/study015/live-4"
CAUSAL = "causal/study015/live-4"
TARGET_REPO = "Aftergraph/runtime"
TARGET_BRANCH = "study015/l6-cross-host-proof-target"
TARGET_REF = "refs/heads/" + TARGET_BRANCH
TARGET_PR = 211

PRIOR_L5_CONTEXT = "ctx_62ae40ce4ba8cf61672c9045dc61ceb1"
PRIOR_L5_RECEIPT = "9bb6d0ed6833d09f7b5e9e0d2b70b3eeb7c3aba922fd887eed3c1e91fced7178"


class L6Error(RuntimeError):
    pass


def configure_base() -> None:
    base.ORG = ORG
    base.TENANT = TENANT
    base.PRINCIPAL = PRINCIPAL
    base.AUTH = AUTH
    base.ADMISSION = ADMISSION
    base.ACTION = ACTION
    base.MISSION = MISSION
    base.ATTEMPT = ATTEMPT
    base.EFFECT = EFFECT
    base.CAUSAL = CAUSAL
    base.TARGET_REPO = TARGET_REPO
    base.TARGET_BRANCH = TARGET_BRANCH
    base.TARGET_REF = TARGET_REF
    base.TARGET_PR = TARGET_PR


def host_identity() -> dict:
    machine_path = Path("/etc/machine-id")
    if not machine_path.is_file():
        raise L6Error("/etc/machine-id unavailable; cannot prove physical host identity")
    machine_id = machine_path.read_text(encoding="utf-8").strip()
    if not machine_id:
        raise L6Error("empty /etc/machine-id")
    runner_name = os.environ.get("RUNNER_NAME", "").strip()
    if not runner_name:
        raise L6Error("RUNNER_NAME unavailable")
    hostname = socket.gethostname().strip()
    if not hostname:
        raise L6Error("hostname unavailable")
    return {
        "runner_name": runner_name,
        "hostname": hostname,
        "machine_id_sha256": hashlib.sha256(machine_id.encode()).hexdigest(),
    }


def exact_roots() -> tuple[dict[str, Path], dict[str, str]]:
    roots = {
        "runtime": Path(os.environ["STUDY015_RUNTIME_ROOT"]).resolve(),
        "works": Path(os.environ["STUDY015_WORKS_ROOT"]).resolve(),
        "trust_gateway": Path(os.environ["STUDY015_TG_ROOT"]).resolve(),
        "aie": Path(os.environ["STUDY015_AIE_ROOT"]).resolve(),
        "sentinel": Path(os.environ["STUDY015_SENTINEL_ROOT"]).resolve(),
    }
    heads = {
        "runtime": os.environ["STUDY015_RUNTIME_HEAD"],
        "works": os.environ["STUDY015_WORKS_HEAD"],
        "trust_gateway": os.environ["STUDY015_TG_HEAD"],
        "aie": os.environ["STUDY015_AIE_HEAD"],
        "sentinel": os.environ["STUDY015_SENTINEL_HEAD"],
    }
    for name, root in roots.items():
        base.require_exact(root, heads[name], name)
    return roots, heads


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def durable_files(state_dir: Path) -> list[Path]:
    allowed = []
    for path in sorted(state_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(state_dir).as_posix()
        if rel == "works-ready.json":
            allowed.append(path)
        elif rel.startswith("works.db"):
            allowed.append(path)
        elif rel.startswith("aie-state.db"):
            allowed.append(path)
        elif rel == "tg-data/study015-audit.jsonl":
            allowed.append(path)
        elif rel == "phase-a.json":
            allowed.append(path)
        else:
            raise L6Error(f"unexpected handoff file: {rel}")
    return allowed


def scan_no_secrets(state_dir: Path, secret_values: list[str]) -> None:
    needles = [s.encode() for s in secret_values if s]
    for path in durable_files(state_dir):
        raw = path.read_bytes()
        for needle in needles:
            if needle in raw:
                raise L6Error(f"secret material leaked into handoff: {path.name}")


def manifest_file_map(state_dir: Path) -> dict[str, dict]:
    out = {}
    for path in durable_files(state_dir):
        rel = path.relative_to(state_dir).as_posix()
        if rel == "phase-a.json":
            continue
        out[rel] = {"sha256": file_sha256(path), "size": path.stat().st_size}
    return out


def verify_handoff_files(state_dir: Path, manifest: dict) -> None:
    expected = manifest.get("handoff_files")
    if not isinstance(expected, dict) or not expected:
        raise L6Error("phase-A manifest has no handoff files")
    actual_paths = {
        p.relative_to(state_dir).as_posix()
        for p in durable_files(state_dir)
        if p.relative_to(state_dir).as_posix() != "phase-a.json"
    }
    if actual_paths != set(expected):
        raise L6Error(f"handoff file set mismatch: actual={sorted(actual_paths)} expected={sorted(expected)}")
    for rel, meta in expected.items():
        path = state_dir / rel
        if path.stat().st_size != meta.get("size"):
            raise L6Error(f"handoff size mismatch: {rel}")
        if file_sha256(path) != meta.get("sha256"):
            raise L6Error(f"handoff SHA mismatch: {rel}")


def runtime_paths(runtime_root: Path) -> tuple[Path, Path]:
    dispatch = runtime_root / "packages/runtime-host/dist/steward-dispatch-v2-cli.js"
    bind = runtime_root / "packages/runtime-host/dist/steward-bind-subject-v2-cli.js"
    if not dispatch.is_file() or not bind.is_file():
        raise L6Error("Runtime V2 CLIs are not built")
    return dispatch, bind


def api_env(works_url: str, works_token: str, bridge_secret: str) -> dict:
    env = os.environ.copy()
    env.update({
        "WORKS_BASE_URL": works_url,
        "WORKS_BEARER_TOKEN": works_token,
        "WORKS_PLATFORM_BRIDGE_SECRET": bridge_secret,
    })
    return env


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
        "request_id": "req/study015/live-4",
        "repository": TARGET_REPO,
        "ref": TARGET_REF,
        "new_sha": sha_b,
        "force": True,
    }


def tg_fingerprint(tg_root: Path, args: dict) -> str:
    js = (
        "const {actionFingerprint}=require(process.argv[1]);"
        "const args=JSON.parse(process.argv[2]);"
        "process.stdout.write(actionFingerprint({bot:'worker',tool:'git.push',args}));"
    )
    digest = base.run(
        ["node", "-e", js, str(tg_root / "src/gateway/aie-client.js"), json.dumps(args, separators=(",", ":"))]
    ).stdout.strip()
    if len(digest) != 64:
        raise L6Error("TG action fingerprint malformed")
    return digest


def start_works(
    works_root: Path,
    *,
    db: Path,
    ready: Path,
    works_token: str,
    bridge_secret: str,
    verifier_token: str,
    resume_fixture: Path | None = None,
    relocated: bool = False,
):
    binary = works_root / "study015-live-works"
    if not binary.is_file():
        base.run(["go", "build", "-o", str(binary), "./cmd/study015-live-works"], cwd=works_root)
    env = os.environ.copy()
    env.update({
        "WORKS_API_TOKEN": works_token,
        "WORKS_PLATFORM_BRIDGE_SECRET": bridge_secret,
        "WORKS_VERIFIER_TOKEN": verifier_token,
    })
    argv = [str(binary), "--addr", "127.0.0.1:0", "--db", str(db), "--fixture-out", str(ready)]
    if resume_fixture is not None:
        argv += ["--resume-fixture", str(resume_fixture)]
        if relocated:
            argv += ["--resume-relocated"]
    proc = subprocess.Popen(
        argv, cwd=works_root, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc, env


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
    proc = subprocess.Popen(
        ["node", "bin/study015-live-gateway.js"],
        cwd=tg_root, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc, env


def terminate(proc: subprocess.Popen | None, *, kill: bool = False) -> None:
    if proc is None or proc.poll() is not None:
        return
    if kill:
        proc.kill()
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def prepare(handoff: Path) -> dict:
    configure_base()
    roots, heads = exact_roots()
    host_a = host_identity()
    sha_a = os.environ["STUDY015_SHA_A"]
    sha_b = os.environ["STUDY015_SHA_B"]
    if len(sha_a) != 40 or len(sha_b) != 40 or sha_a == sha_b:
        raise L6Error("invalid proof SHAs")
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise L6Error("GitHub token missing")
    gh_env = os.environ.copy()
    gh_env["GH_TOKEN"] = gh_token

    state_dir = handoff / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "tg-data").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="study015-l6-a-") as td:
        local = Path(td)
        works_token = secrets.token_hex(32)
        bridge_secret = secrets.token_hex(32)
        verifier_token = secrets.token_hex(32)
        worker_token = secrets.token_hex(24)
        operator_token = secrets.token_hex(24)
        vault_master = secrets.token_hex(32)
        secret_values = [
            works_token, bridge_secret, verifier_token, worker_token,
            operator_token, vault_master, gh_token,
        ]

        works_db = state_dir / "works.db"
        works_ready = state_dir / "works-ready.json"
        aie_state = state_dir / "aie-state.db"
        tg_ready = local / "tg-ready.json"

        dispatch_cli, _ = runtime_paths(roots["runtime"])
        works_proc, _ = start_works(
            roots["works"], db=works_db, ready=works_ready,
            works_token=works_token, bridge_secret=bridge_secret,
            verifier_token=verifier_token,
        )
        tg_proc = None
        try:
            fixture = base.wait_json(works_ready, works_proc)
            works_url = fixture["base_url"]
            work_id = fixture["work_id"]
            lease_id = fixture["worker_lease_id"]
            runtime_env = api_env(works_url, works_token, bridge_secret)

            dispatch_request = {
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
                "idempotencyKey": "idem/study015/live-4",
                "budgetRef": "budget/study015/live-4",
                "budgetCeiling": 100,
                "checkpointId": "checkpoint/study015/live-4",
                "evidenceRoot": "evidence/study015/live-4",
                "causalId": CAUSAL,
            }
            dispatched = json.loads(base.run(
                ["node", str(dispatch_cli)], env=runtime_env,
                input_text=json.dumps(dispatch_request),
            ).stdout)
            if dispatched.get("ok") is not True:
                raise L6Error("Runtime dispatch failed on Host A")
            runtime_receipt = dispatched["receipt"]
            ctx_id = runtime_receipt["executionContextId"]
            works_execution_id = runtime_receipt["worksExecutionId"]

            args = action_args(ctx_id, works_execution_id, sha_b)
            digest = tg_fingerprint(roots["trust_gateway"], args)
            base.seed_aie(roots["aie"], aie_state, args, digest, os.environ.copy())

            base.patch_ref(TARGET_REPO, TARGET_BRANCH, sha_a, gh_env)
            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_a:
                raise L6Error("Host A failed to reset proof target")

            tg_proc, _ = start_tg(
                roots["trust_gateway"], root=local, state_dir=state_dir,
                aie_root=roots["aie"], aie_state=aie_state,
                works_url=works_url, works_token=works_token,
                bridge_secret=bridge_secret, worker_token=worker_token,
                operator_token=operator_token, vault_master=vault_master,
                gh_token=gh_token, ready=tg_ready,
            )
            tg_fixture = base.wait_json(tg_ready, tg_proc)
            tg_url = tg_fixture["base_url"]

            action_body = {
                "action_id": ACTION,
                "execution_context_id": ctx_id,
                "mission_id": MISSION,
                "tool": "git.push",
                "args": args,
            }
            status, proposed = base.http_json(
                "POST", tg_url + "/v1/actions", token=worker_token, body=action_body
            )
            if status != 202 or proposed.get("decision") != "needs_approval":
                raise L6Error("Host A destructive action did not reach approval boundary")
            status, approved = base.http_json(
                "POST", tg_url + f"/v1/approvals/{quote(proposed['approvalId'])}/approve",
                token=operator_token, body={},
            )
            if status != 200 or approved.get("status") != "approved":
                raise L6Error("Host A approval failed")
            execution_pdr = approved.get("execution_pdr_id")
            effect = approved.get("result") or {}
            if (
                not isinstance(execution_pdr, str)
                or effect.get("execution_context_id") != ctx_id
                or effect.get("action_id") != ACTION
                or effect.get("effect_id") != EFFECT
                or effect.get("causal_id") != CAUSAL
                or effect.get("new_sha") != sha_b
            ):
                raise L6Error("Host A effect receipt lost causal binding")

            for _ in range(20):
                if (
                    base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) == sha_b
                    and base.github_pr_head(TARGET_REPO, TARGET_PR, gh_env) == sha_b
                ):
                    break
                time.sleep(0.25)
            else:
                raise L6Error("Host A exact remote readback failed")

            # Hard failover boundary: no graceful application shutdown.
            terminate(tg_proc, kill=True)
            tg_proc = None
            terminate(works_proc, kill=True)

            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_b:
                raise L6Error("remote effect changed at Host A failure boundary")

            # The transfer set is deliberately narrow; TG DB/vault and all
            # auth tokens stay host-local and are not artifacted.
            scan_no_secrets(state_dir, secret_values)
            files = manifest_file_map(state_dir)
            manifest = {
                "schema": "study015.l6-handoff/1.0",
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
                    "execution_pdr_id": execution_pdr,
                    "effect_id": EFFECT,
                    "causal_id": CAUSAL,
                },
                "dispatch_request": dispatch_request,
                "action_body": action_body,
                "runtime_receipt": runtime_receipt,
                "handoff_files": files,
                "secrets_transferred": False,
                "excluded_state": ["tg.db", "tg vault master", "GitHub credential", "API tokens", "approval tokens"],
                "prior_l5_receipt_sha256": PRIOR_L5_RECEIPT,
            }
            canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
            manifest["phase_a_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
            (state_dir / "phase-a.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            scan_no_secrets(state_dir, secret_values)
            print(json.dumps({
                "schema": "study015.l6-phase-a/1.0",
                "status": "HANDOFF_READY",
                "host_a": host_a,
                "phase_a_sha256": manifest["phase_a_sha256"],
                "remote_readback": sha_b,
                "handoff_file_count": len(files),
                "secrets_transferred": False,
            }, sort_keys=True))
            return manifest
        finally:
            terminate(tg_proc, kill=True)
            terminate(works_proc, kill=True)
            try:
                base.patch_ref(TARGET_REPO, TARGET_BRANCH, sha_b, gh_env)
            except Exception:
                pass


def resume(handoff: Path) -> dict:
    configure_base()
    roots, heads = exact_roots()
    host_b = host_identity()
    state_dir = handoff / "state"
    phase_path = state_dir / "phase-a.json"
    if not phase_path.is_file():
        raise L6Error("phase-A manifest missing")
    manifest = json.loads(phase_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "study015.l6-handoff/1.0":
        raise L6Error("bad L6 handoff schema")
    prior_hash = manifest.pop("phase_a_sha256", None)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != prior_hash:
        raise L6Error("phase-A manifest hash mismatch")
    manifest["phase_a_sha256"] = prior_hash
    verify_handoff_files(state_dir, manifest)

    host_a = manifest["host_a"]
    if host_a.get("machine_id_sha256") == host_b.get("machine_id_sha256"):
        raise L6Error("Host B is the same physical machine as Host A")
    if host_a.get("hostname") == host_b.get("hostname"):
        raise L6Error("Host B hostname equals Host A; cross-host claim refused")
    if manifest.get("secrets_transferred") is not False:
        raise L6Error("handoff claims transferred secrets")
    if manifest.get("heads") != heads:
        raise L6Error("owner-head drift between Host A and Host B")

    proof = manifest["proof_target"]
    sha_a, sha_b = proof["sha_a"], proof["sha_b"]
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise L6Error("GitHub token missing on Host B")
    gh_env = os.environ.copy()
    gh_env["GH_TOKEN"] = gh_token
    if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_b:
        raise L6Error("Host B observed wrong remote effect before recovery")

    with tempfile.TemporaryDirectory(prefix="study015-l6-b-") as td:
        local = Path(td)
        # All secrets are freshly issued on Host B. None are loaded from handoff.
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

        dispatch_cli, bind_cli = runtime_paths(roots["runtime"])
        works_proc, _ = start_works(
            roots["works"], db=works_db, ready=works_ready_b,
            works_token=works_token, bridge_secret=bridge_secret,
            verifier_token=verifier_token, resume_fixture=prior_fixture,
            relocated=True,
        )
        tg_proc = None
        try:
            resumed_works = base.wait_json(works_ready_b, works_proc)
            identity = manifest["identity"]
            if resumed_works.get("recovered") is not True or resumed_works.get("relocated") is not True:
                raise L6Error("WORKS did not enter explicit relocated recovery")
            if resumed_works.get("work_id") != identity["work_id"]:
                raise L6Error("WORKS rebound work identity across hosts")
            if resumed_works.get("worker_lease_id") != identity["worker_lease_id"]:
                raise L6Error("WORKS rebound lease identity across hosts")
            if resumed_works.get("prior_db_path") == resumed_works.get("db_path"):
                raise L6Error("WORKS relocation receipt did not record a path change")

            works_url = resumed_works["base_url"]
            runtime_env = api_env(works_url, works_token, bridge_secret)
            replayed = json.loads(base.run(
                ["node", str(dispatch_cli)], env=runtime_env,
                input_text=json.dumps(manifest["dispatch_request"]),
            ).stdout)
            if replayed.get("ok") is not True:
                raise L6Error("Runtime dispatch replay failed on Host B")
            replay_receipt = replayed["receipt"]
            for field in ("runtimeDispatchId","worksExecutionId","workId","executionContextId","traceId","workerId"):
                if replay_receipt.get(field) != manifest["runtime_receipt"].get(field):
                    raise L6Error(f"cross-host dispatch rebound {field}")

            ctx_id = identity["execution_context_id"]
            ctx_status, recovered_context = base.http_json(
                "GET", works_url + "/v1/execution-contexts/" + quote(ctx_id, safe="")
            )
            if ctx_status != 200:
                raise L6Error("WORKS durable execution context unavailable on Host B")
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
                    raise L6Error(f"Host B execution context rebound {key}")

            tg_proc, _ = start_tg(
                roots["trust_gateway"], root=local, state_dir=state_dir,
                aie_root=roots["aie"], aie_state=aie_state,
                works_url=works_url, works_token=works_token,
                bridge_secret=bridge_secret, worker_token=worker_token,
                operator_token=operator_token, vault_master=vault_master,
                gh_token=gh_token, ready=tg_ready_b,
            )
            resumed_tg = base.wait_json(tg_ready_b, tg_proc)
            if resumed_tg.get("mission_id") != MISSION or resumed_tg.get("authority_lease_id") != AUTH:
                raise L6Error("TG rebound mission/authority on Host B")
            tg_url = resumed_tg["base_url"]

            audit_status, audit = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=500", token=operator_token
            )
            if audit_status != 200:
                raise L6Error("TG audit unavailable on Host B")
            entries = audit.get("entries", [])
            effects = [
                e for e in entries
                if isinstance(e, dict)
                and isinstance(e.get("payload"), dict)
                and e["payload"].get("type") == "git_egress_completed"
                and e["payload"].get("actionId") == ACTION
                and e["payload"].get("effectId") == EFFECT
                and e["payload"].get("executionContextId") == ctx_id
            ]
            if len(effects) != 1:
                raise L6Error(f"expected one transferred external-effect receipt, got {len(effects)}")
            verify_status, verify = base.http_json(
                "GET", tg_url + "/v1/audit/verify", token=operator_token
            )
            if verify_status != 200 or verify.get("ok") is not True:
                raise L6Error("transferred TG audit chain failed verification")

            # Re-run authorization only; never approve a second destructive effect.
            reval_status, reval = base.http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token, body=manifest["action_body"],
            )
            if reval_status != 202 or reval.get("decision") != "needs_approval":
                raise L6Error("Host B authority revalidation did not reach approval boundary")
            if base.github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != sha_b:
                raise L6Error("Host B revalidation changed remote effect")

            _, audit2 = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=500", token=operator_token
            )
            effects2 = [
                e for e in audit2.get("entries", [])
                if isinstance(e, dict)
                and isinstance(e.get("payload"), dict)
                and e["payload"].get("type") == "git_egress_completed"
                and e["payload"].get("actionId") == ACTION
                and e["payload"].get("effectId") == EFFECT
                and e["payload"].get("executionContextId") == ctx_id
            ]
            if len(effects2) != 1:
                raise L6Error("Host B duplicated external effect")

            sentinel = base.sentinel_review(roots["sentinel"], gh_env)
            if sentinel.get("review", {}).get("headSha") != sha_b:
                raise L6Error("Sentinel reviewed wrong L6 head")
            if sentinel.get("verdict", {}).get("decision") != "SHIP":
                raise L6Error("Sentinel did not SHIP L6 exact head")
            sentinel_receipt = sentinel.get("receipt", {}).get("receipt_id")
            if not isinstance(sentinel_receipt, str) or len(sentinel_receipt) != 64:
                raise L6Error("Sentinel receipt malformed")

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
                ["node", str(bind_cli)], env=runtime_env,
                input_text=json.dumps(bind_request),
            ).stdout)
            if bound.get("ok") is not True or bound.get("receipt", {}).get("subject") != subject:
                raise L6Error("cross-host subject binding failed")

            acceptance_body = {
                "schema": "dispatch.mission-acceptance/1.0",
                "execution_context_id": ctx_id,
                "execution_pdr_id": identity["execution_pdr_id"],
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
                "POST", accept_url, token=works_token, body=acceptance_body, headers=headers
            )
            if (
                status != 200 or accepted.get("verified") is not True
                or accepted.get("outcome") != "SUCCEEDED"
                or accepted.get("execution_context_id") != ctx_id
                or accepted.get("verification_subject") != subject
            ):
                raise L6Error("Host B MissionAcceptance did not commit Verified Outcome")
            retry_status, retry = base.http_json(
                "POST", accept_url, token=works_token, body=acceptance_body, headers=headers
            )
            if retry_status != 200 or retry.get("verification_subject") != subject:
                raise L6Error("cross-host MissionAcceptance retry not idempotent")

            # Hostile seams.
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
            prior["execution_context_id"] = PRIOR_L5_CONTEXT
            prior_status, _ = base.http_json(
                "POST", accept_url, token=works_token, body=prior, headers=headers
            )
            if (wrong_status, stale_status, prior_status) != (409, 409, 409):
                raise L6Error("cross-host hostile MissionAcceptance seam failed")

            base.revoke_aie(roots["aie"], aie_state, os.environ.copy())
            before = len(effects2)
            status, proposed = base.http_json(
                "POST", tg_url + "/v1/actions", token=worker_token,
                body=manifest["action_body"],
            )
            if status != 202:
                raise L6Error("revocation replay did not reach approval boundary")
            status, rejected = base.http_json(
                "POST", tg_url + f"/v1/approvals/{quote(proposed['approvalId'])}/approve",
                token=operator_token, body={},
            )
            if status != 403 or rejected.get("error") != "authority_revoked":
                raise L6Error("revoked authority did not fail closed on Host B")
            _, audit3 = base.http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=500", token=operator_token
            )
            after = sum(
                1 for e in audit3.get("entries", [])
                if isinstance(e, dict)
                and isinstance(e.get("payload"), dict)
                and e["payload"].get("type") == "git_egress_completed"
                and e["payload"].get("actionId") == ACTION
                and e["payload"].get("effectId") == EFFECT
                and e["payload"].get("executionContextId") == ctx_id
            )
            if after != before:
                raise L6Error("revoked Host B action reached Git egress")

            receipt = {
                "schema": "study015.l6-cross-host-failover/1.0",
                "execution_class": "LIVE_INTEGRATION_CONFORMANCE",
                "evidence_class": "L6_CROSS_HOST_CAUSAL_FAILOVER_CANDIDATE",
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
                    "sentinel_receipt_id": sentinel_receipt,
                    "exact_subject": subject,
                },
                "handoff": {
                    "phase_a_sha256": manifest["phase_a_sha256"],
                    "files_verified": True,
                    "secrets_transferred": False,
                    "fresh_host_b_secrets": True,
                    "works_relocated": resumed_works.get("relocated") is True,
                    "tg_audit_chain_transferred": True,
                },
                "cross_host": {
                    "machine_identity_changed": host_a["machine_id_sha256"] != host_b["machine_id_sha256"],
                    "hostname_changed": host_a["hostname"] != host_b["hostname"],
                    "same_work": replay_receipt["workId"] == identity["work_id"],
                    "same_execution_context": replay_receipt["executionContextId"] == ctx_id,
                    "same_trace": replay_receipt["traceId"] == identity["trace_id"],
                    "same_works_execution": replay_receipt["worksExecutionId"] == identity["works_execution_id"],
                    "single_external_effect": after == 1,
                    "durable_verified_outcome": accepted.get("verified") is True,
                },
                "hostile": {
                    "wrong_pdr_rejected": True,
                    "stale_verification_head_rejected": True,
                    "prior_l5_execution_context_rejected": True,
                    "revoked_authority_rejected_before_egress": True,
                },
                "prior_l5_receipt_sha256": PRIOR_L5_RECEIPT,
            }
            if not all(receipt["cross_host"].values()):
                raise L6Error("cross-host invariant set incomplete")
            canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt["causal_slice_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
            print(json.dumps(receipt, sort_keys=True))
            return receipt
        finally:
            terminate(tg_proc, kill=True)
            terminate(works_proc, kill=True)
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
