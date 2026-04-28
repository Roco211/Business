from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_TSX = ROOT / "apps" / "h5" / "src" / "App.tsx"
ENV_EXAMPLE = ROOT / "apps" / "h5" / ".env.example"


def test_h5_login_demo_values_are_gated_by_vite_demo_mode():
    source = APP_TSX.read_text(encoding="utf-8")

    assert "VITE_DEMO_MODE" in source
    assert "const DEMO_MODE" in source
    assert "useState(DEMO_MODE ? '13800000000' : '')" in source
    assert "useState(DEMO_MODE ? '888888' : '')" in source
    assert "DEMO_MODE ? '演示登录（888888）' : '登录'" in source


def test_h5_env_example_defaults_demo_mode_off():
    source = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "VITE_DEMO_MODE=0" in source
