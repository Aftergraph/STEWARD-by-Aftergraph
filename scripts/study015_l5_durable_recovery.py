#!/usr/bin/env python3
"""STUDY-015 L5 durable causal recovery.

This is a durability/recovery conformance proof, not a performance experiment.
G15-9 remains unapproved. The script composes real process boundaries:
WORKS HTTP -> Runtime CLI -> TG HTTP -> AIE bridge subprocess -> governed
GitHub effect -> exact remote readback -> Sentinel CLI -> Runtime subject
binding -> durable WORKS MissionAcceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ORG = "org_" + "1" * 32
TENANT = "ten_" + "2" * 32
PRINCIPAL = "prn_" + "3" * 32
AUTH = "auth_" + "4" * 32
ADMISSION = "pdr_" + "7" * 32
ACTION = "act_" + "c" * 32
MISSION = "mis_study015_l5_durable_recovery"
ATTEMPT = "attempt/study015/live-3"
EFFECT = "effect/study015/live-3"
CAUSAL = "causal/study015/live-3"
TARGET_REPO = "Aftergraph/runtime"
TARGET_BRANCH = "study015/l5-durable-recovery-proof-target"
TARGET_REF = "refs/heads/" + TARGET_BRANCH
TARGET_PR = 209


class ProofError(RuntimeError):
    pass


def run(argv, *, cwd=None, env=None, input_text=None, ok=(0,)):
    proc = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in ok:
        raise ProofError(
            f"{Path(argv[0]).name} failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[-2000:]}"
        )
    return proc


def git_head(root: Path) -> str:
    return run(["git", "-C", str(root), "rev-parse", "HEAD"]).stdout.strip()


def require_exact(root: Path, expected: str, label: str) -> None:
    actual = git_head(root)
    if actual != expected:
        raise ProofError(f"{label} exact-head mismatch: {actual} != {expected}")


def http_json(method, url, *, token=None, body=None, headers=None):
    payload = None if body is None else json.dumps(body).encode()
    req_headers = {"accept": "application/json"}
    if payload is not None:
        req_headers["content-type"] = "application/json"
    if token:
        req_headers["authorization"] = "Bearer " + token
    if headers:
        req_headers.update(headers)
    req = Request(url, method=method, data=payload, headers=req_headers)
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw or "{}")
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            parsed = {"error": "non_json"}
        return exc.code, parsed


def wait_json(path: Path, proc: subprocess.Popen, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise ProofError(f"process exited before readiness: rc={proc.returncode}")
        if path.is_file() and path.stat().st_size > 0:
            return json.loads(path.read_text())
        time.sleep(0.1)
    raise ProofError(f"readiness timeout: {path.name}")


def github_ref_sha(repo: str, branch: str, env) -> str:
    return run(
        ["gh", "api", f"repos/{repo}/git/ref/heads/{branch}", "--jq", ".object.sha"],
        env=env,
    ).stdout.strip()


def github_pr_head(repo: str, pr: int, env) -> str:
    return run(
        ["gh", "api", f"repos/{repo}/pulls/{pr}", "--jq", ".head.sha"],
        env=env,
    ).stdout.strip()


def patch_ref(repo: str, branch: str, sha: str, env) -> None:
    run(
        [
            "gh", "api", "-X", "PATCH",
            f"repos/{repo}/git/refs/heads/{branch}",
            "-f", f"sha={sha}", "-F", "force=true",
        ],
        env=env,
    )


def seed_aie(aie_root: Path, state_file: Path, args: dict, digest: str, env) -> None:
    code = """
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
root, db, action, principal, mission, authority, digest, repo, ref = sys.argv[1:]
sys.path.insert(0, str(Path(root) / "src"))
from aie_runtime.engine import ActionRequest, AdmissionEngine, AuthorityLease, Mission, Principal
from aie_runtime.persistent_state import PersistentState
now = datetime.now(timezone.utc)
state = PersistentState(db_path=db)
state.principals[principal] = Principal(principal, "agent", "ref:study015-live")
state.missions[mission] = Mission(mission, "RUNNING")
state.leases[authority] = AuthorityLease(
    id=authority, principal_id=principal, mission_id=mission,
    capabilities={"git.push"}, resource_prefixes=("repo:" + repo,),
    expires_at=now + timedelta(minutes=30), budget_remaining=20, revoked=False,
)
engine = AdmissionEngine(state, policy=lambda _: True)
engine.admit(ActionRequest(
    action, principal, mission, authority, "git.push",
    "repo:" + repo + "#" + ref, 1,
    extensions=({"namespace":"urn:aftergraph:tg-action:v1","sha256":digest},),
))
state.save_all()
state._conn.close()
"""
    run(
        [
            sys.executable, "-c", code, str(aie_root), str(state_file),
            ACTION, PRINCIPAL, MISSION, AUTH, digest, TARGET_REPO, TARGET_REF,
        ],
        env=env,
    )


def revoke_aie(aie_root: Path, state_file: Path, env) -> None:
    code = """
