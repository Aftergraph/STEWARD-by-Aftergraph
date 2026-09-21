"""Secret-safe readiness gate for a live STEWARD P2 Golden Mission run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import shutil
from typing import Mapping, Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ready: bool
    reason: str


@dataclass(frozen=True)
class LiveReadinessReport:
    schema: str
    state: str
    checks: tuple[ReadinessCheck, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": self.schema,
                "state": self.state,
                "checks": [asdict(check) for check in self.checks],
            },
            indent=2,
            sort_keys=True,
        )


def _command_check(name: str, value: str | None) -> ReadinessCheck:
    if value is None or not value.strip():
        return ReadinessCheck(name, False, "binding_missing")
    executable = value.strip().split()[0]
    if shutil.which(executable) is None:
        return ReadinessCheck(name, False, "executable_not_found")
    return ReadinessCheck(name, True, "executable_resolved")


def _url_check(name: str, value: str | None) -> ReadinessCheck:
    if value is None or not value.strip():
        return ReadinessCheck(name, False, "binding_missing")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ReadinessCheck(name, False, "invalid_http_url")
    return ReadinessCheck(name, True, "endpoint_configured")


def _secret_check(name: str, value: str | None) -> ReadinessCheck:
    # Never return, hash or log secret material. Readiness only records presence.
    return ReadinessCheck(
        name,
        bool(value),
        "secret_present" if value else "binding_missing",
    )


def inspect_live_readiness(
    environment: Mapping[str, str] | None = None,
) -> LiveReadinessReport:
    env = os.environ if environment is None else environment
    checks = (
        _command_check("runtime_command", env.get("STEWARD_RUNTIME_COMMAND")),
        _url_check("trust_gateway_url", env.get("STEWARD_TRUST_GATEWAY_URL")),
        _secret_check("trust_gateway_token", env.get("STEWARD_TRUST_GATEWAY_TOKEN")),
        _command_check("habitat_command", env.get("STEWARD_HABITAT_COMMAND")),
        _command_check("sentinel_command", env.get("STEWARD_SENTINEL_COMMAND")),
    )
    state = "READY" if all(check.ready for check in checks) else "BLOCKED"
    return LiveReadinessReport(
        schema="steward.p2.live-readiness/0.1",
        state=state,
        checks=checks,
    )


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    report = inspect_live_readiness()
    print(report.to_json())
    return 0 if report.state == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
