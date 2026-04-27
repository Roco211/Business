"""DeepSeek Main Agent — 主调度Agent，负责意图理解、工具规划、响应合成。

架构：
- DeepSeek 作为"小雅"（运营协调官），是用户的第一接触点
- 小雅理解用户意图后，决定调用哪些工具/Subagent
- 工具执行结果是确定性的，小雅负责把结果合成为自然语言回复
- 涉及写操作时，小雅生成待确认草稿，不直接落账
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.llm_real_provider import LLMProviderError, create_llm_provider
from app.services.v2_llm import LLMService, ParsedIntent

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolCall:
    """A planned tool call by the Main Agent."""
    tool_name: str  # e.g. "query_inventory", "query_revenue", "draft_stock_in"
    parameters: dict[str, Any]
    reasoning: str  # Why this tool is needed


@dataclass(frozen=True)
class AgentPlan:
    """Execution plan produced by the Main Agent."""
    intent_type: str
    employee_role: dict[str, str]  # {"name": "库存守护员", "color": "#10B981", "badge": "库存"}
    tool_calls: list[ToolCall]
    needs_confirmation: bool  # Whether any write operation needs user confirmation
    direct_reply: str | None  # If no tools needed, reply directly


@dataclass(frozen=True)
class AgentResponse:
    """Final synthesized response from the Main Agent."""
    content: str
    employee_role: dict[str, str]
    intent_type: str
    tool_results: list[dict[str, Any]]  # Raw tool results for debugging
    confidence: float


class DeepSeekMainAgent:
    """DeepSeek-powered Main Agent (小雅/运营协调官).

    职责：
    1. 理解用户自然语言输入（支持复杂、模糊、多条件意图）
    2. 规划需要调用的工具链
    3. 合成最终回复

    设计原则：
    - AI 负责理解和编排
    - 系统负责权限、约束、确认、落账、审计
    - AI 不能直接修改业务真相
    - 不确定性必须进入追问、确认、拒绝或纠错工作流
    """

    SYSTEM_PROMPT = """你是"小雅"，五金店的AI运营协调官。你的职责是理解老板的自然语言指令，规划执行步骤，并协调各个专业AI员工完成任务。

可协调的专业员工：
- 营业数据员：负责营业额、营收、利润、交易数据查询
- 销售分析员：负责热销排行、销量分析、趋势分析
- 库存守护员：负责库存查询、入库、出库、库存预警
- 价格参谋：负责商品价格、定价建议
- AI参谋：负责一般性经营建议、问题解答

规则：
1. 像真人经营助手一样理解自然语言，不要说"不理解"
2. 如果缺少条件，用一句自然问题追问，不要要求固定格式
3. 涉及开单、入库、出库、采购等写操作时，说明会先生成待确认草稿，老板确认后才落账
4. 回答简短、具体、中文
5. 不要编造数据，只能基于工具返回的真实数据回答

可用工具：
- query_inventory(item_name): 查询商品库存
- query_revenue(days=30): 查询营业额摘要
- query_sales_ranking(days=30, limit=5): 查询热销排行
- query_low_stock_alerts(): 查询库存预警
- draft_stock_in(item_name, quantity): 生成入库待确认草稿
- draft_stock_out(item_name, quantity): 生成出库待确认草稿
- general_chat(): 一般性对话，不需要工具

输出格式（JSON）：
{
  "intent_type": "stock_query|revenue_query|sales_query|alert_query|stock_in|stock_out|price_query|general_chat",
  "employee": "库存守护员|营业数据员|销售分析员|价格参谋|AI参谋",
  "thinking": "你的思考过程",
  "tools": [
    {"tool": "工具名", "params": {}, "reason": "为什么调用"}
  ],
  "needs_confirmation": true|false,
  "direct_reply": null  // 如果不需要工具，直接回复的内容
}"""

    RESPONSE_SYNTHESIS_PROMPT = """你是"小雅"，五金店AI运营协调官。基于工具返回的真实业务数据，用中文简洁回复老板。

