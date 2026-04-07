import importlib
import json

import pytest


def _load_trial_readiness_module():
    try:
        return importlib.import_module("app.devtools.trial_readiness")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.trial_readiness module is missing: {exc}")


def _load_trial_readiness_script_module():
    try:
        return importlib.import_module("scripts.run_trial_readiness_check")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.run_trial_readiness_check module is missing: {exc}")


def _load_pilot_summary_check_script_module():
    try:
        return importlib.import_module("scripts.run_pilot_summary_check")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.run_pilot_summary_check module is missing: {exc}")


def _load_set_pilot_cutover_script_module():
    try:
        return importlib.import_module("scripts.set_pilot_cutover")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.set_pilot_cutover module is missing: {exc}")


def test_run_trial_readiness_reports_compact_ready_summary() -> None:
    module = _load_trial_readiness_module()
    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
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
                        "object_storage": {
                            "status": "ready",
                            "mode": "s3-compatible",
                            "message": "ok",
                            "details": {},
                        },
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
                                "calibration_dataset_dir_configured": "true",
                                "calibration_artifacts_dir_configured": "true",
                            },
                        },
                    },
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    result = module.run_trial_readiness(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert result.to_dict() == {
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
    assert calls == [
        ("GET", "/health", None, None),
        ("GET", "/api/v1/system/readiness", "seed-token", None),
    ]


def test_run_trial_readiness_logs_in_when_bearer_token_is_omitted() -> None:
    module = _load_trial_readiness_module()
    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/api/v1/auth/login":
            assert payload == {"email": "owner@example.com", "password": "dev-password"}
            return 200, {"data": {"access_token": "issued-token"}}
        if path == "/api/v1/system/readiness":
            assert token == "issued-token"
            return 200, {
                "data": {
                    "overall_status": "degraded",
                    "runtime_mode": "trial",
                    "trial_provider_profile": "",
                    "checks": {
                        "object_storage": {"status": "ready", "mode": "s3-compatible", "message": "ok", "details": {}},
                        "asr": {"status": "degraded", "mode": "real-provider", "message": "bad", "details": {}},
                        "ocr": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
                        "vision": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
                        "trial_profile": {
                            "status": "degraded",
                            "mode": "trial",
                            "message": "missing metadata",
                            "details": {
                                "reason": "missing_config",
                                "missing_fields": "trial_provider_profile",
                            },
                        },
                    },
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    result = module.run_trial_readiness(
        api_base_url="http://127.0.0.1:8001",
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        request_json=request_json,
    )

    assert result.readiness_status == "degraded"
    assert result.overall_status == "degraded"
    assert calls == [
        ("GET", "/health", None, None),
        ("POST", "/api/v1/auth/login", None, {"email": "owner@example.com", "password": "dev-password"}),
        ("GET", "/api/v1/system/readiness", "issued-token", None),
    ]


def test_run_trial_readiness_marks_local_demo_as_non_ready_operator_verdict() -> None:
    module = _load_trial_readiness_module()

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, token, payload
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/api/v1/system/readiness":
            return 200, {
                "data": {
                    "overall_status": "ready",
                    "runtime_mode": "local-demo",
                    "checks": {
                        "object_storage": {"status": "ready", "mode": "mock", "message": "ok", "details": {}},
                        "asr": {"status": "ready", "mode": "mock", "message": "ok", "details": {}},
                        "ocr": {"status": "ready", "mode": "mock", "message": "ok", "details": {}},
                        "vision": {"status": "ready", "mode": "mock", "message": "ok", "details": {}},
                    },
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    result = module.run_trial_readiness(
        api_base_url="http://127.0.0.1:8001",
        auth_token="seed-token",
        request_json=request_json,
    )

    assert result.runtime_mode == "local-demo"
    assert result.readiness_status == "ready"
    assert result.overall_status == "degraded"


def test_run_trial_readiness_raises_clear_error_for_invalid_readiness_envelope() -> None:
    module = _load_trial_readiness_module()

    def malformed_request(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, token, payload
        if path == "/health":
            return 200, {"status": "ok"}
        return 200, {"overall_status": "ready"}

    with pytest.raises(module.TrialReadinessError, match="data envelope"):
        module.run_trial_readiness(
            api_base_url="http://127.0.0.1:8001",
            auth_token="seed-token",
            request_json=malformed_request,
        )


def test_trial_readiness_cli_defaults_to_owner_login_credentials() -> None:
    script_module = _load_trial_readiness_script_module()
    parser = script_module.build_parser()

    args = parser.parse_args([])

    assert args.auth_token is None
    assert args.login_email == "owner@example.com"
    assert args.login_password == "dev-password"


def test_trial_readiness_cli_defaults_follow_seed_owner_env(monkeypatch) -> None:
    script_module = _load_trial_readiness_script_module()
    monkeypatch.setenv("SEED_OWNER_EMAIL", "pilot-owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "pilot-pass-123")
    parser = script_module.build_parser()

    args = parser.parse_args([])

    assert args.auth_token is None
    assert args.login_email == "pilot-owner@example.com"
    assert args.login_password == "pilot-pass-123"


def test_trial_readiness_cli_prints_compact_json_and_exits_zero_when_ready(capsys, monkeypatch) -> None:
    script_module = _load_trial_readiness_script_module()
    summary = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="ready",
        overall_status="ready",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )

    def _fake_run_trial_readiness(**_: object):
        return summary

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == summary.to_dict()
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_trial_readiness_cli_returns_non_zero_when_summary_is_not_ready(capsys, monkeypatch) -> None:
    script_module = _load_trial_readiness_script_module()
    summary = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="degraded",
        overall_status="degraded",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "degraded", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )

    def _fake_run_trial_readiness(**_: object):
        return summary

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == summary.to_dict()
    assert captured.err == ""


def test_trial_readiness_cli_reports_error_and_exits_non_zero(capsys, monkeypatch) -> None:
    script_module = _load_trial_readiness_script_module()

    def _raise_error(**_: object):
        raise script_module.TrialReadinessError("readiness request failed")

    monkeypatch.setattr(script_module, "run_trial_readiness", _raise_error)

    exit_code = script_module.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Trial readiness check failed" in captured.err


def test_set_pilot_cutover_cli_defaults_to_owner_login_credentials() -> None:
    script_module = _load_set_pilot_cutover_script_module()
    parser = script_module.build_parser()

    args = parser.parse_args(["--mode", "shadow"])

    assert args.auth_token is None
    assert args.login_email == "owner@example.com"
    assert args.login_password == "dev-password"


def test_set_pilot_cutover_cli_returns_non_zero_when_open_preflight_is_not_ready(
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_set_pilot_cutover_script_module()

    class _Summary:
        overall_status = "degraded"

        @staticmethod
        def to_dict() -> dict[str, object]:
            return {
                "overall_status": "degraded",
                "reasons": ["artifact_profile_mismatch"],
            }

    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary())

    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
        raise AssertionError(f"Unexpected request path: {path}")

    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(["--mode", "open", "--artifact-path", "C:/secure/pilot/artifacts/approved.json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Cutover preflight failed" in captured.err
    assert calls == []


def test_set_pilot_cutover_cli_prints_compact_json_and_exits_zero_on_success(capsys, monkeypatch) -> None:
    script_module = _load_set_pilot_cutover_script_module()
    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
        if path == "/api/v1/auth/login":
            return 200, {"data": {"access_token": "issued-token"}}
        if path == "/api/v1/system/pilot-control":
            assert token == "issued-token"
            assert payload == {
                "cutover_mode": "shadow",
                "approved_calibration_artifact_id": None,
                "approved_calibration_report_path": None,
                "last_preflight_status": None,
                "notes": "provider observation window",
            }
            return 200, {
                "data": {
                    "shop_id": "shop_default",
                    "previous_cutover_mode": "closed",
                    "cutover_mode": "shadow",
                    "transition_audit_log_id": "audit_transition_shadow",
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(
        [
            "--mode",
            "shadow",
            "--note",
            "provider observation window",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "cutover_mode": "shadow",
        "previous_cutover_mode": "closed",
        "shop_id": "shop_default",
        "transition_audit_log_id": "audit_transition_shadow",
    }
    assert captured.err == ""
    assert calls == [
        ("POST", "/api/v1/auth/login", None, {"email": "owner@example.com", "password": "dev-password"}),
        (
            "POST",
            "/api/v1/system/pilot-control",
            "issued-token",
            {
                "cutover_mode": "shadow",
                "approved_calibration_artifact_id": None,
                "approved_calibration_report_path": None,
                "last_preflight_status": None,
                "notes": "provider observation window",
            },
        ),
    ]


def test_set_pilot_cutover_cli_returns_non_zero_when_server_rejects_transition(
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_set_pilot_cutover_script_module()

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        if path == "/api/v1/auth/login":
            return 200, {"data": {"access_token": "issued-token"}}
        if path == "/api/v1/system/pilot-control":
            assert method == "POST"
            assert token == "issued-token"
            assert payload == {
                "cutover_mode": "open",
                "approved_calibration_artifact_id": None,
                "approved_calibration_report_path": None,
                "last_preflight_status": None,
                "notes": None,
            }
            return 409, {
                "error": {
                    "code": "invalid_cutover_mode_transition",
                    "message": "cutover_mode transition is not allowed",
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(["--mode", "open", "--skip-preflight"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "invalid_cutover_mode_transition" in captured.err


def test_set_pilot_cutover_cli_derives_artifact_id_from_artifact_path_for_open_mode(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_set_pilot_cutover_script_module()
    artifact_file = tmp_path / "approved.json"
    artifact_file.write_text(
        json.dumps(
            {
                "artifact_id": "artifact_approved_20260407",
                "trial_provider_profile": "pilot-v1",
                "recommended_shop_rules": {},
            }
        ),
        encoding="utf-8",
    )

    class _Summary:
        overall_status = "ready"

        @staticmethod
        def to_dict() -> dict[str, object]:
            return {"overall_status": "ready", "reasons": []}

    monkeypatch.setattr(script_module, "run_live_pilot_preflight", lambda **_: _Summary())

    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
        if path == "/api/v1/auth/login":
            return 200, {"data": {"access_token": "issued-token"}}
        if path == "/api/v1/system/pilot-control":
            assert token == "issued-token"
            assert payload == {
                "cutover_mode": "open",
                "approved_calibration_artifact_id": "artifact_approved_20260407",
                "approved_calibration_report_path": str(artifact_file),
                "last_preflight_status": "ready",
                "notes": "morning shift",
            }
            return 200, {
                "data": {
                    "shop_id": "shop_default",
                    "previous_cutover_mode": "shadow",
                    "cutover_mode": "open",
                    "transition_audit_log_id": "audit_transition_open",
                }
            }
        raise AssertionError(f"Unexpected request path: {path}")

    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(
        [
            "--mode",
            "open",
            "--artifact-path",
            str(artifact_file),
            "--note",
            "morning shift",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "cutover_mode": "open",
        "previous_cutover_mode": "shadow",
        "shop_id": "shop_default",
        "transition_audit_log_id": "audit_transition_open",
    }
    assert captured.err == ""
    assert calls == [
        ("POST", "/api/v1/auth/login", None, {"email": "owner@example.com", "password": "dev-password"}),
        (
            "POST",
            "/api/v1/system/pilot-control",
            "issued-token",
            {
                "cutover_mode": "open",
                "approved_calibration_artifact_id": "artifact_approved_20260407",
                "approved_calibration_report_path": str(artifact_file),
                "last_preflight_status": "ready",
                "notes": "morning shift",
            },
        ),
    ]


def test_pilot_summary_check_cli_prints_compact_json_and_exits_zero_when_summary_is_ready(
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_pilot_summary_check_script_module()
    readiness = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="ready",
        overall_status="ready",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )
    calls: list[tuple[str, str, str | None, dict[str, object] | None]] = []

    def _fake_run_trial_readiness(**_: object):
        return readiness

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        calls.append((method, path, token, payload))
        return 200, {
            "data": {
                "time_window": {
                    "hours": 24,
                    "started_at": "2026-04-07T00:00:00",
                    "ended_at": "2026-04-08T00:00:00",
                },
                "task_totals": {
                    "voice-stock-query": {"completed": 2, "failed": 1},
                    "photo-stock-in": {"awaiting-confirmation": 1, "completed": 1},
                },
                "confirmations": {"created": 2, "approved": 1, "rejected": 1},
                "telemetry_task_count": 4,
                "low_confidence_count": 1,
                "fallback_count": 1,
                "provider_failures": {},
                "trial_provider_profile": "pilot-v1",
            }
        }

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)
    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(
        [
            "--auth-token",
            "seed-token",
            "--hours",
            "24",
            "--max-fallback-rate",
            "0.25",
            "--max-low-confidence-rate",
            "0.50",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "api_base_url": "http://127.0.0.1:8001",
        "hours": 24,
        "overall_status": "ready",
        "pilot_summary": {
            "confirmations": {"approved": 1, "created": 2, "rejected": 1},
            "confirmation_rate": 0.4,
            "fallback_count": 1,
            "fallback_rate": 0.25,
            "low_confidence_count": 1,
            "low_confidence_rate": 0.25,
            "overall_status": "ready",
            "provider_failures": {},
            "reasons": [],
            "rejection_rate": 0.5,
            "task_totals": {
                "photo-stock-in": {"awaiting-confirmation": 1, "completed": 1},
                "voice-stock-query": {"completed": 2, "failed": 1},
            },
            "time_window": {
                "ended_at": "2026-04-08T00:00:00",
                "hours": 24,
                "started_at": "2026-04-07T00:00:00",
            },
            "telemetry_task_count": 4,
            "total_task_count": 5,
            "trial_provider_profile": "pilot-v1",
        },
        "readiness": readiness.to_dict(),
        "thresholds": {
            "max_fallback_rate": 0.25,
            "max_low_confidence_rate": 0.5,
        },
    }
    assert captured.err == ""
    assert calls == [("GET", "/api/v1/system/pilot-summary?hours=24", "seed-token", None)]


@pytest.mark.parametrize(
    ("status_code", "body", "message_fragment"),
    [
        (500, {"error": {"code": "boom"}}, "returned HTTP 500"),
        (200, {"task_totals": {}}, "did not return a data envelope"),
    ],
)
def test_pilot_summary_check_cli_reports_summary_fetch_errors(
    status_code,
    body,
    message_fragment,
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_pilot_summary_check_script_module()
    readiness = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="ready",
        overall_status="ready",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )

    def _fake_run_trial_readiness(**_: object):
        return readiness

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, path, token, payload
        return status_code, body

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)
    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(["--auth-token", "seed-token"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Pilot summary check failed" in captured.err
    assert message_fragment in captured.err


def test_pilot_summary_check_cli_returns_non_zero_for_missing_profile_provider_failures_and_threshold_breach(
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_pilot_summary_check_script_module()
    readiness = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="ready",
        overall_status="ready",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )

    def _fake_run_trial_readiness(**_: object):
        return readiness

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, path, token, payload
        return 200, {
            "data": {
                "time_window": {
                    "hours": 24,
                    "started_at": "2026-04-07T00:00:00",
                    "ended_at": "2026-04-08T00:00:00",
                },
                "task_totals": {
                    "voice-stock-query": {"completed": 1, "failed": 2},
                    "photo-stock-in": {"awaiting-confirmation": 1, "completed": 1},
                },
                "confirmations": {"created": 3, "approved": 1, "rejected": 1},
                "telemetry_task_count": 4,
                "low_confidence_count": 2,
                "fallback_count": 2,
                "provider_failures": {"vision_unavailable": 1},
                "trial_provider_profile": "",
            }
        }

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)
    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(
        [
            "--auth-token",
            "seed-token",
            "--max-fallback-rate",
            "0.20",
            "--max-low-confidence-rate",
            "0.20",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["overall_status"] == "degraded"
    assert payload["pilot_summary"]["overall_status"] == "degraded"
    assert payload["pilot_summary"]["telemetry_task_count"] == 4
    assert payload["pilot_summary"]["trial_provider_profile"] == ""
    assert payload["pilot_summary"]["fallback_rate"] == 0.5
    assert payload["pilot_summary"]["low_confidence_rate"] == 0.5
    assert payload["pilot_summary"]["provider_failures"] == {"vision_unavailable": 1}
    assert payload["pilot_summary"]["reasons"] == [
        "trial_provider_profile_missing",
        "provider_failures_present",
        "fallback_rate_exceeded",
        "low_confidence_rate_exceeded",
    ]
    assert captured.err == ""


def test_pilot_summary_check_cli_rejects_non_string_trial_provider_profile(
    capsys,
    monkeypatch,
) -> None:
    script_module = _load_pilot_summary_check_script_module()
    readiness = script_module.TrialReadinessSummary(
        api_base_url="http://127.0.0.1:8001",
        health_status="ok",
        runtime_mode="trial",
        readiness_status="ready",
        overall_status="ready",
        object_storage={"status": "ready", "mode": "s3-compatible"},
        providers={
            "asr": {"status": "ready", "mode": "real-provider"},
            "ocr": {"status": "ready", "mode": "real-provider"},
            "vision": {"status": "ready", "mode": "real-provider"},
        },
    )

    def _fake_run_trial_readiness(**_: object):
        return readiness

    def _fake_request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        del method, path, token, payload
        return 200, {
            "data": {
                "time_window": {
                    "hours": 24,
                    "started_at": "2026-04-07T00:00:00",
                    "ended_at": "2026-04-08T00:00:00",
                },
                "task_totals": {"voice-stock-query": {"completed": 1}},
                "confirmations": {"created": 0, "approved": 0, "rejected": 0},
                "telemetry_task_count": 1,
                "low_confidence_count": 0,
                "fallback_count": 0,
                "provider_failures": {},
                "trial_provider_profile": 17,
            }
        }

    monkeypatch.setattr(script_module, "run_trial_readiness", _fake_run_trial_readiness)
    monkeypatch.setattr(script_module, "_build_live_request", lambda _: _fake_request_json)

    exit_code = script_module.main(["--auth-token", "seed-token"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Pilot summary check failed" in captured.err
    assert "trial_provider_profile" in captured.err
