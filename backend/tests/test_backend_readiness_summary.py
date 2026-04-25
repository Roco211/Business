from __future__ import annotations

from pathlib import Path


def test_backend_readiness_summary_reports_ready_when_required_artifacts_exist(tmp_path):
    from app.devtools.backend_readiness_summary import build_backend_readiness_summary

    required_files = [
        "backend/scripts/run_backend_preflight.sh",
        "backend/scripts/run_docker_backend_acceptance.sh",
        "backend/scripts/run_provider_trial_preflight.py",
        ".github/workflows/backend-preflight.yml",
        "backend/tests/test_v2_inventory_item_audit_http_flow.py",
        "backend/tests/test_v2_inventory_item_crud_http_flow.py",
        "backend/tests/test_provider_trial_preflight.py",
        "backend/tests/test_v2_pc_dashboard_overview_http_flow.py",
        "backend/tests/test_v2_sales_orders_http_flow.py",
        "backend/tests/test_v2_commercial_modules_http_flow.py",
        "apps/h5/package.json",
        "infra/docker/docker-compose.production.yml",
        "backend/tests/test_production_readiness_config.py",
        "backend/scripts/backup_postgres.sh",
        "backend/scripts/restore_postgres.sh",
        "backend/scripts/run_production_trial_rehearsal.sh",
        "backend/scripts/run_lightweight_stability_check.py",
        "docs/superpowers/guides/2026-04-25-production-trial-runbook.md",
    ]
    for relative_path in required_files:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")

    summary = build_backend_readiness_summary(repo_root=tmp_path).to_dict()

    assert summary["overall_status"] == "ready"
    assert summary["ready_count"] == len(required_files)
    assert summary["missing_count"] == 0
    assert all(check["status"] == "ready" for check in summary["checks"])


def test_backend_readiness_summary_reports_degraded_with_missing_artifacts(tmp_path):
    from app.devtools.backend_readiness_summary import build_backend_readiness_summary

    (tmp_path / "backend/scripts").mkdir(parents=True)
    (tmp_path / "backend/scripts/run_backend_preflight.sh").write_text("ok", encoding="utf-8")

    summary = build_backend_readiness_summary(repo_root=tmp_path).to_dict()

    assert summary["overall_status"] == "degraded"
    assert summary["ready_count"] == 1
    assert summary["missing_count"] > 0
    missing_paths = {check["path"] for check in summary["checks"] if check["status"] == "missing"}
    assert "backend/scripts/run_provider_trial_preflight.py" in missing_paths