规则：
1. 不能编造数据，只能解释输入里的真实数据
2. 查询类直接给结论和下一步建议
3. 写操作必须提醒需要老板确认后才落账
4. 如果信息不足，自然追问一个最关键的问题
5. 回答简短、具体、中文，像真人助手说话"""

    def __init__(self, llm_service: LLMService | None = None):
        self._llm_service = llm_service
        self._provider = getattr(llm_service, "provider", None) if llm_service else None

    def _get_provider(self):
        if self._provider is None:
            self._provider = create_llm_provider()
        return self._provider

    def plan(
        self,
        user_message: str,
        db_session: Session | None = None,
        history: list[dict] | None = None,
    ) -> AgentPlan:
        """理解用户意图并生成执行计划。

        Args:
            user_message: 用户的自然语言输入
            db_session: 可选的数据库会话
            history: 可选的对话历史

        Returns:
            AgentPlan: 包含意图类型、员工角色、工具调用计划
        """
        rule_intent = self._rule_based_intent(user_message)

        # Compatibility path for injected test doubles: production get_llm_service()
        # never returns without a real provider, but unit tests may pass a fake
        # service to verify routing without external network calls.
        if self._provider is None and self._llm_service is not None and hasattr(self._llm_service, "parse_intent"):
            service_intent = self._llm_service.parse_intent(user_message, db_session, history=history)
            if service_intent.intent_type == "unknown" and hasattr(self._llm_service, "generate_general_reply"):
                generated = self._llm_service.generate_general_reply(
                    original_text=user_message,
                    intent_type=service_intent.intent_type,
                    history=history,
                )
                return AgentPlan(
                    intent_type="general_chat",
                    employee_role=self._get_employee_role("general_chat"),
                    tool_calls=[],
                    needs_confirmation=False,
                    direct_reply=generated.content,
                )
            return self._plan_from_rule(service_intent, user_message)

        # Fast path: 高置信度的规则匹配，避免简单查询也走 LLM
        if rule_intent.confidence >= 0.85 and rule_intent.intent_type != "unknown":
            return self._plan_from_rule(rule_intent, user_message)

        # DeepSeek reasoning path: 复杂意图用 LLM 深度理解
        try:
            provider = self._get_provider()

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
            ]
            if history:
                messages.extend(history[-4:])

            messages.append({"role": "user", "content": f"老板说：{user_message}\n请分析意图并规划工具调用。"})

            response = provider.chat(messages, stream=False, max_tokens=800)
            content = response.content

            # Parse JSON plan
            plan = self._parse_plan(content, user_message)
            return plan

        except (LLMProviderError, ValueError) as exc:
            logger.error("DeepSeek planning failed: %s", getattr(exc, "message", str(exc)))
            # Fallback to rule-based plan
            return self._plan_from_rule(rule_intent, user_message)

    def synthesize(
        self,
        *,
        user_message: str,
        plan: AgentPlan,
        tool_results: list[dict[str, Any]],
        history: list[dict] | None = None,
    ) -> AgentResponse:
        """合成最终回复。

        Args:
            user_message: 原始用户输入
            plan: 执行计划
            tool_results: 工具执行结果列表
            history: 可选的对话历史

        Returns:
            AgentResponse: 包含合成后的回复内容
        """
        # Compatibility path for injected test doubles only; production services always carry a provider.
        if tool_results and self._provider is None and self._llm_service is not None and hasattr(self._llm_service, "generate_business_response"):
            generated = self._llm_service.generate_business_response(
                query_result=tool_results[0] if tool_results else {},
                original_text=user_message,
                intent_type=plan.intent_type,
                history=history,
            )
            return AgentResponse(
                content=generated.content,
                employee_role=plan.employee_role,
                intent_type=plan.intent_type,
                tool_results=tool_results,
                confidence=getattr(generated, "confidence", 0.88),
            )

        # Fast path: 确定性高频查询直接回复，不走 LLM
        if self._should_use_fast_reply(plan, tool_results):
            content = self._build_fast_reply(plan, tool_results)
            return AgentResponse(
                content=content,
                employee_role=plan.employee_role,
                intent_type=plan.intent_type,
                tool_results=tool_results,
                confidence=0.82,
            )

        # DeepSeek synthesis path
        try:
            provider = self._get_provider()

            # Build context from tool results
            tool_context = json.dumps(tool_results, ensure_ascii=False, default=str)

            messages = [
                {"role": "system", "content": self.RESPONSE_SYNTHESIS_PROMPT},
            ]
            if history:
                messages.extend(history[-4:])

            messages.append({
                "role": "user",
                "content": (
                    f"老板原话：{user_message}\n"
                    f"识别意图：{plan.intent_type}\n"
                    f"真实业务数据JSON：{tool_context}\n"
                    f"需要确认：{'是' if plan.needs_confirmation else '否'}\n"
                    "请基于真实数据回复老板。"
                ),
            })

            response = provider.chat(messages, stream=False, max_tokens=600)

            return AgentResponse(
                content=response.content.strip(),
                employee_role=plan.employee_role,
                intent_type=plan.intent_type,
                tool_results=tool_results,
                confidence=0.9,
            )

        except LLMProviderError as exc:
            logger.error("DeepSeek synthesis failed: %s", exc.message)
            content = self._build_fast_reply(plan, tool_results)
            return AgentResponse(
                content=content,
                employee_role=plan.employee_role,
                intent_type=plan.intent_type,
                tool_results=tool_results,
                confidence=0.7,
            )

    def _parse_plan(self, content: str, user_message: str) -> AgentPlan:
        """Parse LLM response into AgentPlan."""
        try:
            # Extract JSON
            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}")
                if json_start >= 0 and json_end > json_start:
                    content = content[json_start:json_end + 1]

            result = json.loads(content)

            intent_type = result.get("intent_type", "unknown")
            employee_name = result.get("employee", "AI参谋")
            tools_data = result.get("tools", [])
            needs_confirmation = result.get("needs_confirmation", False)
            direct_reply = result.get("direct_reply")
            thinking = result.get("thinking", "")

            # Map employee name to role dict
            employee_role = self._get_employee_role(intent_type, employee_name)

            # Parse tool calls
            tool_calls = []
            for t in tools_data:
                tool_calls.append(ToolCall(
                    tool_name=t.get("tool", "general_chat"),
                    parameters=t.get("params", {}),
                    reasoning=t.get("reason", ""),
                ))

            # If no tools planned but intent is clear, infer from intent_type
            if not tool_calls and intent_type != "general_chat":
                tool_calls = self._infer_tools_from_intent(intent_type, result)

            logger.info(
                "DeepSeek plan: intent=%s employee=%s tools=%s thinking=%s",
                intent_type,
                employee_name,
                [t.tool_name for t in tool_calls],
                thinking[:100],
            )

            return AgentPlan(
                intent_type=intent_type,
                employee_role=employee_role,
                tool_calls=tool_calls,
                needs_confirmation=needs_confirmation,
                direct_reply=direct_reply,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse DeepSeek plan JSON, trying textual tool-plan fallback")
            textual_plan = self._parse_textual_plan(content, user_message)
            if textual_plan is not None:
                return textual_plan
            rule_intent = self._rule_based_intent(user_message)
            return self._plan_from_rule(rule_intent, user_message)

    def _parse_textual_plan(self, content: str, user_message: str) -> AgentPlan | None:
        """Best-effort parser for DeepSeek responses that describe tools in prose."""
        tool_order = [
            ("query_low_stock_alerts", "alert_query", {}, "查询库存预警"),
            ("query_revenue", "revenue_query", {"days": 30}, "查询营业额摘要"),
            ("query_sales_ranking", "sales_query", {"days": 30, "limit": 5}, "查询热销排行"),
            ("query_inventory", "stock_query", {}, "查询商品库存"),
            ("draft_stock_in", "stock_in", {}, "生成入库草稿"),
            ("draft_stock_out", "stock_out", {}, "生成出库草稿"),
        ]
        tool_calls: list[ToolCall] = []
        primary_intent: str | None = None
        for tool_name, intent_type, params, reason in tool_order:
            if tool_name in content:
                if primary_intent is None:
                    primary_intent = intent_type
                tool_calls.append(ToolCall(tool_name=tool_name, parameters=dict(params), reasoning=reason))

        if not tool_calls:
            return None

        intent_type = primary_intent or "general_chat"
        return AgentPlan(
            intent_type=intent_type,
            employee_role=self._get_employee_role(intent_type),
            tool_calls=tool_calls,
            needs_confirmation=any(t.tool_name.startswith("draft_") for t in tool_calls),
            direct_reply=None,
        )

    def _rule_based_intent(self, text: str) -> ParsedIntent:
        """Fast rule-based intent for fallback and simple queries."""
        # Delegate to existing rule-based logic
        from app.services.v2_llm import LLMService
        service = LLMService(provider=None)  # provider is not needed for local rule parsing
        return service._rule_based_parse_intent(text)

    def _plan_from_rule(self, intent: ParsedIntent, user_message: str) -> AgentPlan:
        """Generate plan from rule-based intent."""
        employee_role = self._get_employee_role(intent.intent_type)
        tool_calls = self._infer_tools_from_intent(intent.intent_type, {
            "item_name": intent.item_name,
            "quantity": intent.quantity,
        })

        needs_confirmation = intent.intent_type in ("stock_in", "stock_out")

        return AgentPlan(
            intent_type=intent.intent_type,
            employee_role=employee_role,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            direct_reply=None,
        )

    def _infer_tools_from_intent(self, intent_type: str, params: dict) -> list[ToolCall]:
        """Infer tool calls from intent type."""
        item_name = params.get("item_name")
        quantity = params.get("quantity")

        if intent_type == "stock_query" and item_name:
            return [ToolCall("query_inventory", {"item_name": item_name}, "查询商品库存")]
        if intent_type == "revenue_query":
            return [ToolCall("query_revenue", {"days": 30}, "查询营业额摘要")]
        if intent_type == "sales_query":
            return [ToolCall("query_sales_ranking", {"days": 30, "limit": 5}, "查询热销排行")]
        if intent_type == "alert_query":
            return [ToolCall("query_low_stock_alerts", {}, "查询库存预警")]
        if intent_type == "stock_in" and item_name and quantity:
            return [ToolCall("draft_stock_in", {"item_name": item_name, "quantity": quantity}, "生成入库草稿")]
        if intent_type == "stock_out" and item_name and quantity:
            return [ToolCall("draft_stock_out", {"item_name": item_name, "quantity": quantity}, "生成出库草稿")]

        return []

    def _get_employee_role(self, intent_type: str, employee_name: str | None = None) -> dict[str, str]:
        """Get employee role info."""
        roles = {
            "stock_query": {"name": "库存守护员", "color": "#10B981", "badge": "库存"},
            "stock_in": {"name": "库存守护员", "color": "#10B981", "badge": "入库"},
            "stock_out": {"name": "库存守护员", "color": "#10B981", "badge": "出库"},
            "price_query": {"name": "价格参谋", "color": "#F59E0B", "badge": "价格"},
            "sales_query": {"name": "销售分析员", "color": "#3B82F6", "badge": "销售"},
            "revenue_query": {"name": "营业数据员", "color": "#8B5CF6", "badge": "营收"},
            "alert_query": {"name": "库存守护员", "color": "#EF4444", "badge": "预警"},
            "general_chat": {"name": "AI参谋", "color": "#6B7280", "badge": "助手"},
            "unknown": {"name": "AI参谋", "color": "#6B7280", "badge": "助手"},
        }

        # If employee_name is provided, try to match
        if employee_name:
            name_map = {
                "库存守护员": {"name": "库存守护员", "color": "#10B981", "badge": "库存"},
                "营业数据员": {"name": "营业数据员", "color": "#8B5CF6", "badge": "营收"},
                "销售分析员": {"name": "销售分析员", "color": "#3B82F6", "badge": "销售"},
                "价格参谋": {"name": "价格参谋", "color": "#F59E0B", "badge": "价格"},
                "AI参谋": {"name": "AI参谋", "color": "#6B7280", "badge": "助手"},
            }
            if employee_name in name_map:
                return name_map[employee_name]

        return roles.get(intent_type, roles["unknown"])

    def _should_use_fast_reply(self, plan: AgentPlan, tool_results: list[dict]) -> bool:
        """Return True for high-frequency deterministic queries."""
        if plan.direct_reply and not tool_results:
            return True
        if any(result.get("type") in {"stock_tx_pending", "stock_tx_error", "stock_not_found"} for result in tool_results):
            return True
        if plan.intent_type in {"revenue_query", "sales_query", "alert_query"}:
            return True
        if plan.intent_type == "stock_query" and tool_results:
            return True
        return False

    def _build_fast_reply(self, plan: AgentPlan, tool_results: list[dict]) -> str:
        """Build deterministic reply without LLM."""
        if not tool_results:
            if plan.direct_reply:
                return plan.direct_reply
            return "请问有什么可以帮您的？"

        result = tool_results[-1] if tool_results[-1].get("type") in {"stock_tx_pending", "stock_tx_error"} else tool_results[0]

        if result.get("type") == "stock_tx_error":
            if result.get("error") == "库存不足":
                return (
                    f"库存不足，{result.get('item_name', '该商品')}当前只有"
                    f"{result.get('current_quantity', 0):.0f}{result.get('unit', '个')}，"
                    f"不能出库{result.get('requested_quantity', 0)}{result.get('unit', '个')}。"
                )
            return f"操作失败：{result.get('error', '请稍后重试')}"

        if result.get("type") == "stock_tx_pending":
            return (
                f"已生成{result.get('action', '库存操作')}待确认单，请确认后再落账。\n"
                f"商品：{result.get('item_name')}\n"
                f"数量：{result.get('quantity')}{result.get('unit', '个')}\n"
                f"确认单：{result.get('confirmation_id')}"
            )

        if result.get("type") == "stock_not_found":
            return f"未找到商品“{result.get('item_name', '')}”，请确认商品名称是否正确。"
        if plan.intent_type == "revenue_query" and result.get("type") == "revenue_summary":
            return (
                f"过去30天营业额为¥{result.get('total_revenue', 0):.2f}，"
                f"毛利润¥{result.get('gross_profit', 0):.2f}，"
                f"共{result.get('transaction_count', 0)}笔交易。"
            )

        if plan.intent_type == "sales_query" and result.get("ranking"):
            top = result["ranking"][0]
            return f"过去30天卖得最好的是{top['item_name']}，售出{top['total_sold']:.0f}件，销售额¥{top['total_revenue']:.2f}。"

        if plan.intent_type == "alert_query":
            count = result.get("count", 0)
            if count:
                first = result["alerts"][0]
                return f"当前有{count}个库存预警，最需要关注的是{first['item_name']}，还剩{first['current_quantity']}{first['unit']}。"
            return "当前没有库存预警，库存状态整体正常。"

        if plan.intent_type == "stock_query" and result.get("type") == "stock":
            return f"{result['item_name']}当前库存{result['quantity']:.0f}{result['unit']}。"

        return json.dumps(result, ensure_ascii=False, default=str)[:200]


# Singleton
_main_agent: DeepSeekMainAgent | None = None


def get_main_agent() -> DeepSeekMainAgent:
    """Get the global DeepSeek Main Agent singleton."""
    global _main_agent
    if _main_agent is None:
        from app.services.v2_llm import get_llm_service
        llm_service = get_llm_service()
        _main_agent = DeepSeekMainAgent(llm_service=llm_service)
    return _main_agent


def reset_main_agent() -> None:
    """Reset the singleton (for testing)."""
    global _main_agent
    _main_agent = None
