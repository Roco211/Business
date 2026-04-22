from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _load_app_cli_module():
    try:
        return importlib.import_module("scripts.app_cli")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.app_cli module is missing: {exc}")


def test_app_cli_check_delegates_to_run_system_check(monkeypatch) -> None:
    module = _load_app_cli_module()
    captured: list[list[str]] = []

    def _fake_system_check_main(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(module, "run_system_check_main", _fake_system_check_main)

    exit_code = module.main(
        [
            "check",
            "--mode",
            "trial",
            "--api-base-url",
            "http://127.0.0.1:8001",
        ]
    )

    assert exit_code == 0
    assert captured == [
        [
            "--mode",
            "trial",
            "--api-base-url",
            "http://127.0.0.1:8001",
        ]
    ]


def test_app_cli_demo_runs_local_demo_smoke_and_prints_snapshot(monkeypatch, capsys) -> None:
    module = _load_app_cli_module()
    captured_call: dict[str, object] = {}

    class _FakeDemoResult:
        def to_dict(self) -> dict[str, object]:
            return {
                "api_base_url": "http://127.0.0.1:8001",
                "health_status": "ok",
                "shop_id": "shop_default",
                "session_id": "sess_default",
                "inventory_item_count": 3,
                "inventory_item_names": ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
                "pending_confirmation_count": 2,
                "pending_confirmation_types": ["receipt-stock-in-batch", "stock-out"],
                "open_low_stock_alert_count": 1,
                "open_low_stock_item_names": ["Cola"],
                "message_count": 10,
                "task_run_count": 4,
                "recent_messages": [
                    {
                        "actor_type": "system",
                        "message_type": "text",
                        "text": "Please confirm the receipt line items before committing inventory.",
                    },
                    {
                        "actor_type": "owner",
                        "message_type": "receipt-image",
                        "text": None,
                    },
                ],
                "replay_event_count": 4,
                "latest_replay_seq": 4,
            }

    def _fake_run_local_demo_smoke(
        *,
        api_base_url: str,
        auth_token: str | None = None,
        login_email: str | None = None,
        login_password: str | None = None,
    ) -> _FakeDemoResult:
        captured_call.update(
            {
                "api_base_url": api_base_url,
                "auth_token": auth_token,
                "login_email": login_email,
                "login_password": login_password,
            }
        )
        return _FakeDemoResult()

    monkeypatch.setattr(module, "run_local_demo_smoke", _fake_run_local_demo_smoke, raising=False)

    exit_code = module.main(
        [
            "demo",
            "--api-base-url",
            "http://127.0.0.1:8001",
            "--auth-token",
            "token-123",
            "--login-email",
            "owner@example.com",
            "--login-password",
            "dev-password",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_call == {
        "api_base_url": "http://127.0.0.1:8001",
        "auth_token": "token-123",
        "login_email": "owner@example.com",
        "login_password": "dev-password",
    }
    assert json.loads(captured.out) == {
        "api_base_url": "http://127.0.0.1:8001",
        "health_status": "ok",
        "shop_id": "shop_default",
        "session_id": "sess_default",
        "inventory_item_count": 3,
        "inventory_item_names": ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
        "pending_confirmation_count": 2,
        "pending_confirmation_types": ["receipt-stock-in-batch", "stock-out"],
        "open_low_stock_alert_count": 1,
        "open_low_stock_item_names": ["Cola"],
        "message_count": 10,
        "task_run_count": 4,
        "recent_messages": [
            {
                "actor_type": "system",
                "message_type": "text",
                "text": "Please confirm the receipt line items before committing inventory.",
            },
            {
                "actor_type": "owner",
                "message_type": "receipt-image",
                "text": None,
            },
        ],
        "replay_event_count": 4,
        "latest_replay_seq": 4,
    }


def test_app_cli_cutover_uses_latest_runtime_artifact_when_not_explicitly_provided(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_app_cli_module()
    runtime_root = tmp_path / "runtime"
    artifacts_dir = runtime_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    older_artifact = artifacts_dir / "artifact_old.json"
    older_artifact.write_text(
        json.dumps({"artifact_id": "artifact-old", "trial_provider_profile": "pilot-old"}),
        encoding="utf-8",
    )
    newer_artifact = artifacts_dir / "artifact_new.json"
    newer_artifact.write_text(
        json.dumps({"artifact_id": "artifact-new", "trial_provider_profile": "pilot-new"}),
        encoding="utf-8",
    )
    captured: list[list[str]] = []

    def _fake_cutover_main(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(module, "set_pilot_cutover_main", _fake_cutover_main)

    exit_code = module.main(
        [
            "cutover",
            "--mode",
            "shadow",
            "--runtime-root",
            str(runtime_root),
            "--api-base-url",
            "http://127.0.0.1:8001",
        ]
    )

    assert exit_code == 0
    assert captured == [
        [
            "--mode",
            "shadow",
            "--api-base-url",
            "http://127.0.0.1:8001",
            "--artifact-path",
            str(newer_artifact),
        ]
    ]


def test_app_cli_up_prepares_trial_runtime_and_starts_uvicorn(monkeypatch, tmp_path) -> None:
    module = _load_app_cli_module()
    runtime_root = tmp_path / "runtime"
    source_artifacts_dir = tmp_path / "source-artifacts"
    source_artifacts_dir.mkdir(parents=True, exist_ok=True)
    source_artifact = source_artifacts_dir / "pilot-private-default_report.json"
    source_artifact.write_text(
        json.dumps(
            {
                "artifact_id": "artifact-1",
                "trial_provider_profile": "pilot-private-default",
                "recommended_shop_rules": {},
            }
        ),
        encoding="utf-8",
    )
    upgrade_calls: list[str] = []
    uvicorn_calls: list[dict[str, object]] = []

    monkeypatch.setattr(module, "DEFAULT_ARTIFACT_SEARCH_DIR", source_artifacts_dir)
    monkeypatch.setattr(module, "run_alembic_upgrade", lambda database_url: upgrade_calls.append(database_url))

    def _fake_run_uvicorn(*, host: str, port: int) -> int:
        uvicorn_calls.append(
            {
                "host": host,
                "port": port,
                "app_runtime_mode": module.os.environ["APP_RUNTIME_MODE"],
                "trial_provider_profile": module.os.environ["TRIAL_PROVIDER_PROFILE"],
                "database_url": module.os.environ["DATABASE_URL"],
                "artifacts_dir": module.os.environ["TRIAL_CALIBRATION_ARTIFACTS_DIR"],
            }
        )
        return 0

    monkeypatch.setattr(module, "run_uvicorn_app", _fake_run_uvicorn)

    exit_code = module.main(
        [
            "up",
            "--profile",
            "trial",
            "--runtime-root",
            str(runtime_root),
            "--port",
            "8011",
        ]
    )

    copied_artifact = runtime_root / "artifacts" / source_artifact.name

    assert exit_code == 0
    assert upgrade_calls == ["sqlite:///" + runtime_root.joinpath("runtime.db").as_posix()]
    assert copied_artifact.exists()
    assert uvicorn_calls == [
        {
            "host": "127.0.0.1",
            "port": 8011,
            "app_runtime_mode": "trial",
            "trial_provider_profile": "pilot-private-default",
            "database_url": "sqlite:///" + runtime_root.joinpath("runtime.db").as_posix(),
            "artifacts_dir": str(runtime_root / "artifacts"),
        }
    ]


def test_app_cli_up_uses_local_demo_profile_without_trial_only_env(monkeypatch, tmp_path) -> None:
    module = _load_app_cli_module()
    runtime_root = tmp_path / "runtime"
    upgrade_calls: list[str] = []
    uvicorn_calls: list[dict[str, object]] = []

    monkeypatch.setattr(module, "run_alembic_upgrade", lambda database_url: upgrade_calls.append(database_url))

    def _fake_run_uvicorn(*, host: str, port: int) -> int:
        uvicorn_calls.append(
            {
                "host": host,
                "port": port,
                "app_runtime_mode": module.os.environ["APP_RUNTIME_MODE"],
                "trial_provider_profile": module.os.environ.get("TRIAL_PROVIDER_PROFILE", ""),
                "object_storage_provider": module.os.environ["OBJECT_STORAGE_PROVIDER"],
            }
        )
        return 0

    monkeypatch.setattr(module, "run_uvicorn_app", _fake_run_uvicorn)

    exit_code = module.main(
        [
            "up",
            "--profile",
            "local-demo",
            "--runtime-root",
            str(runtime_root),
        ]
    )

    assert exit_code == 0
    assert upgrade_calls == ["sqlite:///" + runtime_root.joinpath("runtime.db").as_posix()]
    assert uvicorn_calls == [
        {
            "host": "127.0.0.1",
            "port": 8001,
            "app_runtime_mode": "local-demo",
            "trial_provider_profile": "",
            "object_storage_provider": "mock",
        }
    ]


def test_app_cli_reports_runtime_errors_and_exits_non_zero(monkeypatch, tmp_path, capsys) -> None:
    module = _load_app_cli_module()
    runtime_root = tmp_path / "runtime"

    monkeypatch.setattr(module, "run_alembic_upgrade", lambda _database_url: (_ for _ in ()).throw(RuntimeError("boom")))

    exit_code = module.main(
        [
            "up",
            "--profile",
            "local-demo",
            "--runtime-root",
            str(runtime_root),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "boom" in captured.err
