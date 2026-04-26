from pathlib import Path

APP_TSX = Path("apps/h5/src/App.tsx")
STYLES = Path("apps/h5/src/styles.css")


def read_app() -> str:
    return APP_TSX.read_text(encoding="utf-8")


def read_styles() -> str:
    return STYLES.read_text(encoding="utf-8")


def test_data_table_has_mobile_card_fallback_with_cell_labels():
    source = read_app()
    assert "className=\"mobile-data-list\"" in source
    assert "className=\"mobile-data-card\"" in source
    assert "className=\"mobile-data-row\"" in source
    assert "<span>{columnLabel(c)}</span>" in source
    assert "className=\"desktop-table-wrap table-wrap\"" in source


def test_mobile_css_prevents_horizontal_overflow_and_makes_tables_card_like():
    css = read_styles()
    assert "html,body,#root" in css
    assert "overflow-x:hidden" in css
    assert "touch-action:manipulation" in css
    assert ".mobile-data-list" in css
    assert ".mobile-data-card" in css
    assert ".desktop-table-wrap" in css
    assert "@media(max-width:760px)" in css
    mobile = css[css.index("@media(max-width:760px)"):]
    for token in [
        ".desktop-table-wrap{display:none}",
        ".mobile-data-list{display:grid",
        ".mobile-data-row",
        ".task-actions{display:grid",
        ".post-approval-actions{display:grid",
        ".ai-next-actions>div{display:grid",
        ".ui-button{width:100%",
        "min-height:48px",
        "word-break:break-word",
    ]:
        assert token in mobile


def test_mobile_ai_and_task_actions_use_design_system_buttons():
    source = read_app()
    tasks_start = source.index("function TasksPage")
    tasks_end = source.index("type ExecutionResult", tasks_start)
    tasks = source[tasks_start:tasks_end]
    assert "<UiButton variant=\"primary\"" in tasks
    assert "<UiButton variant=\"secondary\"" in tasks
    assert "post-approval-actions" in tasks
    assert "task-actions" in tasks
