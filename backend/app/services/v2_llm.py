"""LLM service layer for intent parsing and response generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.llm_real_provider import (
    LLMProviderError,
    OpenAILLMProvider,
    create_llm_provider,
)


logger = get_logger(__name__)


@dataclass(frozen=True)
class ParsedIntent:
    """Result of intent parsing."""
    intent_type: str  # "stock_query", "stock_in", "stock_out", "unknown"
    item_name: str | None
    quantity: int | None
    confidence: float


@dataclass(frozen=True)
class GeneratedResponse:
    """Result of response generation."""
    content: str
    confidence: float


class LLMService:
    """Service for LLM-based operations."""
    
    # Optimized system prompt for speed (~30 tokens instead of 150)
    INTENT_PARSING_PROMPT = """你是店铺库存助手。从用户输入中提取意图和商品信息。

意图：stock_query(查库存), stock_in(入库), stock_out(出库), price_query(查价格), revenue_query(查营业额), sales_query(查销量), alert_query(查预警)
输出JSON格式：{"intent": "意图", "item": "商品名", "quantity": 数量}
示例：
- "螺丝刀还有几个" -> {"intent": "stock_query", "item": "螺丝刀", "quantity": null}
- "扳手多少钱" -> {"intent": "price_query", "item": "扳手", "quantity": null}
- "今天营业额多少" -> {"intent": "revenue_query", "item": null, "quantity": null}"""

    RESPONSE_PROMPT = """你是五金店AI经营助手。基于系统给出的真实业务数据，用中文简洁回答老板。
规则：
1. 不能编造数据，只能解释输入里的真实数据
2. 查询类直接给结论和下一步建议
3. 写操作必须提醒需要老板确认后才落账
4. 如果信息不足，自然追问一个最关键的问题，不要要求用户按固定格式输入"""

    GENERAL_ASSISTANT_PROMPT = """你是五金店AI经营助手，帮助个体户老板管理营业额、库存、销售、采购和待确认任务。