import sys
from pathlib import Path
root, db, authority = sys.argv[1:]
sys.path.insert(0, str(Path(root) / "src"))
from aie_runtime.engine import AdmissionEngine
from aie_runtime.persistent_state import PersistentState
state = PersistentState(db_path=db)
AdmissionEngine(state=state, policy=lambda _: True).revoke(authority)
state.save_all()
state._conn.close()
"""
    run([sys.executable, "-c", code, str(aie_root), str(state_file), AUTH], env=env)


def sentinel_review(sentinel_root: Path, env):
    proc = run(
        [
            "node", str(sentinel_root / "bin" / "sentinel.js"),
            "review", "--pr", str(TARGET_PR), "--repo", TARGET_REPO,
            "--format", "json", "--no-ledger",
        ],
        env=env,
        ok=(0, 1),
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ProofError("Sentinel emitted non-JSON") from exc


def main() -> int:
    runtime_root = Path(os.environ["STUDY015_RUNTIME_ROOT"]).resolve()
    works_root = Path(os.environ["STUDY015_WORKS_ROOT"]).resolve()
    tg_root = Path(os.environ["STUDY015_TG_ROOT"]).resolve()
    aie_root = Path(os.environ["STUDY015_AIE_ROOT"]).resolve()
    sentinel_root = Path(os.environ["STUDY015_SENTINEL_ROOT"]).resolve()

    expected = {
        "runtime": os.environ["STUDY015_RUNTIME_HEAD"],
        "works": os.environ["STUDY015_WORKS_HEAD"],
        "trust_gateway": os.environ["STUDY015_TG_HEAD"],
        "aie": os.environ["STUDY015_AIE_HEAD"],
        "sentinel": os.environ["STUDY015_SENTINEL_HEAD"],
    }
    require_exact(runtime_root, expected["runtime"], "Runtime")
    require_exact(works_root, expected["works"], "WORKS")
    require_exact(tg_root, expected["trust_gateway"], "Trust Gateway")
    require_exact(aie_root, expected["aie"], "AIE")
    require_exact(sentinel_root, expected["sentinel"], "Sentinel")

    proof_sha_a = os.environ["STUDY015_SHA_A"]
    proof_sha_b = os.environ["STUDY015_SHA_B"]
    if len(proof_sha_a) != 40 or len(proof_sha_b) != 40 or proof_sha_a == proof_sha_b:
        raise ProofError("invalid proof target SHAs")

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise ProofError("GitHub token missing")
    gh_env = os.environ.copy()
    gh_env["GH_TOKEN"] = gh_token

    with tempfile.TemporaryDirectory(prefix="study015-live-causal-") as td:
        root = Path(td)
        works_token = secrets.token_hex(32)
        bridge_secret = secrets.token_hex(32)
        verifier_token = secrets.token_hex(32)
        worker_token = secrets.token_hex(24)
        operator_token = secrets.token_hex(24)
        vault_master = secrets.token_hex(32)
        works_ready = root / "works-ready.json"
        tg_ready = root / "tg-ready.json"
        aie_state = root / "aie-state.db"
        works_db = root / "works.db"

        works_bin = works_root / "study015-live-works"
        run(
            ["go", "build", "-o", str(works_bin), "./cmd/study015-live-works"],
            cwd=works_root,
        )
        runtime_dispatch = runtime_root / "packages/runtime-host/dist/steward-dispatch-v2-cli.js"
        runtime_bind = runtime_root / "packages/runtime-host/dist/steward-bind-subject-v2-cli.js"
        if not runtime_dispatch.is_file() or not runtime_bind.is_file():
            raise ProofError("Runtime V2 CLIs not built")

        child_env = os.environ.copy()
        child_env.update({
            "WORKS_API_TOKEN": works_token,
            "WORKS_PLATFORM_BRIDGE_SECRET": bridge_secret,
            "WORKS_VERIFIER_TOKEN": verifier_token,
        })
        works_proc = subprocess.Popen(
            [
                str(works_bin), "--addr", "127.0.0.1:0",
                "--db", str(works_db), "--fixture-out", str(works_ready),
            ],
            cwd=works_root,
            env=child_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tg_proc = None
        try:
            fixture = wait_json(works_ready, works_proc)
            works_url = fixture["base_url"]
            work_id = fixture["work_id"]
            lease_id = fixture["worker_lease_id"]

            runtime_env = os.environ.copy()
            runtime_env.update({
                "WORKS_BASE_URL": works_url,
                "WORKS_BEARER_TOKEN": works_token,
                "WORKS_PLATFORM_BRIDGE_SECRET": bridge_secret,
            })
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
                "idempotencyKey": "idem/study015/live-3",
                "budgetRef": "budget/study015/live-3",
                "budgetCeiling": 100,
                "checkpointId": "checkpoint/study015/live-3",
                "evidenceRoot": "evidence/study015/live-3",
                "causalId": CAUSAL,
            }
            dispatched = json.loads(run(
                ["node", str(runtime_dispatch)],
                env=runtime_env,
                input_text=json.dumps(dispatch_request),
            ).stdout)
            if dispatched.get("ok") is not True:
                raise ProofError(f"Runtime dispatch rejected: {dispatched.get('reason')}")
            runtime_receipt = dispatched["receipt"]
            ctx_id = runtime_receipt["executionContextId"]
            works_execution_id = runtime_receipt["worksExecutionId"]

            args = {
                "action_id": ACTION,
                "execution_context_id": ctx_id,
                "works_execution_id": works_execution_id,
                "mission_id": MISSION,
                "authority_ref": AUTH,
                "tenant_id": TENANT,
                "principal_id": PRINCIPAL,
                "effect_id": EFFECT,
                "causal_id": CAUSAL,
                "request_id": "req/study015/live-3",
                "repository": TARGET_REPO,
                "ref": TARGET_REF,
                "new_sha": proof_sha_b,
                "force": True,
            }
            fp_script = (
                "const {actionFingerprint}=require(process.argv[1]);"
                "const args=JSON.parse(process.argv[2]);"
                "process.stdout.write(actionFingerprint({bot:'worker',tool:'git.push',args}));"
            )
            digest = run(
                [
                    "node", "-e", fp_script,
                    str(tg_root / "src/gateway/aie-client.js"),
                    json.dumps(args, separators=(",", ":")),
                ],
                env=os.environ.copy(),
            ).stdout.strip()
            if len(digest) != 64:
                raise ProofError("TG action fingerprint malformed")
            seed_aie(aie_root, aie_state, args, digest, os.environ.copy())

            # Establish the known pre-effect remote state. Only the dedicated
            # proof branch is force-moved; cleanup leaves it at proof_sha_b.
            patch_ref(TARGET_REPO, TARGET_BRANCH, proof_sha_a, gh_env)
            if github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != proof_sha_a:
                raise ProofError("proof target did not reset to SHA A")

            tg_env = os.environ.copy()
            tg_env.update({
                "TG_DB_FILE": str(root / "tg.db"),
                "TG_DATA_DIR": str(root / "tg-data"),
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
                "STUDY015_TG_READY_OUT": str(tg_ready),
                "STUDY015_TG_PORT": "0",
            })
            tg_proc = subprocess.Popen(
                ["node", "bin/study015-live-gateway.js"],
                cwd=tg_root,
                env=tg_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            tg_fixture = wait_json(tg_ready, tg_proc)
            tg_url = tg_fixture["base_url"]
            tg_audit_file = tg_fixture.get("audit_file")
            if not isinstance(tg_audit_file, str) or not tg_audit_file:
                raise ProofError("TG did not expose its durable audit file")

            action_body = {
                "action_id": ACTION,
                "execution_context_id": ctx_id,
                "mission_id": MISSION,
                "tool": "git.push",
                "args": args,
            }
            status, proposed = http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token, body=action_body,
            )
            if status != 202 or proposed.get("decision") != "needs_approval":
                raise ProofError(f"TG did not park destructive action: {status}")
            approval_id = proposed["approvalId"]

            status, approved = http_json(
                "POST", tg_url + f"/v1/approvals/{quote(approval_id)}/approve",
                token=operator_token, body={},
            )
            if status != 200 or approved.get("status") != "approved":
                raise ProofError(f"TG approval failed: {status} {approved.get('error')}")
            if approved.get("execution_context_id") != ctx_id:
                raise ProofError("TG approval rebound execution context")
            execution_pdr = approved.get("execution_pdr_id")
            effect = approved.get("result") or {}
            if (
                not isinstance(execution_pdr, str)
                or not execution_pdr.startswith("pdr_")
                or effect.get("schema") != "study015.governed-git-effect/1.0"
                or effect.get("execution_context_id") != ctx_id
                or effect.get("action_id") != ACTION
                or effect.get("effect_id") != EFFECT
                or effect.get("causal_id") != CAUSAL
                or effect.get("new_sha") != proof_sha_b
            ):
                raise ProofError("TG governed effect receipt lost causal binding")

            observed = pr_head = None
            for _ in range(16):
                observed = github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env)
                pr_head = github_pr_head(TARGET_REPO, TARGET_PR, gh_env)
                if observed == proof_sha_b and pr_head == proof_sha_b:
                    break
                time.sleep(0.25)
            if observed != proof_sha_b or pr_head != proof_sha_b:
                raise ProofError("remote exact SHA readback did not observe SHA B")

            # L5 durability boundary: crash both real process carriers AFTER the
            # governed effect is externally visible but BEFORE independent
            # verification / subject binding / MissionAcceptance.
            # Simulate an abrupt carrier failure. SIGKILL prevents either
            # process from performing application-level graceful shutdown work.
            tg_proc.kill()
            tg_proc.wait(timeout=5)
            tg_proc = None
            works_proc.kill()
            works_proc.wait(timeout=5)

            if github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != proof_sha_b:
                raise ProofError("remote effect changed during process crash")

            works_resume_ready = root / "works-resume-ready.json"
            if works_resume_ready.exists():
                works_resume_ready.unlink()
            works_proc = subprocess.Popen(
                [
                    str(works_bin), "--addr", "127.0.0.1:0",
                    "--db", str(works_db), "--fixture-out", str(works_resume_ready),
                    "--resume-fixture", str(works_ready),
                ],
                cwd=works_root,
                env=child_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            resumed_works = wait_json(works_resume_ready, works_proc)
            if resumed_works.get("recovered") is not True:
                raise ProofError("WORKS restart did not enter durable recovery mode")
            if resumed_works.get("work_id") != work_id:
                raise ProofError("WORKS restart rebound work identity")
            if resumed_works.get("worker_lease_id") != lease_id:
                raise ProofError("WORKS restart rebound WorkerLease identity")
            if Path(resumed_works.get("db_path", "")).resolve() != works_db.resolve():
                raise ProofError("WORKS restart opened another durable database")
            works_url = resumed_works["base_url"]
            runtime_env["WORKS_BASE_URL"] = works_url

            # Replay the exact same Runtime dispatch after restart. WORKS must
            # return the durable acceptance winner rather than minting a new
            # execution/context/trace identity.
            replayed = json.loads(run(
                ["node", str(runtime_dispatch)],
                env=runtime_env,
                input_text=json.dumps(dispatch_request),
            ).stdout)
            if replayed.get("ok") is not True:
                raise ProofError("Runtime dispatch replay failed after WORKS restart")
            replay_receipt = replayed["receipt"]
            for field in (
                "runtimeDispatchId",
                "worksExecutionId",
                "workId",
                "executionContextId",
                "traceId",
                "workerId",
            ):
                if replay_receipt.get(field) != runtime_receipt.get(field):
                    raise ProofError(f"durable dispatch replay rebound {field}")

            # Independently resolve the execution context from durable WORKS
            # state; this cannot be satisfied from orchestrator memory.
            ctx_status, recovered_context = http_json(
                "GET",
                works_url + "/v1/execution-contexts/" + quote(ctx_id, safe=""),
            )
            if ctx_status != 200:
                raise ProofError("durable execution context unavailable after restart")
            expected_context = {
                "execution_context_id": ctx_id,
                "organization_id": ORG,
                "tenant_id": TENANT,
                "principal_id": PRINCIPAL,
                "mission_id": MISSION,
                "authority_lease_id": AUTH,
                "work_id": work_id,
                "worker_lease_id": lease_id,
                "admission_decision_id": ADMISSION,
                "trace_id": runtime_receipt["traceId"],
            }
            for key, value in expected_context.items():
                if recovered_context.get(key) != value:
                    raise ProofError(f"durable execution context rebound {key}")

            tg_resume_ready = root / "tg-resume-ready.json"
            if tg_resume_ready.exists():
                tg_resume_ready.unlink()
            tg_env["WORKS_API_URL"] = works_url
            tg_env["STUDY015_TG_READY_OUT"] = str(tg_resume_ready)
            tg_proc = subprocess.Popen(
                ["node", "bin/study015-live-gateway.js"],
                cwd=tg_root,
                env=tg_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            resumed_tg = wait_json(tg_resume_ready, tg_proc)
            if resumed_tg.get("mission_id") != MISSION:
                raise ProofError("TG restart rebound mission identity")
            if resumed_tg.get("authority_lease_id") != AUTH:
                raise ProofError("TG restart rebound authority identity")
            if resumed_tg.get("repository") != TARGET_REPO or resumed_tg.get("ref") != TARGET_REF:
                raise ProofError("TG restart rebound governed effect target")
            if Path(resumed_tg.get("audit_file", "")).resolve() != Path(tg_audit_file).resolve():
                raise ProofError("TG restart opened another audit chain")
            tg_url = resumed_tg["base_url"]

            if github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != proof_sha_b:
                raise ProofError("restart caused duplicate or divergent remote effect")

            audit_status, audit_body = http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=500", token=operator_token,
            )
            if audit_status != 200 or not isinstance(audit_body, dict):
                raise ProofError("TG audit unavailable after restart")
            audit_entries = audit_body.get("entries")
            if not isinstance(audit_entries, list):
                raise ProofError("TG audit response missing entries")
            effect_completions = [
                entry for entry in audit_entries
                if isinstance(entry, dict)
                and isinstance(entry.get("payload"), dict)
                and entry["payload"].get("type") == "git_egress_completed"
                and entry["payload"].get("actionId") == ACTION
                and entry["payload"].get("effectId") == EFFECT
                and entry["payload"].get("executionContextId") == ctx_id
            ]
            if len(effect_completions) != 1:
                raise ProofError(
                    f"expected exactly one persisted L5 git_egress_completed entry, got {len(effect_completions)}"
                )
            if int(effect_completions[0]["payload"].get("status") or 0) < 200 or int(
                effect_completions[0]["payload"].get("status") or 0
            ) >= 300:
                raise ProofError("persisted L5 git egress completion is not successful")

            verify_status, verify_body = http_json(
                "GET", tg_url + "/v1/audit/verify", token=operator_token,
            )
            if verify_status != 200 or not isinstance(verify_body, dict) or verify_body.get("ok") is not True:
                raise ProofError("TG audit chain failed verification after restart")

            # Re-enter the same TG action after restart. The V2.1 authorization
            # path must re-read WORKS context and revalidate AIE authority, but
            # we deliberately do NOT approve this second destructive request:
            # no duplicate remote effect may occur.
            pre_revalidation_egress = len(effect_completions)
            reval_status, reval_proposed = http_json(
                "POST", tg_url + "/v1/actions",
                token=worker_token, body=action_body,
            )
            if reval_status != 202 or reval_proposed.get("decision") != "needs_approval":
                raise ProofError("post-restart TG/AIE revalidation did not reach approval boundary")
            if github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != proof_sha_b:
                raise ProofError("post-restart revalidation changed remote effect")
            _, reval_audit = http_json(
                "GET", tg_url + "/v1/audit?since=0&limit=500", token=operator_token,
            )
            reval_entries = reval_audit.get("entries", []) if isinstance(reval_audit, dict) else []
            post_revalidation_egress = sum(
                1 for entry in reval_entries
                if isinstance(entry, dict)
                and isinstance(entry.get("payload"), dict)
                and entry["payload"].get("type") == "git_egress_completed"
                and entry["payload"].get("actionId") == ACTION
                and entry["payload"].get("effectId") == EFFECT
                and entry["payload"].get("executionContextId") == ctx_id
            )
            if post_revalidation_egress != pre_revalidation_egress:
                raise ProofError("post-restart authority revalidation duplicated Git effect")

            sentinel = sentinel_review(sentinel_root, gh_env)
            if sentinel.get("review", {}).get("headSha") != proof_sha_b:
                raise ProofError("Sentinel reviewed another head")
            if sentinel.get("verdict", {}).get("decision") != "SHIP":
                raise ProofError("Sentinel did not SHIP exact proof head")
            sentinel_receipt = sentinel.get("receipt", {}).get("receipt_id")
            if not isinstance(sentinel_receipt, str) or len(sentinel_receipt) != 64:
                raise ProofError("Sentinel receipt ID malformed")

            subject = f"git:{TARGET_REPO}@{proof_sha_b}"
            bind_request = {
                "workId": work_id,
                "worksExecutionId": works_execution_id,
                "attemptId": ATTEMPT,
                "effectId": EFFECT,
                "causalId": CAUSAL,
                "subject": subject,
            }
            bound = json.loads(run(
                ["node", str(runtime_bind)],
                env=runtime_env,
                input_text=json.dumps(bind_request),
            ).stdout)
            if bound.get("ok") is not True or bound.get("receipt", {}).get("subject") != subject:
                raise ProofError("Runtime/WORKS subject binding failed")

            acceptance_body = {
                "schema": "dispatch.mission-acceptance/1.0",
                "execution_context_id": ctx_id,
                "execution_pdr_id": execution_pdr,
                "verifier_id": "sentinel:exact-head",
                "sentinel_head_sha": proof_sha_b,
                "sentinel_verdict": "SHIP",
                "sentinel_receipt_id": sentinel_receipt,
            }
            accept_url = (
                works_url + "/v2/works/" + quote(work_id, safe="")
                + "/acceptances/" + quote(works_execution_id, safe="")
                + "/mission-acceptance"
            )
            status, accepted = http_json(
                "POST", accept_url,
                token=works_token,
                body=acceptance_body,
                headers={
                    "X-Works-Platform-Bridge": bridge_secret,
                    "X-WORKS-Verifier-Token": verifier_token,
                },
            )
            if (
                status != 200
                or accepted.get("verified") is not True
                or accepted.get("outcome") != "SUCCEEDED"
                or accepted.get("execution_context_id") != ctx_id
                or accepted.get("execution_pdr_id") != execution_pdr
                or accepted.get("verification_subject") != subject
            ):
                raise ProofError("WORKS MissionAcceptance did not commit Verified Outcome")

            # A retry of the exact acceptance after recovery must be idempotent.
            retry_status, accepted_retry = http_json(
                "POST", accept_url,
                token=works_token,
                body=acceptance_body,
                headers={
                    "X-Works-Platform-Bridge": bridge_secret,
                    "X-WORKS-Verifier-Token": verifier_token,
                },
            )
            if retry_status != 200:
                raise ProofError("MissionAcceptance retry was not idempotent")
            for key in (
                "verified",
                "outcome",
                "execution_context_id",
                "execution_pdr_id",
                "verification_subject",
            ):
                if accepted_retry.get(key) != accepted.get(key):
                    raise ProofError(f"MissionAcceptance retry rebound {key}")

            # Hostile owner-level acceptance checks.
            wrong = dict(acceptance_body)
            wrong["execution_pdr_id"] = "pdr_" + "9" * 32
            wrong_status, _ = http_json(
                "POST", accept_url, token=works_token, body=wrong,
                headers={
                    "X-Works-Platform-Bridge": bridge_secret,
                    "X-WORKS-Verifier-Token": verifier_token,
                },
            )
            stale = dict(acceptance_body)
            stale["sentinel_head_sha"] = proof_sha_a
            stale_status, _ = http_json(
                "POST", accept_url, token=works_token, body=stale,
                headers={
                    "X-Works-Platform-Bridge": bridge_secret,
                    "X-WORKS-Verifier-Token": verifier_token,
                },
            )
            if wrong_status != 409 or stale_status != 409:
                raise ProofError("MissionAcceptance hostile seam did not fail closed")

            prior_l4_context = "ctx_243e1bc1627b3ce8167df39c791e3f6e"
            old_identity = dict(acceptance_body)
            old_identity["execution_context_id"] = prior_l4_context
            old_identity_status, _ = http_json(
                "POST", accept_url, token=works_token, body=old_identity,
                headers={
                    "X-Works-Platform-Bridge": bridge_secret,
                    "X-WORKS-Verifier-Token": verifier_token,
                },
            )
            if old_identity_status != 409:
                raise ProofError("L4 execution context replay bound into L5 acceptance")

            # Revoke the live AIE lease, then replay the exact admitted action.
            # It must fail before the governed Git executor/transport runs.
            revoke_aie(aie_root, aie_state, os.environ.copy())
            _, before_audit = http_json("GET", tg_url + "/v1/audit", token=worker_token)
            before_egress = sum(
                1 for e in before_audit.get("entries", [])
                if e.get("payload", {}).get("type") == "git_egress_completed"
            )
            status, proposed2 = http_json(
                "POST", tg_url + "/v1/actions", token=worker_token, body=action_body
            )
            if status != 202:
                raise ProofError("revocation replay did not reach approval boundary")
            status, rejected = http_json(
                "POST",
                tg_url + f"/v1/approvals/{quote(proposed2['approvalId'])}/approve",
                token=operator_token,
                body={},
            )
            if status != 403 or rejected.get("error") != "authority_revoked":
                raise ProofError("revoked authority did not fail closed at TG/AIE")
            _, after_audit = http_json("GET", tg_url + "/v1/audit", token=worker_token)
            after_egress = sum(
                1 for e in after_audit.get("entries", [])
                if e.get("payload", {}).get("type") == "git_egress_completed"
            )
            if after_egress != before_egress:
                raise ProofError("revoked action reached Git egress")

            if github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) != proof_sha_b:
                raise ProofError("revoked action changed remote proof ref")

            receipt = {
                "schema": "study015.l5-durable-recovery/1.0",
                "execution_class": "LIVE_INTEGRATION_CONFORMANCE",
                "evidence_class": "L5_DURABLE_CAUSAL_RECOVERY_CANDIDATE",
                "performance_claim": False,
                "g15_9_authorized": False,
                "production_deployment": False,
                "network_used": True,
                "heads": expected,
                "proof_target": {
                    "repository": TARGET_REPO,
                    "pull_request": TARGET_PR,
                    "branch": TARGET_BRANCH,
                    "sha_a": proof_sha_a,
                    "sha_b": proof_sha_b,
                    "remote_readback": proof_sha_b,
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
                    "exact_subject": subject,
                    "sentinel_receipt_id": sentinel_receipt,
                },
                "seams": {
                    "works_process_http": True,
                    "runtime_process_cli": True,
                    "tg_process_http": True,
                    "aie_revalidation_subprocess": True,
                    "human_approval_boundary": True,
                    "governed_remote_git_effect": True,
                    "remote_exact_sha_readback": True,
                    "sentinel_process_exact_head": True,
                    "runtime_works_subject_binding": True,
                    "works_mission_acceptance": True,
                    "durable_verified_outcome": True,
                },
                "hostile": {
                    "wrong_pdr_rejected": True,
                    "stale_verification_head_rejected": True,
                    "prior_l4_execution_context_rejected": True,
                    "revoked_authority_rejected_before_egress": True,
                },
                "durability": {
                    "prior_l4_causal_slice_sha256": "3ae010a18e036d7978b06f85c783b21be724776ce9c2947fee93813d17d47e4c",
                    "prior_l4_execution_context_id": "ctx_243e1bc1627b3ce8167df39c791e3f6e",
                    "works_process_restarted_after_sigkill": resumed_works.get("recovered") is True,
                    "trust_gateway_process_restarted_after_sigkill": True,
                    "same_work_id_after_restart": resumed_works.get("work_id") == work_id,
                    "same_worker_lease_after_restart": resumed_works.get("worker_lease_id") == lease_id,
                    "same_works_db_after_restart": Path(resumed_works.get("db_path", "")).resolve() == works_db.resolve(),
                    "same_runtime_dispatch_after_restart": replay_receipt.get("runtimeDispatchId") == runtime_receipt.get("runtimeDispatchId"),
                    "same_works_execution_after_restart": replay_receipt.get("worksExecutionId") == works_execution_id,
                    "same_execution_context_after_restart": replay_receipt.get("executionContextId") == ctx_id,
                    "same_trace_after_restart": replay_receipt.get("traceId") == runtime_receipt.get("traceId"),
                    "durable_execution_context_readback": recovered_context.get("execution_context_id") == ctx_id,
                    "same_mission_after_tg_restart": resumed_tg.get("mission_id") == MISSION,
                    "same_authority_after_tg_restart": resumed_tg.get("authority_lease_id") == AUTH,
                    "same_tg_audit_file_after_restart": Path(resumed_tg.get("audit_file", "")).resolve() == Path(tg_audit_file).resolve(),
                    "post_restart_authority_revalidated_without_effect": reval_status == 202 and post_revalidation_egress == pre_revalidation_egress,
                    "same_remote_effect_after_restart": github_ref_sha(TARGET_REPO, TARGET_BRANCH, gh_env) == proof_sha_b,
                    "single_persisted_git_egress_completion": len(effect_completions) == 1,
                    "tg_audit_chain_verified_after_restart": verify_body.get("ok") is True,
                    "mission_acceptance_retry_idempotent": retry_status == 200 and accepted_retry == accepted,
                    "fresh_exact_subject": subject != "git:Aftergraph/runtime@92cc08482d91d70140db4916f1a11fc43b6318f6",
                    "fresh_execution_context": ctx_id != "ctx_243e1bc1627b3ce8167df39c791e3f6e",
                },
            }
            if not all(
                type(value) is bool and value is True
                for key, value in receipt["durability"].items()
                if not key.startswith("prior_l4_")
            ):
                raise ProofError("L5 durable recovery invariant failed")
            canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt["causal_slice_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
            print(json.dumps(receipt, sort_keys=True))
            return 0
        finally:
            if tg_proc is not None and tg_proc.poll() is None:
                tg_proc.terminate()
                try:
                    tg_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tg_proc.kill()
            if works_proc.poll() is None:
                works_proc.terminate()
                try:
                    works_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    works_proc.kill()
            try:
                patch_ref(TARGET_REPO, TARGET_BRANCH, proof_sha_b, gh_env)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
