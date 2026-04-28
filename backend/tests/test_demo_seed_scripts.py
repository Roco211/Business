import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "bootstrap_v2_trial_data.py"


def _load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("bootstrap_v2_trial_data_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_trial_data_refuses_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    module = _load_bootstrap_module()

    with pytest.raises(SystemExit) as exc:
        module.ensure_not_production()

    assert exc.value.code != 0


def test_bootstrap_trial_data_allows_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    module = _load_bootstrap_module()

    module.ensure_not_production()