规则：
1. 像真人经营助手一样理解自然语言，不要说“不理解”
2. 如果缺少条件，用一句自然问题追问
3. 不要要求用户按固定格式输入
4. 涉及开单、入库、出库、采购等写操作时，说明会先生成待确认草稿，老板确认后才落账
5. 回答简短、具体、中文"""

    def __init__(self, provider: OpenAILLMProvider | None = None):
        self._provider = provider
        self._use_mock = provider is None
    
    def _get_provider(self) -> OpenAILLMProvider:
        """Lazy load provider if not provided."""
        if self._provider is None:
            self._provider = create_llm_provider()
        return self._provider
    
    def parse_intent(
        self,
        text: str,
        db_session: Session | None = None,
        history: list[dict] | None = None,
    ) -> ParsedIntent:
        """Parse user intent from transcribed text.
        
        Args:
            text: The transcribed user input
            db_session: Optional DB session for inventory lookup
            history: Optional conversation history for context-aware parsing
            
        Returns:
            ParsedIntent with type, item_name, quantity, confidence
        """
        if self._use_mock:
            intent = self._mock_parse_intent(text)
            # Apply context resolution if item_name is missing
            return self._resolve_context(intent, text, history)

        # Fast path: high-confidence operational phrases should not block on remote LLM.
        # The LLM remains available as fallback for genuinely ambiguous input, while common
        # owner questions like “今天生意怎么样” answer from deterministic business tools first.
        rule_intent = self._rule_based_parse_intent(text)
        if rule_intent.intent_type != "unknown" and rule_intent.confidence >= 0.75:
            return self._resolve_context(rule_intent, text, history)
        
        try:
            provider = self._get_provider()
            
            messages = [
                {"role": "system", "content": self.INTENT_PARSING_PROMPT},
            ]
            
            # Add history for context
            if history:
                messages.extend(history[-6:])  # Last 6 turns for context
            
            messages.append({"role": "user", "content": f"分析输入：\"{text}\""})
            
            response = provider.chat(messages, stream=False)
            content = response.content
            
            # Parse JSON response
            import json
            try:
                # Extract JSON if wrapped in markdown
                if "{" in content and "}" in content:
                    json_start = content.find("{")
                    json_end = content.rfind("}")
                    if json_start >= 0 and json_end > json_start:
                        content = content[json_start:json_end + 1]
                
                result = json.loads(content)
                
                intent_type = result.get("intent", "unknown")
                item_name = result.get("item") or result.get("item_name")
                quantity = result.get("quantity") or result.get("qty")
                
                # Convert quantity to int if present
                if quantity is not None:
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        quantity = None
                
                # Calculate confidence based on parsing success
                confidence = 0.9 if intent_type != "unknown" else 0.5
                
                intent = ParsedIntent(
                    intent_type=intent_type,
                    item_name=item_name,
                    quantity=quantity,
                    confidence=confidence,
                )
                
                # Apply context resolution
                return self._resolve_context(intent, text, history)
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON: %s", content)
                # Fallback to rule-based
                intent = self._rule_based_parse_intent(text)
                return self._resolve_context(intent, text, history)
                
        except LLMProviderError as exc:
            logger.error("LLM parse intent failed: %s", exc.message)
            # Fallback to rule-based
            intent = self._rule_based_parse_intent(text)
            return self._resolve_context(intent, text, history)
    
    def _resolve_context(
        self,
        intent: ParsedIntent,
        text: str,
        history: list[dict] | None,
    ) -> ParsedIntent:
        """Resolve missing item_name from conversation history.
        
        When user says things like "那扳手呢？" or "再查一下库存",
        the item_name may be missing. Try to infer from history.
        """
        # If item_name is already present, no need to resolve
        if intent.item_name:
            return intent
        
        # If no history, can't resolve
        if not history:
            return intent
        
        # Look for context clues in current text
        context_keywords = ["那", "再", "还", "呢", "它", "这个", "那个"]
        has_context_reference = any(kw in text for kw in context_keywords)
        
        if not has_context_reference:
            return intent
        
        # Search history backwards for the most recent item mention
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Try to extract item from historical message
                historical_intent = self._rule_based_parse_intent(content)
                if historical_intent.item_name:
                    # Found an item in history, inherit it
                    return ParsedIntent(
                        intent_type=intent.intent_type,
                        item_name=historical_intent.item_name,
                        quantity=intent.quantity,
                        confidence=intent.confidence * 0.85,  # Slightly lower due to inference
                    )
        
        return intent
    
    def _rule_based_parse_intent(self, text: str) -> ParsedIntent:
        """Fallback rule-based intent parsing."""
        text = text.strip()
        
        import re

        # Detect stock in patterns
        if any(kw in text for kw in ["进货", "入库", "采购", "买", "买了一", "进了一"]) or re.search(r"进了?\d+", text):
            item_name = self._extract_item_name(text)
            quantity = self._extract_quantity(text)
            return ParsedIntent(
                intent_type="stock_in",
                item_name=item_name,
                quantity=quantity,
                confidence=0.7,
            )
        
        # Detect stock out patterns
        if any(kw in text for kw in ["卖出", "出货", "出库", "卖了", "走了", "卖了一", "出了"]) or re.search(r"出了?\d+", text):
            item_name = self._extract_item_name(text)
            quantity = self._extract_quantity(text)
            return ParsedIntent(
                intent_type="stock_out",
                item_name=item_name,
                quantity=quantity,
                confidence=0.7,
            )
        
        # Detect revenue query patterns
        if any(kw in text for kw in ["营业额", "营收", "赚了", "收入", "利润", "毛利", "赚多少", "卖了多少", "生意", "经营", "今天店里", "店里情况", "怎么样"]):
            return ParsedIntent(
                intent_type="revenue_query",
                item_name=None,
                quantity=None,
                confidence=0.8,
            )
        
        # Detect sales ranking patterns
        if any(kw in text for kw in ["热销", "排行", "最好卖", "最畅销", "销量", "排行"]):
            return ParsedIntent(
                intent_type="sales_query",
                item_name=None,
                quantity=None,
                confidence=0.8,
            )
        
        # Detect low stock alert patterns
        if any(kw in text for kw in ["预警", "缺货", "库存不足", "不够", "要进货", "低于"]):
            return ParsedIntent(
                intent_type="alert_query",
                item_name=None,
                quantity=None,
                confidence=0.8,
            )
        
        # Detect stock query patterns (default)
        if any(kw in text for kw in ["多少", "几个", "还剩", "还有", "库存", "数量", "呢"]):
            item_name = self._extract_item_name(text)
            return ParsedIntent(
                intent_type="stock_query",
                item_name=item_name,
                quantity=None,
                confidence=0.8,
            )
        
        # Unknown
        return ParsedIntent(
            intent_type="unknown",
            item_name=self._extract_item_name(text),
            quantity=None,
            confidence=0.3,
        )
    
    def _extract_item_name(self, text: str) -> str | None:
        """Extract item name from text using simple heuristics."""
        # Common item patterns
        keywords = ["螺丝刀", "扳手", "钳子", "锤子", "钻头", "锯片", "电钻", "水管", "电线", "开关", "插座", "灯泡", "油漆", "胶水", "钉子", "螺丝", "螺母", "垫片", "轴承", "皮带", "链条"]
        
        for kw in keywords:
            if kw in text:
                return kw
        
        # Fallback: extract first noun-like word (2-6 chars)
        import re
        nouns = re.findall(r'[\u4e00-\u9fa5]{2,6}', text)
        
        # Common words to exclude (actions, particles, pronouns)
        exclude_words = [
            "进货", "入库", "出库", "库存", "多少", "几个", "还剩", "还有",
            "查询", "查一下", "查查看", "看看", "一下", "多少", "几个",
            "这个", "那个", "什么", "怎么", "多少", "还有", "再查",
            "查库存", "查一下", "查查看",
        ]
        
        for noun in nouns:
            if noun not in exclude_words and not any(ew in noun for ew in exclude_words):
                return noun
        
        return None
    
    def _extract_quantity(self, text: str) -> int | None:
        """Extract quantity from text."""
        import re
        
        # Number patterns
        patterns = [
            r'(\d+)[个位支箱把套件只]',
            r'[买了进进出售卖交货了]了?(\d+)',
            r'(\d+)件',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _mock_parse_intent(self, text: str) -> ParsedIntent:
        """Mock intent parsing for testing without LLM."""
        return self._rule_based_parse_intent(text)
    
    def generate_response(
        self,
        query_result: dict[str, Any],
        original_text: str,
        history: list[dict] | None = None,
    ) -> GeneratedResponse:
        """Generate natural language response from query result.
        
        Args:
            query_result: The inventory query result
            original_text: The original user query text
            history: Optional conversation history for multi-turn context
            
        Returns:
            GeneratedResponse with natural language content
        """
        if self._use_mock:
            return self._mock_generate_response(query_result)
        
        try:
            provider = self._get_provider()
            
            # Build prompt with query result
            prompt = self._build_response_prompt(query_result, original_text)
            
            messages = [
                {"role": "system", "content": self.RESPONSE_PROMPT},
            ]
            
            # Add history for multi-turn context
            if history:
                messages.extend(history)
            
            messages.append({"role": "user", "content": prompt})
            
            response = provider.chat(messages, stream=False)
            
            return GeneratedResponse(
                content=response.content.strip(),
                confidence=0.9,
            )
            
        except LLMProviderError as exc:
            logger.error("LLM generate response failed: %s", exc.message)
            # Fallback
            return self._mock_generate_response(query_result)
    
    def generate_business_response(
        self,
        *,
        query_result: dict[str, Any],
        original_text: str,
        intent_type: str,
        history: list[dict] | None = None,
    ) -> GeneratedResponse:
        """Generate an AI-native business reply from deterministic tool results."""
        if self._use_mock:
            return GeneratedResponse(content=self._build_deterministic_business_reply(intent_type, query_result), confidence=0.72)

        if self._should_use_fast_business_reply(intent_type, query_result, original_text):
            return GeneratedResponse(content=self._build_deterministic_business_reply(intent_type, query_result), confidence=0.82)

        try:
            provider = self._get_provider()
            import json

            messages = [{"role": "system", "content": self.RESPONSE_PROMPT}]
            if history:
                messages.extend(history[-4:])
            messages.append({
                "role": "user",
                "content": (
                    f"老板原话：{original_text}\n"
                    f"识别意图：{intent_type}\n"
                    f"真实业务数据JSON：{json.dumps(query_result, ensure_ascii=False, default=str)}\n"
                    "请基于这些真实数据回复老板。"
                ),
            })
            response = provider.chat(messages, stream=False)
            return GeneratedResponse(content=response.content.strip(), confidence=0.9)
        except LLMProviderError as exc:
            logger.error("LLM business response failed: %s", exc.message)
            return GeneratedResponse(content=self._build_deterministic_business_reply(intent_type, query_result), confidence=0.7)

    def generate_general_reply(
        self,
        *,
        original_text: str,
        intent_type: str = "unknown",
        history: list[dict] | None = None,
    ) -> GeneratedResponse:
        """Generate a helpful general business-assistant reply for ambiguous input."""
        if self._use_mock:
            return GeneratedResponse(
                content="我理解你想让我帮你看店铺经营。你可以直接问：今天生意怎么样、哪些商品快没货、最近什么卖得最好；如果要开单或改库存，我会先生成待确认草稿。",
                confidence=0.65,
            )

        try:
            provider = self._get_provider()
            messages = [{"role": "system", "content": self.GENERAL_ASSISTANT_PROMPT}]
            if history:
                messages.extend(history[-4:])
            messages.append({"role": "user", "content": original_text})
            response = provider.chat(messages, stream=False)
            return GeneratedResponse(content=response.content.strip(), confidence=0.88)
        except LLMProviderError as exc:
            logger.error("LLM general reply failed: %s", exc.message)
            return GeneratedResponse(
                content="我理解你想让我帮你处理店铺经营问题。你可以直接告诉我目标，比如查营业额、看库存预警、生成销售单或采购草稿，我会先分析再给你下一步。",
                confidence=0.65,
            )

    def _should_use_fast_business_reply(self, intent_type: str, query_result: dict[str, Any], original_text: str) -> bool:
        """Return deterministic business replies for high-frequency dashboard questions.

        These answers are already grounded in backend tool results. Skipping remote LLM here
        prevents basic owner queries from hanging when the free provider is slow, while still
        leaving LLM generation for ambiguous/general business conversation.
        """
        query_type = query_result.get("type")
        if intent_type in {"revenue_query", "sales_query", "alert_query"}:
            return True
        normalized = original_text.strip()
        return any(kw in normalized for kw in ("今天生意", "生意怎么样", "经营情况", "店里情况")) and query_type in {
            "revenue_summary",
            "sales_ranking",
            "low_stock_alerts",
        }

    def _build_deterministic_business_reply(self, intent_type: str, query_result: dict[str, Any]) -> str:
        """Safe deterministic fallback when LLM is unavailable."""
        if intent_type == "revenue_query" and query_result.get("type") == "revenue_summary":
            return (
                f"过去30天营业额为¥{query_result.get('total_revenue', 0):.2f}，"
                f"毛利润¥{query_result.get('gross_profit', 0):.2f}，"
                f"共{query_result.get('transaction_count', 0)}笔交易。"
            )
        if intent_type == "sales_query" and query_result.get("ranking"):
            top = query_result["ranking"][0]
            return f"过去30天卖得最好的是{top['item_name']}，售出{top['total_sold']:.0f}件，销售额¥{top['total_revenue']:.2f}。"
        if intent_type == "alert_query":
            count = query_result.get("count", 0)
            if count:
                first = query_result["alerts"][0]
                return f"当前有{count}个库存预警，最需要关注的是{first['item_name']}，还剩{first['current_quantity']}{first['unit']}。"
            return "当前没有库存预警，库存状态整体正常。"
        return self._build_fallback_reply_from_query(query_result)

    def _build_response_prompt(
        self,
        query_result: dict[str, Any],
        original_text: str,
    ) -> str:
        """Build prompt for response generation."""
        item_name = query_result.get("item_name", "商品")
        quantity = query_result.get("quantity", 0)
        unit = query_result.get("unit", "个")
        
        prompt = f"""查询："{original_text}"
{item_name}当前库存：{quantity}{unit}
用一句话回复店主。"""
        
        return prompt

    def _build_fallback_reply_from_query(self, query_result: dict[str, Any]) -> str:
        item_name = query_result.get("item_name", "商品")
        quantity = query_result.get("quantity", 0)
        unit = query_result.get("unit", "个")
        return f"{item_name}目前还有{quantity}{unit}，需要我继续帮你判断是否要补货吗？"
    
    def _mock_generate_response(self, query_result: dict[str, Any]) -> GeneratedResponse:
        """Mock response generation."""
        item_name = query_result.get("item_name", "商品")
        quantity = query_result.get("quantity", 0)
        unit = query_result.get("unit", "个")
        
        content = f"{item_name}目前还有{quantity}{unit}，需要进货吗？"
        
        return GeneratedResponse(content=content, confidence=0.7)


# Global singleton (thread-safe via imports)
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create global LLM service."""
    global _llm_service
    if _llm_service is None:
        try:
            # Try to create with real provider
            settings = get_settings()
            provider = create_llm_provider(
                timeout_seconds=settings.llm_timeout_seconds,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
            _llm_service = LLMService(provider=provider)
            logger.info("LLM service initialized with real provider")
        except ValueError:
            # Fallback to mock
            _llm_service = LLMService(provider=None)
            logger.warning("LLM service initialized with mock provider")
    return _llm_service


def parse_stock_query_intent(
    text: str,
    db_session: Session | None = None,
) -> ParsedIntent:
    """Convenience function to parse stock query intent."""
    return get_llm_service().parse_intent(text, db_session)
