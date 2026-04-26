from pathlib import Path

APP = Path("apps/h5/src/App.tsx")
CSS = Path("apps/h5/src/styles.css")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def css() -> str:
    return CSS.read_text(encoding="utf-8")


def block(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def test_mobile_navigation_is_explicit_bottom_nav_with_safe_area():
    app = source()
    styles = css()
    shell = block(app, '<div className="app-shell">', '<main className="main-panel">')

    assert 'mobile-bottom-nav' in shell
    assert 'aria-label="主要导航"' in shell
    assert 'safe-area-inset-bottom' in styles
    assert '.mobile-bottom-nav' in styles
    assert 'backdrop-filter:blur' in styles
    assert 'padding-bottom:calc(104px + env(safe-area-inset-bottom))' in styles


def test_mobile_primary_nav_keeps_five_finger_targets_and_hides_secondary_more():
    styles = css()

    assert 'grid-template-columns:repeat(5,minmax(0,1fr))' in styles
    assert '.mobile-bottom-nav .nav-item{min-height:58px' in styles
    assert '.mobile-bottom-nav .nav-item:nth-child(n+6){display:none}' in styles
    assert '.mobile-bottom-nav .nav-badge{display:none}' in styles


def test_mobile_ai_workflow_is_single_column_and_keyboard_friendly():
    styles = css()

    for token in [
        '.mobile-ai-sticky-input',
        '.command-input-row.mobile-ai-sticky-input',
        'position:sticky',
        'bottom:calc(76px + env(safe-area-inset-bottom))',
        '.inline-confirm-actions{display:grid',
        '.draft-preview-grid{grid-template-columns:1fr',
        '.business-insight-card{padding:12px',
    ]:
        assert token in styles


def test_mobile_action_buttons_are_large_full_width_for_boss_confirmation():
    styles = css()

    for selector in [
        '.inline-confirm-actions .ui-button',
        '.boss-brief-actions .ui-button',
        '.task-actions .ui-button',
        '.ai-next-actions .ui-button',
    ]:
        assert selector in styles
    assert 'min-height:52px' in styles
    assert 'width:100%' in styles
