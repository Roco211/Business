from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_export_shift_bundle_script_module():
    try:
        return importlib.import_module("scripts.export_pilot_shift_bundle")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.export_pilot_shift_bundle module is missing: {exc}")


@dataclass(frozen=True)
class _Summary:
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


def _build_request_json(*, pilot_control_payload: dict[str, object]):
    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        if path == "/api/v1/auth/login":
            assert method == "POST"
            assert token is None
            assert payload == {"email": "owner@example.com", "password": "dev-password"}
            return 200, {"data": {"access_token": "issued-token"}}
        if path == "/api/v1/system/pilot-control":
            assert method == "GET"
            assert token == "issued-token"
            assert payload is None
            return 200, {"data": pilot_control_payload}
        raise AssertionError(f"Unexpected request path: {path}")

    return request_json


def _fixed_now() -> datetime:
    return datetime(2026, 4, 7, 9, 0, 0, tzinfo=UTC)


def _ready_readiness_payload() -> dict[str, object]:
    return {
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


def _ready_preflight_payload() -> dict[str, object]:
    return {
        "overall_status": "ready",
        "runtime_mode": "trial",
        "trial_provider_profile": "pilot-v1",
        "cutover_mode": "shadow",
        "approved_calibration_artifact_id": "artifact_20260407",
        "reasons": [],
    }


def _ready_pilot_control_payload() -> dict[str, object]:
    return {
        "shop_id": "shop_default",
        "trial_provider_profile": "pilot-v1",
        "approved_calibration_artifact_id": "artifact_20260407",
        "approved_calibration_report_path": "C:/secure/pilot/artifacts/report.json",
        "cutover_mode": "shadow",
        "opened_at": None,
        "opened_by_actor_id": None,
        "closed_at": None,
        "closed_by_actor_id": None,
        "last_preflight_at": "2026-04-07T08:55:00Z",
        "last_preflight_status": "ready",
        "notes": "incident review",
    }


def _ready_pilot_summary_payload(readiness_payload: dict[str, object]) -> dict[str, object]:
    return {
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


def test_export_shift_bundle_collects_outputs_and_writes_compact_manifest(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

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
    pilot_control_payload = {
        "shop_id": "shop_default",
        "trial_provider_profile": "pilot-v1",
        "approved_calibration_artifact_id": "artifact_20260407",
        "approved_calibration_report_path": "C:/secure/pilot/artifacts/report.json",
        "cutover_mode": "shadow",
        "opened_at": None,
        "opened_by_actor_id": None,
        "closed_at": None,
        "closed_by_actor_id": None,
        "last_preflight_at": "2026-04-07T08:55:00Z",
        "last_preflight_status": "ready",
        "notes": "morning observation window",
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

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    output_dir = repo_root / "secure-bundles" / "shift-handoff"
    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(output_dir),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "ready"
    assert result["degraded_reasons"] == []

    manifest_path = Path(str(result["manifest_path"]))
    assert manifest_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["shop_id"] == "shop_default"
    assert manifest_payload["cutover_mode"] == "shadow"
    assert manifest_payload["trial_provider_profile"] == "pilot-v1"
    assert manifest_payload["approved_calibration_artifact_id"] == "artifact_20260407"
    assert manifest_payload["overall_status"] == "ready"
    assert manifest_payload["degraded_reasons"] == []
    assert manifest_payload["hours"] == 24

    bundle_dir = manifest_path.parent
    files_written = sorted(path.name for path in bundle_dir.iterdir())
    assert all(file_name.endswith(".json") for file_name in files_written)

    expected_keys = {"readiness", "preflight", "pilot_control", "pilot_summary"}
    assert set(manifest_payload["artifacts"]) == expected_keys

    readiness_artifact = bundle_dir / manifest_payload["artifacts"]["readiness"]["file"]
    assert json.loads(readiness_artifact.read_text(encoding="utf-8")) == readiness_payload
    preflight_artifact = bundle_dir / manifest_payload["artifacts"]["preflight"]["file"]
    assert json.loads(preflight_artifact.read_text(encoding="utf-8")) == preflight_payload
    pilot_control_artifact = bundle_dir / manifest_payload["artifacts"]["pilot_control"]["file"]
    assert json.loads(pilot_control_artifact.read_text(encoding="utf-8")) == pilot_control_payload
    pilot_summary_artifact = bundle_dir / manifest_payload["artifacts"]["pilot_summary"]["file"]
    assert json.loads(pilot_summary_artifact.read_text(encoding="utf-8")) == pilot_summary_payload


def test_export_shift_bundle_rejects_repo_destination_that_is_not_gitignored(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    with pytest.raises(script_module.ShiftBundleExportError, match="gitignored"):
        script_module.export_pilot_shift_bundle(
            api_base_url="http://127.0.0.1:8001",
            output_dir=str(repo_root / "untracked-dir"),
            auth_token="seed-token",
            hours=24,
            now_fn=_fixed_now,
        )


def test_export_shift_bundle_surfaces_degraded_reasons_across_inputs(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

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
    pilot_control_payload = {
        "shop_id": "shop_default",
        "trial_provider_profile": "",
        "approved_calibration_artifact_id": "artifact_20260407",
        "approved_calibration_report_path": "C:/secure/pilot/artifacts/report.json",
        "cutover_mode": "invalid-mode",
        "opened_at": None,
        "opened_by_actor_id": None,
        "closed_at": None,
        "closed_by_actor_id": None,
        "last_preflight_at": "2026-04-07T08:55:00Z",
        "last_preflight_status": "degraded",
        "notes": "incident review",
    }
    pilot_summary_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "hours": 24,
        "overall_status": "degraded",
        "pilot_summary": {
            "overall_status": "degraded",
            "reasons": ["provider_failures_present", "fallback_rate_exceeded"],
            "trial_provider_profile": "pilot-v1",
        },
        "readiness": readiness_payload,
        "thresholds": {"max_fallback_rate": 0.05, "max_low_confidence_rate": 0.2},
    }

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    output_dir = repo_root / "secure-bundles" / "incident-review"
    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(output_dir),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "degraded"
    assert result["degraded_reasons"] == [
        "readiness_not_ready",
        "artifact_profile_mismatch",
        "provider_failures_present",
        "fallback_rate_exceeded",
        "pilot_control_cutover_mode_invalid",
        "pilot_control_trial_provider_profile_missing",
    ]


def test_export_shift_bundle_cli_exits_non_zero_when_bundle_is_degraded(capsys, monkeypatch, tmp_path) -> None:
    script_module = _load_export_shift_bundle_script_module()
    monkeypatch.setattr(
        script_module,
        "export_pilot_shift_bundle",
        lambda **_: {
            "bundle_id": "shift_bundle_20260407T090000000000Z",
            "manifest_path": str(tmp_path / "manifest.json"),
            "overall_status": "degraded",
            "degraded_reasons": ["provider_failures_present"],
        },
    )

    exit_code = script_module.main(
        [
            "--output-dir",
            str(tmp_path),
            "--auth-token",
            "seed-token",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "bundle_id": "shift_bundle_20260407T090000000000Z",
        "degraded_reasons": ["provider_failures_present"],
        "manifest_path": str(tmp_path / "manifest.json"),
        "overall_status": "degraded",
    }


def test_export_shift_bundle_adds_fallback_reason_when_preflight_is_degraded_without_reasons(
    tmp_path,
    monkeypatch,
) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

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
        "overall_status": "degraded",
        "runtime_mode": "trial",
        "trial_provider_profile": "pilot-v1",
        "cutover_mode": "shadow",
        "approved_calibration_artifact_id": "artifact_20260407",
        "reasons": [],
    }
    pilot_control_payload = {
        "shop_id": "shop_default",
        "trial_provider_profile": "pilot-v1",
        "approved_calibration_artifact_id": "artifact_20260407",
        "approved_calibration_report_path": "C:/secure/pilot/artifacts/report.json",
        "cutover_mode": "shadow",
        "opened_at": None,
        "opened_by_actor_id": None,
        "closed_at": None,
        "closed_by_actor_id": None,
        "last_preflight_at": "2026-04-07T08:55:00Z",
        "last_preflight_status": "degraded",
        "notes": "incident review",
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

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    output_dir = repo_root / "secure-bundles" / "incident-review"
    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(output_dir),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "degraded"
    assert result["degraded_reasons"] == ["preflight_not_ready"]


def test_export_shift_bundle_adds_fallback_reason_when_pilot_summary_is_degraded_without_reasons(
    tmp_path,
    monkeypatch,
) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

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
    pilot_control_payload = {
        "shop_id": "shop_default",
        "trial_provider_profile": "pilot-v1",
        "approved_calibration_artifact_id": "artifact_20260407",
        "approved_calibration_report_path": "C:/secure/pilot/artifacts/report.json",
        "cutover_mode": "shadow",
        "opened_at": None,
        "opened_by_actor_id": None,
        "closed_at": None,
        "closed_by_actor_id": None,
        "last_preflight_at": "2026-04-07T08:55:00Z",
        "last_preflight_status": "ready",
        "notes": "incident review",
    }
    pilot_summary_payload = {
        "api_base_url": "http://127.0.0.1:8001",
        "hours": 24,
        "overall_status": "degraded",
        "pilot_summary": {
            "overall_status": "degraded",
            "reasons": [],
            "trial_provider_profile": "pilot-v1",
        },
        "readiness": readiness_payload,
        "thresholds": {"max_fallback_rate": 0.05, "max_low_confidence_rate": 0.2},
    }

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    output_dir = repo_root / "secure-bundles" / "incident-review"
    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(output_dir),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "degraded"
    assert result["degraded_reasons"] == ["pilot_summary_not_ready"]


@pytest.mark.parametrize("invalid_reasons", [None, "provider_failures_present", {"reason": "bad"}])
def test_export_shift_bundle_handles_invalid_preflight_reasons_as_fallback(
    tmp_path,
    monkeypatch,
    invalid_reasons,
) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    readiness_payload = _ready_readiness_payload()
    preflight_payload = _ready_preflight_payload()
    preflight_payload["overall_status"] = "degraded"
    preflight_payload["reasons"] = invalid_reasons
    pilot_control_payload = _ready_pilot_control_payload()
    pilot_summary_payload = _ready_pilot_summary_payload(readiness_payload)

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(repo_root / "secure-bundles" / "incident-review"),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "degraded"
    assert result["degraded_reasons"] == ["preflight_not_ready"]


@pytest.mark.parametrize("invalid_reasons", [None, "fallback_rate_exceeded", {"reason": "bad"}])
def test_export_shift_bundle_handles_invalid_pilot_summary_reasons_as_fallback(
    tmp_path,
    monkeypatch,
    invalid_reasons,
) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    readiness_payload = _ready_readiness_payload()
    preflight_payload = _ready_preflight_payload()
    pilot_control_payload = _ready_pilot_control_payload()
    pilot_summary_payload = _ready_pilot_summary_payload(readiness_payload)
    pilot_summary_payload["overall_status"] = "degraded"
    pilot_summary_payload["pilot_summary"]["overall_status"] = "degraded"
    pilot_summary_payload["pilot_summary"]["reasons"] = invalid_reasons

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    result = script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(repo_root / "secure-bundles" / "incident-review"),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    assert result["overall_status"] == "degraded"
    assert result["degraded_reasons"] == ["pilot_summary_not_ready"]


def test_export_shift_bundle_wraps_output_directory_creation_failures(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    output_dir = (repo_root / "secure-bundles" / "shift-handoff").resolve()
    original_mkdir = Path.mkdir

    def _failing_mkdir(self: Path, *args, **kwargs):
        if self.resolve() == output_dir:
            raise OSError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _failing_mkdir)

    with pytest.raises(script_module.ShiftBundleExportError, match="Unable to create output directory"):
        script_module.export_pilot_shift_bundle(
            api_base_url="http://127.0.0.1:8001",
            output_dir=str(output_dir),
            auth_token="seed-token",
            hours=24,
            now_fn=_fixed_now,
        )


def test_export_shift_bundle_removes_partial_bundle_when_write_fails(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    readiness_payload = _ready_readiness_payload()
    preflight_payload = _ready_preflight_payload()
    pilot_control_payload = _ready_pilot_control_payload()
    pilot_summary_payload = _ready_pilot_summary_payload(readiness_payload)

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    original_write_json = script_module._write_json
    write_calls = {"count": 0}

    def _flaky_write_json(path: Path, payload: object) -> None:
        write_calls["count"] += 1
        if write_calls["count"] == 2:
            raise OSError("disk full")
        original_write_json(path, payload)

    monkeypatch.setattr(script_module, "_write_json", _flaky_write_json)

    output_dir = repo_root / "secure-bundles" / "shift-handoff"
    expected_bundle_dir = output_dir / "shift_bundle_20260407T090000000000Z"

    with pytest.raises(script_module.ShiftBundleExportError, match="Unable to write bundle artifact"):
        script_module.export_pilot_shift_bundle(
            api_base_url="http://127.0.0.1:8001",
            output_dir=str(output_dir),
            auth_token=None,
            login_email="owner@example.com",
            login_password="dev-password",
            hours=24,
            now_fn=_fixed_now,
        )

    assert not expected_bundle_dir.exists()


def test_export_shift_bundle_rejects_bundle_directory_collisions(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    readiness_payload = _ready_readiness_payload()
    preflight_payload = _ready_preflight_payload()
    pilot_control_payload = _ready_pilot_control_payload()
    pilot_summary_payload = _ready_pilot_summary_payload(readiness_payload)

    monkeypatch.setattr(script_module, "run_trial_readiness", lambda **_: _Summary(readiness_payload))
    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary(preflight_payload))
    monkeypatch.setattr(script_module, "run_pilot_summary_check", lambda **_: dict(pilot_summary_payload))
    monkeypatch.setattr(
        script_module,
        "_build_live_request",
        lambda _api_base_url: _build_request_json(pilot_control_payload=pilot_control_payload),
    )

    output_dir = repo_root / "secure-bundles" / "shift-handoff"

    script_module.export_pilot_shift_bundle(
        api_base_url="http://127.0.0.1:8001",
        output_dir=str(output_dir),
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        hours=24,
        now_fn=_fixed_now,
    )

    with pytest.raises(script_module.ShiftBundleExportError, match="already exists"):
        script_module.export_pilot_shift_bundle(
            api_base_url="http://127.0.0.1:8001",
            output_dir=str(output_dir),
            auth_token=None,
            login_email="owner@example.com",
            login_password="dev-password",
            hours=24,
            now_fn=_fixed_now,
        )


def test_validate_output_dir_prefers_git_check_ignore_when_available(tmp_path, monkeypatch) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitignore").write_text("secure-bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        script_module,
        "subprocess",
        SimpleNamespace(run=lambda *args, **kwargs: SimpleNamespace(returncode=1)),
        raising=False,
    )

    with pytest.raises(script_module.ShiftBundleExportError, match="gitignored"):
        script_module._validate_output_dir(str(repo_root / "secure-bundles" / "shift-handoff"))


def test_validate_output_dir_accepts_gitignored_directory_when_git_check_ignore_matches_trailing_slash(
    tmp_path,
    monkeypatch,
) -> None:
    script_module = _load_export_shift_bundle_script_module()
    repo_root = tmp_path / "repo"
    output_dir = repo_root / "backend" / "devdata" / "pilot_shift_bundles"
    output_dir.mkdir(parents=True)
    (repo_root / ".gitignore").write_text("backend/devdata/pilot_shift_bundles/\n", encoding="utf-8")
    monkeypatch.setattr(script_module, "REPO_ROOT", repo_root)

    def _fake_run(command, check=False):
        del check
        separator_index = command.index("--")
        checked_paths = command[separator_index + 1 :]
        if len(checked_paths) != 1:
            raise AssertionError("git check-ignore -q should be invoked with a single pathname")
        checked_path = checked_paths[0]
        return SimpleNamespace(returncode=0 if checked_path.endswith("/") else 1)

    monkeypatch.setattr(
        script_module,
        "subprocess",
        SimpleNamespace(run=_fake_run),
        raising=False,
    )

    assert script_module._validate_output_dir(str(output_dir)) == output_dir.resolve()
