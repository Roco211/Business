from pathlib import Path

APP = Path("apps/h5/src/App.tsx")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def between(source: str, start: str, end: str) -> str:
    left = source.index(start)
    right = source.index(end, left)
    return source[left:right]


def test_boss_home_has_one_clear_ai_native_storyline():
    source = read_app()
    dashboard = between(source, "function Dashboard", "type CommandAction")
    assert "BossTodayBrief" in dashboard
    assert "老板，今天店里" in source
    assert "先处理待确认" in source
    assert "问AI" in source
    assert "记一笔销售" in source

    nav = between(source, "const navItems", "]\n")
    for noisy_label in ["我的员工", "经营日报", "执行复盘", "采购单", "客户复购", "财务流水", "营销/售后"]:
        assert noisy_label not in nav
    for primary_label in ["工作台", "AI助手", "任务", "销售", "商品库存", "更多"]:
        assert primary_label in nav


def test_ai_write_operation_shows_business_confirmation_card_not_raw_id_first():
    source = read_app()
    command_center = between(source, "function AiCommandCenter", "type DemoFlowStep")
    assert "draftPreview" in command_center
    assert "我准备这样记" in command_center
    assert "确认后会" in command_center
    assert "确认这笔销售" in command_center
    assert "修改这笔" in command_center
    assert "待确认任务：{result.confirmationId}" not in command_center
    assert "销售草稿 ${confirmationId}" not in command_center


def test_task_center_cards_identify_the_exact_business_task():
    source = read_app()
    tasks = between(source, "type TaskViewModel", "type ExecutionResult")
    assert "businessTitle" in tasks
    assert "刚刚创建" in tasks
    assert "电动螺丝刀 ×2" in tasks or "formatLineSummary" in tasks
    assert "合计" in tasks
    assert "确认后扣库存并记收入" in tasks
    assert "任务ID：{confirmation.confirmation_id}" not in tasks
    assert "查看技术明细" in tasks


def test_sales_page_uses_boss_language_not_database_language():
    source = read_app()
    sales = between(source, "function SalesPage", "function PurchasingPage")
    for term in ["H1 已增强", "生命周期管理", "customer_id，复购分析", "PC/H5销售单"]:
        assert term not in sales
    assert "columns={salesOrderColumns}" in sales
    assert "columns={salesOrderLineColumns}" in sales
    for label in ["今日销售记录", "订单号", "客户", "金额", "商品数", "状态", "已收款"]:
        assert label in source


def test_business_copy_removes_obvious_internal_test_or_english_status_terms():
    source = read_app()
    for term in [
        "H1 已增强",
        "H2 已增强",
        "H2/H3 已增强",
        "AI Task Flow",
        "AI sales order draft awaiting confirmation",
        "Confirmation rejected",
        "L5验收客户",
        "pending confirmation",
    ]:
        assert term not in source
    for raw_header in [">order_no<", ">customer_name<", ">total_amount<", ">items_count<", ">status<", ">paid<"]:
        assert raw_header not in source
