"""Fail-closed P2 production-binding readiness projection.

STEWARD owns composition only. This module does not deploy or authorize any
owner. It consumes secret-free observations emitted by the canonical owner
deployment paths and answers one question: is there enough exact-state evidence
to *attempt* a production Golden Mission?

A green report is deployment readiness evidence, not execution authority and not
MissionAcceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_OWNERS = ("runtime", "works", "trust_gateway", "aie", "sentinel")
_SECRET_KEY_RE = re.compile(r"(?:token|secret|password|credential|private[_-]?key|api[_-]?key)", re.I)


class ProductionBindingContractError(RuntimeError):
    """The observation is malformed or attempts to carry secret material."""


@dataclass(frozen=True)
class OwnerDeploymentObservation:
    owner: str
    repository: str
    expected_sha: str
    observed_sha: str
    mode: str
    active: bool
    deployment_evidence_ref: str
    health_or_invocation_evidence_ref: str

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "OwnerDeploymentObservation":
        allowed = {
            "owner",
            "repository",
            "expected_sha",
            "observed_sha",
            "mode",
            "active",
            "deployment_evidence_ref",
            "health_or_invocation_evidence_ref",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ProductionBindingContractError(
                f"unknown owner deployment fields: {sorted(unknown)}"
            )
        owner = payload.get("owner")
        repository = payload.get("repository")
        expected_sha = payload.get("expected_sha")
        observed_sha = payload.get("observed_sha")
        mode = payload.get("mode")
        active = payload.get("active")
        deploy_ref = payload.get("deployment_evidence_ref")
        health_ref = payload.get("health_or_invocation_evidence_ref")

        if owner not in _REQUIRED_OWNERS:
            raise ProductionBindingContractError("unknown canonical owner")
        if not isinstance(repository, str) or not repository.startswith("Aftergraph/"):
            raise ProductionBindingContractError("repository must be canonical Aftergraph owner")
        if not isinstance(expected_sha, str) or not _SHA_RE.fullmatch(expected_sha):
            raise ProductionBindingContractError("expected_sha must be exact 40-hex")
        if not isinstance(observed_sha, str) or not _SHA_RE.fullmatch(observed_sha):
            raise ProductionBindingContractError("observed_sha must be exact 40-hex")
        if mode not in {"service", "module", "cli"}:
            raise ProductionBindingContractError("mode must be service, module, or cli")
        if active is not True and active is not False:
            raise ProductionBindingContractError("active must be boolean")
        if not isinstance(deploy_ref, str) or not deploy_ref.strip():
            raise ProductionBindingContractError("deployment_evidence_ref is required")
        if not isinstance(health_ref, str) or not health_ref.strip():
            raise ProductionBindingContractError(
                "health_or_invocation_evidence_ref is required"
            )
        return cls(
            owner=owner,
            repository=repository,
            expected_sha=expected_sha,
            observed_sha=observed_sha,
            mode=mode,
            active=active,
            deployment_evidence_ref=deploy_ref,
            health_or_invocation_evidence_ref=health_ref,
        )


@dataclass(frozen=True)
class ProductionBindingObservation:
    schema: str
    execution_plane: str
    environment: str
    owners: tuple[OwnerDeploymentObservation, ...]
    works_durable_state: bool
    tg_adapter_runtime_enabled: bool
    aie_action_time_revalidation_live: bool
    scoped_credential_surrogation_live: bool
    remote_git_readback_live: bool
    independent_sentinel_live: bool

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "ProductionBindingObservation":
        _reject_secret_keys(payload)
        allowed = {
            "schema",
            "execution_plane",
            "environment",
            "owners",
            "works_durable_state",
            "tg_adapter_runtime_enabled",
            "aie_action_time_revalidation_live",
            "scoped_credential_surrogation_live",
            "remote_git_readback_live",
            "independent_sentinel_live",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ProductionBindingContractError(
                f"unknown production binding fields: {sorted(unknown)}"
            )
        if payload.get("schema") != "steward.p2.production-binding/0.1":
            raise ProductionBindingContractError("unsupported production binding schema")
        if payload.get("environment") != "production":
            raise ProductionBindingContractError("environment must be production")
        plane = payload.get("execution_plane")
        if not isinstance(plane, str) or not plane.strip():
            raise ProductionBindingContractError("execution_plane is required")
        raw_owners = payload.get("owners")
        if not isinstance(raw_owners, list):
            raise ProductionBindingContractError("owners must be a list")
        owners = tuple(
            OwnerDeploymentObservation.from_wire(item)
            for item in raw_owners
            if isinstance(item, Mapping)
        )
        if len(owners) != len(raw_owners):
            raise ProductionBindingContractError("each owner observation must be an object")

        bool_fields = (
            "works_durable_state",
            "tg_adapter_runtime_enabled",
            "aie_action_time_revalidation_live",
            "scoped_credential_surrogation_live",
            "remote_git_readback_live",
            "independent_sentinel_live",
        )
        for field in bool_fields:
            if payload.get(field) is not True and payload.get(field) is not False:
                raise ProductionBindingContractError(f"{field} must be boolean")

        return cls(
            schema=payload["schema"],
            execution_plane=plane,
            environment="production",
            owners=owners,
            works_durable_state=payload["works_durable_state"],
            tg_adapter_runtime_enabled=payload["tg_adapter_runtime_enabled"],
            aie_action_time_revalidation_live=payload["aie_action_time_revalidation_live"],
            scoped_credential_surrogation_live=payload["scoped_credential_surrogation_live"],
            remote_git_readback_live=payload["remote_git_readback_live"],
            independent_sentinel_live=payload["independent_sentinel_live"],
        )


@dataclass(frozen=True)
class ProductionBindingReport:
    schema: str
    ready: bool
    execution_plane: str
    blockers: tuple[str, ...]
    exact_owner_heads: Mapping[str, str]

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "ready": self.ready,
            "execution_plane": self.execution_plane,
            "blockers": list(self.blockers),
            "exact_owner_heads": dict(self.exact_owner_heads),
            "authority_granted": False,
            "mission_accepted": False,
        }


def evaluate_production_binding(
    observation: ProductionBindingObservation,
) -> ProductionBindingReport:
    blockers: list[str] = []
    by_owner: dict[str, OwnerDeploymentObservation] = {}
    for owner in observation.owners:
        if owner.owner in by_owner:
            blockers.append(f"duplicate_owner:{owner.owner}")
            continue
        by_owner[owner.owner] = owner

    for name in _REQUIRED_OWNERS:
        item = by_owner.get(name)
        if item is None:
            blockers.append(f"owner_missing:{name}")
            continue
        if item.expected_sha != item.observed_sha:
            blockers.append(f"owner_sha_mismatch:{name}")
        if not item.active:
            blockers.append(f"owner_inactive:{name}")

    cross_plane = {
        "works_durable_state": observation.works_durable_state,
        "tg_adapter_runtime_enabled": observation.tg_adapter_runtime_enabled,
        "aie_action_time_revalidation_live": observation.aie_action_time_revalidation_live,
        "scoped_credential_surrogation_live": observation.scoped_credential_surrogation_live,
        "remote_git_readback_live": observation.remote_git_readback_live,
        "independent_sentinel_live": observation.independent_sentinel_live,
    }
    blockers.extend(
        f"binding_missing:{name}" for name, present in cross_plane.items() if not present
    )

    heads = {
        name: by_owner[name].observed_sha
        for name in _REQUIRED_OWNERS
        if name in by_owner
    }
    return ProductionBindingReport(
        schema="steward.p2.production-binding-report/0.1",
        ready=not blockers,
        execution_plane=observation.execution_plane,
        blockers=tuple(blockers),
        exact_owner_heads=heads,
    )


def load_observation(path: str | Path) -> ProductionBindingObservation:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ProductionBindingContractError("production binding document must be an object")
    return ProductionBindingObservation.from_wire(raw)


def _reject_secret_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                raise ProductionBindingContractError(
                    f"secret-bearing field forbidden at {path}.{key_text}"
                )
            _reject_secret_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_keys(child, f"{path}[{index}]")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            json.dumps(
                {
                    "schema": "steward.p2.production-binding-report/0.1",
                    "ready": False,
                    "blockers": ["usage: python -m steward.p2_production_binding <observation.json>"],
                }
            )
        )
        return 2
    try:
        report = evaluate_production_binding(load_observation(args[0]))
    except (OSError, json.JSONDecodeError, ProductionBindingContractError) as exc:
        print(
            json.dumps(
                {
                    "schema": "steward.p2.production-binding-report/0.1",
                    "ready": False,
                    "blockers": [str(exc)],
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report.to_wire(), sort_keys=True))
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
