from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

READY_STATUS = "ready"
DEGRADED_STATUS = "degraded"


@dataclass(frozen=True)
class BackendReadinessCheck:
    name: str
    path: str
    status: str


@dataclass(frozen=True)
class BackendReadinessSummary:
    overall_status: str
    ready_count: int
    missing_count: int
    checks: list[BackendReadinessCheck]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


REQUIRED_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("backend_preflight_script", "backend/scripts/run_backend_preflight.sh"),
    ("docker_acceptance_script", "backend/scripts/run_docker_backend_acceptance.sh"),
    ("provider_trial_preflight_script", "backend/scripts/run_provider_trial_preflight.py"),
    ("github_actions_backend_preflight", ".github/workflows/backend-preflight.yml"),
    ("inventory_item_audit_regression", "backend/tests/test_v2_inventory_item_audit_http_flow.py"),
    ("inventory_item_crud_regression", "backend/tests/test_v2_inventory_item_crud_http_flow.py"),
    ("provider_trial_preflight_regression", "backend/tests/test_provider_trial_preflight.py"),
    ("pc_dashboard_bff_regression", "backend/tests/test_v2_pc_dashboard_overview_http_flow.py"),
    ("pc_h5_frontend_package", "apps/h5/package.json"),
)


def build_backend_readiness_summary(*, repo_root: str | Path) -> BackendReadinessSummary:
    root = Path(repo_root)
    checks: list[BackendReadinessCheck] = []
    for name, relative_path in REQUIRED_ARTIFACTS:
        exists = (root / relative_path).is_file()
        checks.append(
            BackendReadinessCheck(
                name=name,
                path=relative_path,
                status=READY_STATUS if exists else "missing",
            )
        )

    ready_count = sum(1 for check in checks if check.status == READY_STATUS)
    missing_count = len(checks) - ready_count
    return BackendReadinessSummary(
        overall_status=READY_STATUS if missing_count == 0 else DEGRADED_STATUS,
        ready_count=ready_count,
        missing_count=missing_count,
        checks=checks,
    )
