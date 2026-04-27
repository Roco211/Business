from __future__ import annotations

from app.services.v2_main_agent import DeepSeekMainAgent


def test_main_agent_parse_textual_deepseek_tool_plan_fallback():
    agent = DeepSeekMainAgent(llm_service=None)

    plan = agent._parse_plan(
        """好的老板，我先从库存和销售两个维度扫描一下当前的风险点。工具调用如下：
1. `query_low_stock_alerts()` – 检查缺货或积压预警
2. `query_revenue(days=30)` – 查看近30天营收是否异常波动
3. `query_sales_ranking(days=30, limit=5)` – 看热销榜单有无剧烈变化
""",
        "我想知道这个店现在有什么经营风险需要注意？",
    )

    assert plan.intent_type == "alert_query"
    assert plan.employee_role["name"] == "库存守护员"
    assert [tool.tool_name for tool in plan.tool_calls] == [
        "query_low_stock_alerts",
        "query_revenue",
        "query_sales_ranking",
    ]
