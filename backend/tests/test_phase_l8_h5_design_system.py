from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_TSX = ROOT / "apps" / "h5" / "src" / "App.tsx"
UI_TSX = ROOT / "apps" / "h5" / "src" / "ui.tsx"
STYLES = ROOT / "apps" / "h5" / "src" / "styles.css"


def test_design_system_components_exist_and_are_typed():
    assert UI_TSX.exists(), "H5 should have a small shared design-system component layer"
    source = UI_TSX.read_text(encoding="utf-8")

    for name in ["UiButton", "UiCard", "UiBadge", "UiTextArea"]:
        assert f"export function {name}" in source

    assert "variant?: 'primary' | 'secondary' | 'ghost' | 'text'" in source
    assert "tone?: 'default' | 'ai' | 'success' | 'warning' | 'danger'" in source
    assert "forwardedClassName" not in source, "components should expose className, not ad-hoc prop names"


def test_dashboard_uses_design_system_for_high_traffic_ai_surface():
    source = APP_TSX.read_text(encoding="utf-8")

    assert "from './ui'" in source
    assert source.count("<UiButton") >= 8
    assert source.count("<UiBadge") >= 3
    assert "<UiTextArea" in source
    assert "function Panel" in source and "<UiCard className=\"panel\"" in source
    assert "className={`ai-badge" not in source


def test_design_system_css_unifies_controls_without_breaking_legacy_classes():
    css = STYLES.read_text(encoding="utf-8")

    for class_name in [".ui-button", ".ui-button.primary", ".ui-button.secondary", ".ui-button.ghost", ".ui-button.text", ".ui-card", ".ui-badge", ".ui-textarea"]:
        assert class_name in css

    assert ".primary-button,.secondary-button" in css, "legacy button classes must keep compatibility while gradually migrating"
    assert ".ui-button:focus-visible" in css
    assert ".ui-textarea:focus" in css
    assert "min-height:44px" in css
