from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AuditLog, Shop
from app.services.bootstrap import ensure_default_context


def _load_apply_script_module():
    try:
        return importlib.import_module("scripts.apply_trial_calibration")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.apply_trial_calibration module is missing: {exc}")


def _create_generated_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.devtools.pilot_calibration import run_pilot_calibration

    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-2026-04")
    media_path = tmp_path / "voice.m4a"
    media_path.write_bytes(b"asr")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04",
                "cases": [
                    {
                        "case_id": "asr-pass",
                        "capability": "asr",
                        "media_path": str(media_path),
                        "expected": {"transcript_contains": ["cola"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    calibration_result = run_pilot_calibration(
        manifest_path=manifest_path,
        output_dir=tmp_path / "artifacts",
        evaluate_asr=lambda **_: {
            "transcript": "cola in stock",
            "confidence": 0.91,
            "provider_name": "stub-asr",
            "used_fallback": False,
            "latency_ms": 2,
        },
        evaluate_ocr=lambda **_: {},
        evaluate_vision=lambda **_: {},
    )
    return Path(calibration_result["json_report_path"])


def test_apply_trial_calibration_updates_shop_rules_and_writes_audit_log(
    db_session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_apply_script_module()
    context = ensure_default_context(db_session)
    context.shop.require_price_confirmation = False
    context.shop.require_new_item_confirmation = False
    db_session.flush()
    report_path = _create_generated_report(tmp_path, monkeypatch)

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["trial_provider_profile"] == "pilot-2026-04"
    assert report_payload["recommended_shop_rules"] == {
        "low_confidence_threshold": 0.9,
        "require_price_confirmation": True,
        "require_new_item_confirmation": True,
    }

    result = module.apply_trial_calibration(
        report_path=report_path,
        shop_id=context.shop.shop_id,
        actor_id="owner_default",
        db_session=db_session,
    )

    db_session.expire_all()
    updated_shop = db_session.get(Shop, context.shop.shop_id)
    assert updated_shop is not None
    assert float(updated_shop.low_confidence_threshold) == pytest.approx(0.9)
    assert updated_shop.require_price_confirmation is True
    assert updated_shop.require_new_item_confirmation is True

    audit_logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(
                AuditLog.shop_id == context.shop.shop_id,
                AuditLog.scope == "shop-rules",
                AuditLog.action == "shop_rules.trial_calibration_applied",
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.audit_log_id.asc())
        )
    )
    assert len(audit_logs) == 1
    metadata = audit_logs[0].metadata_json
    assert metadata["trial_provider_profile"] == "pilot-2026-04"
    assert metadata["artifact_id"] == report_payload["artifact_id"]
    assert metadata["before"] == {
        "low_confidence_threshold": 0.85,
        "require_price_confirmation": False,
        "require_new_item_confirmation": False,
    }
    assert metadata["after"] == {
        "low_confidence_threshold": 0.9,
        "require_price_confirmation": True,
        "require_new_item_confirmation": True,
    }

    assert result == {
        "shop_id": context.shop.shop_id,
        "artifact_id": report_payload["artifact_id"],
        "trial_provider_profile": "pilot-2026-04",
        "applied_rules": {
            "low_confidence_threshold": 0.9,
            "require_price_confirmation": True,
            "require_new_item_confirmation": True,
        },
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"trial_provider_profile": "pilot-2026-04"},
        {
            "artifact_id": "artifact_missing_rules",
            "trial_provider_profile": "pilot-2026-04",
            "recommended_shop_rules": {},
        },
        {
            "artifact_id": "artifact_bad_type",
            "trial_provider_profile": "pilot-2026-04",
            "recommended_shop_rules": {"low_confidence_threshold": "high"},
        },
        {
            "artifact_id": "artifact_unknown_rule",
            "trial_provider_profile": "pilot-2026-04",
            "recommended_shop_rules": {"unsupported_rule": True},
        },
    ],
)
def test_apply_trial_calibration_rejects_malformed_or_incomplete_artifacts(
    db_session,
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    module = _load_apply_script_module()
    context = ensure_default_context(db_session)
    report_path = tmp_path / "invalid_report.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.TrialCalibrationApplyError):
        module.apply_trial_calibration(
            report_path=report_path,
            shop_id=context.shop.shop_id,
            actor_id="owner_default",
            db_session=db_session,
        )


def test_apply_trial_calibration_rejects_unknown_shop_id(
    db_session,
    tmp_path: Path,
) -> None:
    module = _load_apply_script_module()
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "artifact_id": "artifact-unknown-shop",
                "trial_provider_profile": "pilot-2026-04",
                "recommended_shop_rules": {
                    "low_confidence_threshold": 0.9,
                    "require_price_confirmation": True,
                    "require_new_item_confirmation": True,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.TrialCalibrationApplyError, match="shop"):
        module.apply_trial_calibration(
            report_path=report_path,
            shop_id="shop_missing",
            actor_id="owner_default",
            db_session=db_session,
        )
