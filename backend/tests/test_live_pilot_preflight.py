import importlib
import json

import pytest


def _load_live_pilot_preflight_module():
    try:
        return importlib.import_module("app.devtools.live_pilot_preflight")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.live_pilot_preflight module is missing: {exc}")


def _load_live_pilot_preflight_script_module():
    try:
        return importlib.import_module("scripts.run_live_pilot_preflight")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.run_live_pilot_preflight module is missing: {exc}")


def _request_json_ready(path_to_use: str):
    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, payload
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/api/v1/system/readiness":
            assert token == "seed-token"
            return 200, {
                "data": {
                    "overall_status": "ready",
                    "runtime_mode": "trial",
                    "trial_provider_profile": "pilot-v1",
                    "checks": {
                        "object_storage": {"status": "ready", "mode": "s3-compatible", "message": "ok", "details": {}},
                        "asr": {
                            "status": "ready",
                            "mode": "real-provider",
                            "message": "ok",
                            "details": {"provider_label": "asr-primary"},
                        },
                        "ocr": {
                            "status": "ready",
                            "mode": "real-provider",
                            "message": "ok",
                            "details": {"provider_label": "ocr-primary"},
                        },
                        "vision": {
                            "status": "ready",
                            "mode": "real-provider",
                            "message": "ok",
                            "details": {"provider_label": "vision-primary"},
                        },
                        "trial_profile": {
                            "status": "ready",
                            "mode": "trial",
                            "message": "ok",
                            "details": {
                                "trial_provider_profile": "pilot-v1",
                                "trial_calibration_dataset_dir": "/secure/pilot/datasets/v1",
                                "trial_calibration_artifacts_dir": "/secure/pilot/artifacts/v1",
                                "allowed_live_pilot_shop_ids": "shop_default,shop_alpha",
                                "asr_provider_label": "asr-primary",
                                "ocr_provider_label": "ocr-primary",
                                "vision_provider_label": "vision-primary",
                            },
                        },
                    },
                }
            }
        if path == "/api/v1/system/pilot-control":
            assert token == "seed-token"
            return 200, {
                "data": {
                    "shop_id": "shop_default",
                    "trial_provider_profile": "pilot-v1",
                    "approved_calibration_artifact_id": "artifact_20260407",
                    "approved_calibration_report_path": path_to_use,
                    "cutover_mode": "shadow",
                    "opened_at": None,
                    "opened_by_actor_id": None,
                    "closed_at": None,
                    "closed_by_actor_id": None,
                    "last_preflight_at": None,
                    "last_preflight_status": None,
                    "notes": None,
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    return request_json


def test_live_pilot_preflight_success_when_readiness_is_green_and_artifact_matches_profile(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        artifact_path=None,
        request_json=request_json,
    )

    assert summary.overall_status == "ready"
    assert summary.trial_provider_profile == "pilot-v1"
    assert summary.approved_calibration_artifact_id == "artifact_20260407"
    assert summary.cutover_mode == "shadow"
    assert summary.reasons == []


def test_live_pilot_preflight_fails_when_artifact_path_is_missing() -> None:
    module = _load_live_pilot_preflight_module()
    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        artifact_path="",
        request_json=_request_json_ready(""),
    )

    assert summary.overall_status == "degraded"
    assert "artifact_path_missing" in summary.reasons


def test_live_pilot_preflight_fails_when_artifact_profile_mismatch(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v2",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "artifact_profile_mismatch" in summary.reasons


def test_live_pilot_preflight_fails_when_shop_not_allowed_for_live_pilot(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        if path == "/api/v1/system/pilot-control":
            payload = response[1]["data"]
            payload["shop_id"] = "shop_blocked"
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "shop_not_allowed" in summary.reasons


def test_live_pilot_preflight_fails_when_trial_profile_details_metadata_is_blank(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            trial_profile_details = response[1]["data"]["checks"]["trial_profile"]["details"]
            trial_profile_details["trial_provider_profile"] = ""
            trial_profile_details["asr_provider_label"] = ""
            trial_profile_details["ocr_provider_label"] = ""
            trial_profile_details["vision_provider_label"] = ""
            trial_profile_details["trial_calibration_dataset_dir"] = ""
            trial_profile_details["trial_calibration_artifacts_dir"] = ""
            trial_profile_details["allowed_live_pilot_shop_ids"] = ""
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "trial_profile_details_trial_provider_profile_missing" in summary.reasons
    assert "trial_profile_details_asr_provider_label_missing" in summary.reasons
    assert "trial_profile_details_ocr_provider_label_missing" in summary.reasons
    assert "trial_profile_details_vision_provider_label_missing" in summary.reasons


def test_live_pilot_preflight_returns_degraded_summary_for_malformed_artifact_json(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "artifact_json_invalid" in summary.reasons


def test_live_pilot_preflight_returns_degraded_summary_for_invalid_artifact_field_types(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": 123,
                "trial_provider_profile": 456,
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "artifact_id_invalid_type" in summary.reasons
    assert "artifact_profile_invalid_type" in summary.reasons


def test_live_pilot_preflight_cli_defaults_to_owner_login_credentials() -> None:
    script_module = _load_live_pilot_preflight_script_module()
    parser = script_module.build_parser()

    args = parser.parse_args([])

    assert args.auth_token is None
    assert args.login_email == "owner@example.com"
    assert args.login_password == "dev-password"


def test_live_pilot_preflight_degrades_when_runtime_mode_is_not_trial(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            response[1]["data"]["runtime_mode"] = "local-demo"
            response[1]["data"]["checks"]["trial_profile"]["mode"] = "local-demo"
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "runtime_mode_not_trial" in summary.reasons


def test_live_pilot_preflight_degrades_when_allowlist_is_not_explicitly_configured(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
            details["allowed_live_pilot_shop_ids"] = ""
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "allowed_live_pilot_shop_ids_missing" in summary.reasons


def test_live_pilot_preflight_degrades_when_profile_and_labels_drift_across_sources(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifact_path = tmp_path / "approved.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v3",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(artifact_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            response[1]["data"]["trial_provider_profile"] = "pilot-v1"
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_provider_profile"] = "pilot-v2"
            details["trial_calibration_artifacts_dir"] = str(tmp_path)
            response[1]["data"]["checks"]["asr"]["details"]["provider_label"] = "asr-live"
            details["asr_provider_label"] = "asr-mirror"
        if path == "/api/v1/system/pilot-control":
            response[1]["data"]["trial_provider_profile"] = "pilot-v4"
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "trial_provider_profile_mismatch_readiness_vs_trial_profile_details" in summary.reasons
    assert "trial_provider_profile_mismatch_readiness_vs_pilot_control" in summary.reasons
    assert "artifact_profile_mismatch" in summary.reasons
    assert "asr_provider_label_mismatch_readiness_vs_trial_profile_details" in summary.reasons


def test_live_pilot_preflight_degrades_when_artifact_path_escapes_artifacts_dir(tmp_path) -> None:
    module = _load_live_pilot_preflight_module()
    artifacts_dir = tmp_path / "approved-artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    outside_path = tmp_path / "outside.json"
    outside_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.25,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": False,
                },
            }
        ),
        encoding="utf-8",
    )

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        response = _request_json_ready(str(outside_path))(method, path, token=token, payload=payload)
        if path == "/api/v1/system/readiness":
            details = response[1]["data"]["checks"]["trial_profile"]["details"]
            details["trial_calibration_artifacts_dir"] = str(artifacts_dir)
        return response

    summary = module.run_live_pilot_preflight(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert summary.overall_status == "degraded"
    assert "artifact_path_outside_artifacts_dir" in summary.reasons


def test_live_pilot_preflight_cli_prints_compact_json_and_exits_zero_when_ready(capsys, monkeypatch) -> None:
    script_module = _load_live_pilot_preflight_script_module()
    preflight_module = _load_live_pilot_preflight_module()
    summary = preflight_module.LivePilotPreflightSummary(
        overall_status="ready",
        runtime_mode="trial",
        trial_provider_profile="pilot-v1",
        cutover_mode="shadow",
        approved_calibration_artifact_id="artifact_20260407",
        reasons=[],
    )

    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: summary)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == summary.to_dict()
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_live_pilot_preflight_cli_returns_non_zero_when_summary_is_not_ready(capsys, monkeypatch) -> None:
    script_module = _load_live_pilot_preflight_script_module()
    preflight_module = _load_live_pilot_preflight_module()
    summary = preflight_module.LivePilotPreflightSummary(
        overall_status="degraded",
        runtime_mode="trial",
        trial_provider_profile="pilot-v1",
        cutover_mode="shadow",
        approved_calibration_artifact_id="artifact_20260407",
        reasons=["runtime_mode_not_trial"],
    )

    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: summary)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == summary.to_dict()
    assert captured.err == ""


def test_live_pilot_preflight_cli_reports_error_and_exits_non_zero(capsys, monkeypatch) -> None:
    script_module = _load_live_pilot_preflight_script_module()

    def _raise_error(**_: object):
        raise script_module.LivePilotPreflightError("preflight request failed")

    monkeypatch.setattr(script_module, "run_live_pilot_preflight", _raise_error)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Live pilot preflight failed" in captured.err
