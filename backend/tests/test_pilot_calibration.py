from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_load_manifest_rejects_unknown_capability(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "cases": [
                    {
                        "case_id": "bad-capability",
                        "capability": "barcode",
                        "media_path": "fixtures/barcode.jpg",
                        "expected": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="capability"):
        load_manifest(manifest_path)


@pytest.mark.parametrize("field_name", ["trial_id", "case_id"])
def test_load_manifest_rejects_empty_ids(tmp_path: Path, field_name: str) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    payload = {
        "trial_id": "pilot-2026-04-06",
        "cases": [
            {
                "case_id": "case-1",
                "capability": "asr",
                "media_path": "fixtures/voice.m4a",
                "expected": {},
            }
        ],
    }
    if field_name == "trial_id":
        payload["trial_id"] = ""
    else:
        payload["cases"][0]["case_id"] = ""

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match=field_name):
        load_manifest(manifest_path)


def test_load_manifest_rejects_missing_expected(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "cases": [
                    {
                        "case_id": "missing-expected",
                        "capability": "asr",
                        "media_path": "fixtures/voice.m4a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="expected"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_invalid_asr_expected_shape(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "cases": [
                    {
                        "case_id": "invalid-asr-expected",
                        "capability": "asr",
                        "media_path": "fixtures/voice.m4a",
                        "expected": {
                            "transcript_contains": "cola",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="transcript_contains"):
        load_manifest(manifest_path)


def test_load_manifest_wraps_invalid_numeric_expected_as_manifest_error(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "cases": [
                    {
                        "case_id": "invalid-min-confidence",
                        "capability": "asr",
                        "media_path": "fixtures/voice.m4a",
                        "expected": {
                            "min_confidence": "nope",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="min_confidence"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_extra_properties(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import ManifestValidationError, load_manifest

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "unexpected_root": True,
                "cases": [
                    {
                        "case_id": "has-extra-field",
                        "capability": "ocr",
                        "media_path": "fixtures/receipt.jpg",
                        "expected": {},
                        "extra_case_field": 123,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="Extra inputs are not permitted"):
        load_manifest(manifest_path)


def test_run_pilot_calibration_dispatches_and_aggregates(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import run_pilot_calibration

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    asr_file = media_dir / "voice.m4a"
    ocr_file = media_dir / "receipt.jpg"
    vision_file = media_dir / "shelf.jpg"
    asr_file.write_bytes(b"asr")
    ocr_file.write_bytes(b"ocr")
    vision_file.write_bytes(b"vision")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-2026-04-06",
                "cases": [
                    {
                        "case_id": "asr-pass",
                        "capability": "asr",
                        "media_path": str(asr_file),
                        "expected": {
                            "transcript_contains": ["cola"],
                            "min_confidence": 0.8,
                        },
                    },
                    {
                        "case_id": "ocr-warn",
                        "capability": "ocr",
                        "media_path": str(ocr_file),
                        "expected": {"total_amount": 13.0, "amount_tolerance": 0.5},
                    },
                    {
                        "case_id": "vision-fail",
                        "capability": "vision",
                        "media_path": str(vision_file),
                        "expected": {
                            "top_candidate_in": ["Red Bull 250ml"],
                            "min_confidence": 0.9,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, Path]] = []

    def _fake_asr(*, audio_path: Path, media_id: str | None, text_hint: str | None):
        assert media_id is None
        assert text_hint is None
        calls.append(("asr", audio_path))
        return {
            "transcript": "please check cola stock",
            "confidence": 0.96,
            "provider_name": "stub-asr",
            "used_fallback": False,
            "latency_ms": 80,
        }

    def _fake_ocr(*, file_path: Path):
        calls.append(("ocr", file_path))
        return {
            "provider_name": "stub-ocr",
            "used_fallback": True,
            "total_amount": 13.0,
            "line_items": [],
            "low_confidence_fields": ["items[0].price"],
            "latency_ms": 140,
        }

    def _fake_vision(*, file_path: Path):
        calls.append(("vision", file_path))
        return {
            "provider_name": "stub-vision",
            "used_fallback": False,
            "candidates": [
                {
                    "item_name": "Unknown Drink",
                    "confidence": 0.52,
                    "packaging_hint": "can",
                }
            ],
            "latency_ms": 200,
        }

    result = run_pilot_calibration(
        manifest_path=manifest_path,
        output_dir=tmp_path / "artifacts",
        evaluate_asr=_fake_asr,
        evaluate_ocr=_fake_ocr,
        evaluate_vision=_fake_vision,
    )

    assert calls == [("asr", asr_file), ("ocr", ocr_file), ("vision", vision_file)]
    assert result["summary"] == {
        "total_cases": 3,
        "pass": 1,
        "warn": 1,
        "fail": 1,
        "fallback_count": 1,
        "low_confidence_count": 2,
    }
    assert result["latency_ms"] == {"min": 80, "max": 200, "avg": 140, "p95": 200}
    assert result["failure_buckets"] == {
        "used_fallback": 1,
        "low_confidence_signal": 1,
        "top_candidate_mismatch": 1,
    }

    json_report_path = Path(result["json_report_path"])
    markdown_report_path = Path(result["markdown_report_path"])
    assert json_report_path.is_file()
    assert markdown_report_path.is_file()

    report_payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    assert report_payload["summary"]["warn"] == 1
    assert report_payload["cases"][2]["outcome"] == "fail"

    markdown = markdown_report_path.read_text(encoding="utf-8")
    assert "# Pilot Calibration Report" in markdown
    assert "| pass | warn | fail |" in markdown
    assert "| 1 | 1 | 1 |" in markdown


def test_run_pilot_calibration_continues_after_case_evaluation_failure(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import run_pilot_calibration

    asr_file = tmp_path / "voice.m4a"
    ocr_file = tmp_path / "receipt.jpg"
    asr_file.write_bytes(b"asr")
    ocr_file.write_bytes(b"ocr")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-continues-on-error",
                "cases": [
                    {
                        "case_id": "asr-fails",
                        "capability": "asr",
                        "media_path": str(asr_file),
                        "expected": {},
                    },
                    {
                        "case_id": "ocr-pass",
                        "capability": "ocr",
                        "media_path": str(ocr_file),
                        "expected": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    calls: list[str] = []

    def _failing_asr(**_: object) -> dict[str, object]:
        calls.append("asr")
        raise FileNotFoundError("missing media fixture")

    def _passing_ocr(**_: object) -> dict[str, object]:
        calls.append("ocr")
        return {
            "provider_name": "stub-ocr",
            "used_fallback": False,
            "total_amount": 13.0,
            "line_items": [],
            "low_confidence_fields": [],
            "latency_ms": 4,
        }

    result = run_pilot_calibration(
        manifest_path=manifest_path,
        output_dir=tmp_path / "artifacts",
        evaluate_asr=_failing_asr,
        evaluate_ocr=_passing_ocr,
        evaluate_vision=lambda **_: {},
    )

    assert calls == ["asr", "ocr"]
    assert result["summary"]["total_cases"] == 2
    assert result["summary"]["fail"] == 1
    assert result["summary"]["pass"] == 1
    assert result["failure_buckets"] == {"evaluation_error": 1}
    assert Path(result["json_report_path"]).is_file()
    assert Path(result["markdown_report_path"]).is_file()

    report_payload = json.loads(Path(result["json_report_path"]).read_text(encoding="utf-8"))
    assert report_payload["cases"][0]["outcome"] == "fail"
    assert report_payload["cases"][0]["reasons"] == ["evaluation_error"]
    assert report_payload["cases"][1]["outcome"] == "pass"


def test_run_pilot_calibration_defaults_artifacts_to_private_devdata(tmp_path: Path) -> None:
    from app.devtools.pilot_calibration import DEFAULT_ARTIFACTS_DIR, run_pilot_calibration

    media_path = tmp_path / "voice.m4a"
    media_path.write_bytes(b"asr")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-private-default",
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

    result = run_pilot_calibration(
        manifest_path=manifest_path,
        evaluate_asr=lambda **_: {
            "transcript": "cola in stock",
            "confidence": None,
            "provider_name": "stub-asr",
            "used_fallback": False,
            "latency_ms": 1,
        },
        evaluate_ocr=lambda **_: {},
        evaluate_vision=lambda **_: {},
    )

    report_path = Path(result["json_report_path"])
    assert report_path.parent == DEFAULT_ARTIFACTS_DIR
    assert str(report_path).startswith(str(DEFAULT_ARTIFACTS_DIR))
    assert "fixtures/provider_calibration" not in str(report_path).replace("\\", "/")


def test_run_pilot_calibration_uses_configured_default_artifact_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.devtools.pilot_calibration import run_pilot_calibration

    configured_dir = tmp_path / "configured-artifacts"
    monkeypatch.setenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", str(configured_dir))

    media_path = tmp_path / "voice.m4a"
    media_path.write_bytes(b"asr")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trial_id": "pilot-configured-default",
                "cases": [
                    {
                        "case_id": "asr-pass",
                        "capability": "asr",
                        "media_path": str(media_path),
                        "expected": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_pilot_calibration(
        manifest_path=manifest_path,
        evaluate_asr=lambda **_: {
            "transcript": "ok",
            "confidence": None,
            "provider_name": "stub-asr",
            "used_fallback": False,
            "latency_ms": 1,
        },
        evaluate_ocr=lambda **_: {},
        evaluate_vision=lambda **_: {},
    )

    assert Path(result["json_report_path"]).parent == configured_dir
    assert Path(result["markdown_report_path"]).parent == configured_dir


def test_fixture_example_manifest_is_valid() -> None:
    from app.devtools.pilot_calibration import load_manifest

    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "provider_calibration"
        / "example_manifest.json"
    )
    manifest = load_manifest(fixture_path)

    assert manifest.trial_id == "example-live-trial-calibration"
    assert len(manifest.cases) == 3


def test_manifest_schema_tracks_capability_specific_expected_contract() -> None:
    schema_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "provider_calibration"
        / "manifest.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    case_schema = schema["properties"]["cases"]["items"]
    conditional_rules = case_schema.get("allOf", [])

    assert conditional_rules, "schema must encode capability-specific expected rules"

    asr_rule = next(
        rule
        for rule in conditional_rules
        if rule.get("if", {}).get("properties", {}).get("capability", {}).get("const") == "asr"
    )
    asr_expected = asr_rule["then"]["properties"]["expected"]
    assert asr_expected["additionalProperties"] is False
    assert asr_expected["properties"]["transcript_contains"]["type"] == "array"
    assert asr_expected["properties"]["min_confidence"]["type"] == "number"

    ocr_rule = next(
        rule
        for rule in conditional_rules
        if rule.get("if", {}).get("properties", {}).get("capability", {}).get("const") == "ocr"
    )
    ocr_expected = ocr_rule["then"]["properties"]["expected"]
    assert ocr_expected["additionalProperties"] is False
    assert ocr_expected["properties"]["amount_tolerance"]["minimum"] == 0

    vision_rule = next(
        rule
        for rule in conditional_rules
        if rule.get("if", {}).get("properties", {}).get("capability", {}).get("const") == "vision"
    )
    vision_expected = vision_rule["then"]["properties"]["expected"]
    assert vision_expected["additionalProperties"] is False
    assert vision_expected["properties"]["top_candidate_in"]["type"] == "array"
