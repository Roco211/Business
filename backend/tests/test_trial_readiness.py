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
                    "checks": {
                        "object_storage": {
                            "status": "ready",
                            "mode": "s3-compatible",
                            "message": "ok",
                            "details": {},
                        },
                        "asr": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
                        "ocr": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
                        "vision": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
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
                    "checks": {
                        "object_storage": {"status": "ready", "mode": "s3-compatible", "message": "ok", "details": {}},
                        "asr": {"status": "degraded", "mode": "real-provider", "message": "bad", "details": {}},
                        "ocr": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
                        "vision": {"status": "ready", "mode": "real-provider", "message": "ok", "details": {}},
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
