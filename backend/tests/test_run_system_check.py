from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _load_system_check_script_module():
    try:
        return importlib.import_module("scripts.run_system_check")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.run_system_check module is missing: {exc}")


def _load_trial_readiness_module():
    try:
        return importlib.import_module("app.devtools.trial_readiness")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.trial_readiness module is missing: {exc}")


def _load_local_demo_smoke_module():
    try:
        return importlib.import_module("app.devtools.local_demo_smoke")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.local_demo_smoke module is missing: {exc}")


def _write_bundle_artifacts(
    *,
    root_dir: Path,
    readiness_payload: dict[str, object],
    preflight_payload: dict[str, object],
    pilot_summary_payload: dict[str, object],
) -> Path:
    root_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "readiness.json").write_text(json.dumps(readiness_payload), encoding="utf-8")
    (root_dir / "preflight.json").write_text(json.dumps(preflight_payload), encoding="utf-8")
    (root_dir / "pilot_summary.json").write_text(json.dumps(pilot_summary_payload), encoding="utf-8")
    manifest_path = root_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "artifacts": {
                    "readiness": {"file": "readiness.json"},
                    "preflight": {"file": "preflight.json"},
                    "pilot_summary": {"file": "pilot_summary.json"},
                }
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_run_system_check_cli_prints_compact_json_and_exits_zero_for_local_demo_mode(capsys, monkeypatch) -> None:
    script_module = _load_system_check_script_module()
    local_demo_module = _load_local_demo_smoke_module()
    calls: list[dict[str, object]] = []
    result = local_demo_module.LocalDemoSmokeResult(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        shop_id="shop_default",
        session_id="sess_default",
        inventory_item_count=3,
        pending_confirmation_count=2,
        open_low_stock_alert_count=1,
        message_count=10,
        replay_event_count=34,
        latest_replay_seq=34,
    )

    def _fake_run_local_demo_smoke(**kwargs: object):
        calls.append(dict(kwargs))
        return result

    monkeypatch.setattr(script_module, "run_local_demo_smoke", _fake_run_local_demo_smoke)

    exit_code = script_module.main(["--mode", "local-demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "mode": "local-demo",
        "overall_status": "ready",
        "checks": {
            "local_demo": result.to_dict(),
        },
    }
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert calls == [
        {
            "api_base_url": "http://127.0.0.1:8001",
            "auth_token": None,
            "login_email": "owner@example.com",
            "login_password": "dev-password",
        }
    ]


def test_run_system_check_cli_returns_non_zero_when_trial_readiness_is_degraded(capsys, monkeypatch) -> None:
    script_module = _load_system_check_script_module()
    trial_module = _load_trial_readiness_module()
    calls: list[dict[str, object]] = []
    summary = trial_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="local-demo",
        readiness_status="ready",
        overall_status="degraded",
        object_storage={"status": "ready", "mode": "mock"},
        providers={
            "asr": {"status": "ready", "mode": "mock"},
            "ocr": {"status": "ready", "mode": "mock"},
            "vision": {"status": "ready", "mode": "mock"},
        },
    )

    def _fake_run_trial_readiness(**kwargs: object):
        calls.append(dict(kwargs))
        return summary

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)

    exit_code = script_module.main(["--mode", "trial", "--auth-token", "seed-token"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {
        "mode": "trial",
        "overall_status": "degraded",
        "checks": {
            "trial_readiness": summary.to_dict(),
        },
    }
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert calls == [
        {
            "api_base_url": "http://127.0.0.1:8001",
            "auth_token": "seed-token",
            "login_email": "owner@example.com",
            "login_password": "dev-password",
        }
    ]


def test_run_system_check_cli_prints_compact_json_and_exits_zero_for_pilot_mode(
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    script_module = _load_system_check_script_module()
    bundle_dir = tmp_path / "pilot-ready-bundle"
    calls: list[dict[str, object]] = []
    readiness_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "health_status": "ok",
        "runtime_mode": "trial",
        "readiness_status": "ready",
        "overall_status": "ready",
        "object_storage": {"status": "ready", "mode": "s3-compatible"},
        "providers": {
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    }
    preflight_payload = {
        "overall_status": "ready",
        "runtime_mode": "trial",
        "trial_provider_profile": "pilot-v1",
        "cutover_mode": "shadow",
        "approved_calibration_artifact_id": "artifact_20260407",
        "reasons": [],
    }
    pilot_summary_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "hours": 24,
        "overall_status": "ready",
        "pilot_summary": {
            "overall_status": "ready",
            "reasons": [],
            "trial_provider_profile": "pilot-v1",
        },
        "readiness": readiness_payload,
        "thresholds": {"max_fallback_rate": 0.05, "max_low_confidence_rate": 0.2},
    }
    manifest_path = _write_bundle_artifacts(
        root_dir=bundle_dir,
        readiness_payload=readiness_payload,
        preflight_payload=preflight_payload,
        pilot_summary_payload=pilot_summary_payload,
    )
    bundle_result = {
        "bundle_id": "shift_bundle_20260407T090000000000Z",
        "manifest_path": str(manifest_path),
        "overall_status": "ready",
        "degraded_reasons": [],
    }

    def _fake_export_pilot_shift_bundle(**kwargs: object):
        calls.append(dict(kwargs))
        return bundle_result

    monkeypatch.setattr(script_module, "export_pilot_shift_bundle", _fake_export_pilot_shift_bundle)

    exit_code = script_module.main(
        [
            "--mode",
            "pilot",
            "--auth-token",
            "seed-token",
            "--hours",
            "24",
            "--output-dir",
            "C:/secure/pilot/shift-bundles",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "mode": "pilot",
        "overall_status": "ready",
        "reasons": [],
        "checks": {
            "trial_readiness": readiness_payload,
            "live_pilot_preflight": preflight_payload,
            "pilot_summary": pilot_summary_payload,
            "shift_bundle": bundle_result,
        },
    }
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert calls == [
        {
            "api_base_url": "http://127.0.0.1:8001",
            "output_dir": "C:/secure/pilot/shift-bundles",
            "auth_token": "seed-token",
            "login_email": "owner@example.com",
            "login_password": "dev-password",
            "hours": 24,
            "max_fallback_rate": 0.05,
            "max_low_confidence_rate": 0.2,
        }
    ]


def test_run_system_check_cli_returns_non_zero_when_pilot_bundle_is_degraded(
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    script_module = _load_system_check_script_module()
    bundle_dir = tmp_path / "pilot-degraded-bundle"
    readiness_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "health_status": "ok",
        "runtime_mode": "trial",
        "readiness_status": "degraded",
        "overall_status": "degraded",
        "object_storage": {"status": "ready", "mode": "s3-compatible"},
        "providers": {
            "asr": {"status": "degraded", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    }
    preflight_payload = {
        "overall_status": "degraded",
        "runtime_mode": "trial",
        "trial_provider_profile": "pilot-v1",
        "cutover_mode": "shadow",
        "approved_calibration_artifact_id": "artifact_20260407",
        "reasons": ["artifact_profile_mismatch"],
    }
    pilot_summary_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "hours": 24,
        "overall_status": "degraded",
        "pilot_summary": {
            "overall_status": "degraded",
            "reasons": ["provider_failures_present"],
            "trial_provider_profile": "pilot-v1",
        },
        "readiness": readiness_payload,
        "thresholds": {"max_fallback_rate": 0.05, "max_low_confidence_rate": 0.2},
    }
    manifest_path = _write_bundle_artifacts(
        root_dir=bundle_dir,
        readiness_payload=readiness_payload,
        preflight_payload=preflight_payload,
        pilot_summary_payload=pilot_summary_payload,
    )

    monkeypatch.setattr(
        script_module,
        "export_pilot_shift_bundle",
        lambda **_: {
            "bundle_id": "shift_bundle_20260407T090000000000Z",
            "manifest_path": str(manifest_path),
            "overall_status": "degraded",
            "degraded_reasons": [
                "readiness_not_ready",
                "artifact_profile_mismatch",
                "provider_failures_present",
            ],
        },
    )

    exit_code = script_module.main(["--mode", "pilot"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {
        "mode": "pilot",
        "overall_status": "degraded",
        "reasons": [
            "readiness_not_ready",
            "artifact_profile_mismatch",
            "provider_failures_present",
        ],
        "checks": {
            "trial_readiness": readiness_payload,
            "live_pilot_preflight": preflight_payload,
            "pilot_summary": pilot_summary_payload,
            "shift_bundle": {
                "bundle_id": "shift_bundle_20260407T090000000000Z",
                "manifest_path": str(manifest_path),
                "overall_status": "degraded",
                "degraded_reasons": [
                    "readiness_not_ready",
                    "artifact_profile_mismatch",
                    "provider_failures_present",
                ],
            },
        },
    }
    assert captured.err == ""


def test_run_system_check_cli_reports_leaf_error_and_exits_non_zero(capsys, monkeypatch) -> None:
    script_module = _load_system_check_script_module()

    def _raise_error(**_: object):
        raise script_module.LocalDemoSmokeError("demo smoke failed")

    monkeypatch.setattr(script_module, "run_local_demo_smoke", _raise_error)

    exit_code = script_module.main(["--mode", "local-demo"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "System check failed" in captured.err
    assert "demo smoke failed" in captured.err
