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


def test_dashboard_can_confirm_ai_draft_inline_without_losing_confirmation_first_boundary():
    app = source()
    center = block(app, "function AiCommandCenter", "type DemoFlowStep")

    assert "approveInlineDraft" in center
    assert "api.approveConfirmation(auth, result.confirmationId)" in center
    assert "确认并入账" in center
    assert "已完成，库存和流水已经更新" in center
    assert "查看复盘" in center
    assert "查看销售记录" in center
    assert "void runCommand(action.commandText)" in center
    assert "setCommand(action.commandText)" not in center
    assert "confirmationId" in center, "inline approval must still approve a server confirmation, not write business facts directly"
    assert "api.createSalesOrder(auth" not in center, "Dashboard AI must not bypass confirmation-first by creating orders directly"


def test_ai_query_result_is_structured_as_conclusion_evidence_next_action():
    app = source()
    center = block(app, "function AiCommandCenter", "type DemoFlowStep")

    assert "businessInsight" in center
    assert "先给结论" in center
    assert "关键依据" in center
    assert "建议下一步" in center
    assert "待确认任务堆积" in center


def test_dashboard_secondary_noise_is_collapsible_and_boss_first():
    app = source()
    dashboard = block(app, "function Dashboard", "function getKpiValue")

    assert "showMoreDashboard" in dashboard
    assert "展开更多经营细节" in dashboard
    assert "收起经营细节" in dashboard
    assert "dashboard-secondary-zone" in dashboard
    assert dashboard.index("<BossTodayBrief") < dashboard.index("<AiCommandCenter")


def test_task_center_and_ai_copy_avoid_remaining_backend_flavored_terms():
    app = source()
    center = block(app, "function AiCommandCenter", "function routeToPage")
    tasks = block(app, "function TasksPage", "type ExecutionResult")
    rendered = center + tasks
    for term in ["Command Center", "payload", "unknown", "AI sales order draft", "Confirmation rejected", "H1 已增强"]:
        assert term not in rendered
    assert "查看原始数据" not in rendered
    assert "查看系统记录" in rendered


def test_phase_ux2_styles_support_inline_completion_and_collapsed_sections():
    styles = css()
    for token in [
        ".inline-confirm-actions",
        ".completion-recap-card",
        ".business-insight-card",
        ".dashboard-secondary-zone",
        ".dashboard-more-toggle",
    ]:
        assert token in styles
