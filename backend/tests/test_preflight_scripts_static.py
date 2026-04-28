from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_backend_preflight_does_not_reference_deleted_tests():
    script = _read("backend/scripts/run_backend_preflight.sh")

    assert "test_v2_chat_confirmation_first.py" not in script


def test_backend_preflight_is_explicitly_local_demo_mock_only():
    script = _read("backend/scripts/run_backend_preflight.sh")

    assert "local-demo/mock preflight" in script
    assert "does not validate commercial providers" in script


def test_real_provider_preflight_exists_and_does_not_force_mock_providers():
    script = _read("backend/scripts/run_real_provider_preflight.sh")

    assert "LLM_PROVIDER=mock" not in script
    assert "OCR_PROVIDER=mock" not in script
    assert "VISION_PROVIDER=mock" not in script
    assert "production_mock_violations" in script


def test_docker_acceptance_warns_mock_local_only():
    script = _read("backend/scripts/run_docker_backend_acceptance.sh")

    assert "mock providers for local acceptance only" in script
