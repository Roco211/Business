"""LLM service layer for intent parsing and response generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

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

意图：stock_query(查库存), stock_in(入库), stock_out(出库)
输出JSON格式：{"intent": "意图", "item": "商品名", "quantity": 数量}
示例输入："螺丝刀还有几个" -> {"intent": "stock_query", "item": "螺丝刀", "quantity": null}"""

    RESPONSE_PROMPT = """你是店铺库存助手。简洁回复用户问题。
规则：
1. 直接回答问题
2. 使用中文
3. 如果不确定，请用户确认"""

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
    ) -> ParsedIntent:
        """Parse user intent from transcribed text.
        
        Args:
            text: The transcribed user input
            db_session: Optional DB session for inventory lookup
            
        Returns:
            ParsedIntent with type, item_name, quantity, confidence
        """
        if self._use_mock:
            return self._mock_parse_intent(text)
        
        try:
            provider = self._get_provider()
            
            messages = [
                {"role": "system", "content": self.INTENT_PARSING_PROMPT},
                {"role": "user", "content": f"分析输入：\"{text}\""},
            ]
            
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
                
                return ParsedIntent(
                    intent_type=intent_type,
                    item_name=item_name,
                    quantity=quantity,
                    confidence=confidence,
                )
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON: %s", content)
                # Fallback to rule-based
                return self._rule_based_parse_intent(text)
                
        except LLMProviderError as exc:
            logger.error("LLM parse intent failed: %s", exc.message)
            # Fallback to rule-based
            return self._rule_based_parse_intent(text)
    
    def _rule_based_parse_intent(self, text: str) -> ParsedIntent:
        """Fallback rule-based intent parsing."""
        text = text.strip()
        
        # Detect stock in patterns
        if any(kw in text for kw in ["进货", "入库", "采购", "买", "买了一", "进了一"]):
            item_name = self._extract_item_name(text)
            quantity = self._extract_quantity(text)
            return ParsedIntent(
                intent_type="stock_in",
                item_name=item_name,
                quantity=quantity,
                confidence=0.7,
            )
        
        # Detect stock out patterns
        if any(kw in text for kw in ["卖出", "出货", "出库", "卖了", "走了", "卖了一"]):
            item_name = self._extract_item_name(text)
            quantity = self._extract_quantity(text)
            return ParsedIntent(
                intent_type="stock_out",
                item_name=item_name,
                quantity=quantity,
                confidence=0.7,
            )
        
        # Detect stock query patterns (default)
        if any(kw in text for kw in ["多少", "几个", "还剩", "还有", "库存", "数量"]):
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
        
        # Fallback: extract first noun-like word (2-4 chars)
        import re
        nouns = re.findall(r'[\u4e00-\u9fa5]{2,6}', text)
        for noun in nouns:
            if noun not in ["进货", "入库", "出库", "库存", "多少", "几个", "还剩"]:
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
            provider = create_llm_provider()
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
