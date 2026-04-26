from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_TSX = ROOT / "apps" / "h5" / "src" / "App.tsx"


def read_app() -> str:
    return APP_TSX.read_text(encoding="utf-8")


def test_dashboard_ai_command_center_surfaces_next_step_guidance():
    source = read_app()

    assert "type CommandAction" in source
    assert "actions?: CommandAction[]" in source
    assert "ai-next-actions" in source
    assert "下一步可以这样做" in source
    assert "查看库存风险" in source
    assert "查看热销排行" in source
    assert "查看经营日报" in source


def test_dashboard_ai_draft_result_links_confirmation_and_recap_flow():
    source = read_app()

    assert "我准备这样记" in source
    assert "确认这笔销售" in source
    assert "修改这笔" in source
    assert "先看销售记录" in source
    assert "confirmations/${confirmationId}/approve" not in source, "首页 AI 入口不能绕过任务中心直接审批"


def test_dashboard_ai_query_result_keeps_user_in_ai_native_flow():
    source = read_app()

    assert "command-result-card" in source
    assert "command-journey" in source
    assert "AI已读取真实业务数据" in source
    assert "继续追问" in source
    assert "处理待确认任务" in source
