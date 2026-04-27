from __future__ import annotations

import importlib
from dataclasses import dataclass

from app.api.v2.routes import chat as chat_routes
from app.services import v2_llm

from tests.test_v2_chat_http_confirmation_flow import (
    _FakeIntent,
    _login_and_select_context,
    _seed_v2_chat_http_context,
)


@dataclass
class _FakeGeneratedResponse:
    content: str
    confidence: float = 0.98


class _FakeGeneralLLMService:
    def parse_intent(self, user_message: str, db_session=None, history=None):
        return _FakeIntent(intent_type="unknown", item_name=None, quantity=None)

    def generate_business_response(self, *, query_result, original_text: str, intent_type: str, history=None):
        raise AssertionError("unknown general chat should not require business query result")

    def generate_general_reply(self, *, original_text: str, intent_type: str, history=None):
        return _FakeGeneratedResponse(content="我理解你想先了解店铺经营情况，可以先看今天营业额、库存预警和待确认任务。")


class _FakeRevenueLLMService:
    def parse_intent(self, user_message: str, db_session=None, history=None):
        return _FakeIntent(intent_type="revenue_query", item_name=None, quantity=None)

    def generate_business_response(self, *, query_result, original_text: str, intent_type: str, history=None):
        assert intent_type == "revenue_query"
        assert query_result["type"] == "revenue_summary"
        assert "total_revenue" in query_result
        return _FakeGeneratedResponse(content="AI已根据真实流水汇总：今天可以重点关注营业额和毛利变化。")

    def generate_general_reply(self, *, original_text: str, intent_type: str, history=None):
        raise AssertionError("revenue query should use business data response")


class _FakeProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_create_llm_provider_reads_business_provider_prefixed_env(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("VOLCANO_API_KEY", raising=False)
    monkeypatch.delenv("VOLCANO_API_URL", raising=False)
    monkeypatch.delenv("VOLCANO_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER_API_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_PROVIDER_MODEL", "test/model:free")

    import app.services.llm_real_provider as provider_module

    created = {}

    class CapturingProvider:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr(provider_module, "OpenAILLMProvider", CapturingProvider)

    provider_module.create_llm_provider()

    assert created["api_key"] == "test-key"
    assert created["api_url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert created["model"] == "test/model:free"
    assert created["provider_name"] == "openrouter"


def test_get_llm_service_uses_real_provider_when_business_prefixed_config_exists(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER_API_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_PROVIDER_MODEL", "test/model:free")
    monkeypatch.setattr(v2_llm, "_llm_service", None)
    monkeypatch.setattr(v2_llm, "create_llm_provider", lambda **_: _FakeProvider())

    service = v2_llm.get_llm_service()

    assert service.provider is not None


def test_http_chat_unknown_intent_uses_ai_general_reply_not_format_instruction(client, db_session, monkeypatch):
    tenant_id, shop_id, email, _ = _seed_v2_chat_http_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)
    monkeypatch.setattr(chat_routes, "get_llm_service", lambda: _FakeGeneralLLMService())

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={"message": "这个店现在有什么问题需要我注意？"},
    )

    assert response.status_code == 200
    reply = response.json()["data"]["reply"]
    assert "我理解你想先了解店铺经营情况" in reply
    assert "不理解您的意思" not in reply
    assert "您可以问我：查库存" not in reply


def test_http_chat_revenue_query_uses_real_tool_result_then_ai_explanation(client, db_session, monkeypatch):
    tenant_id, shop_id, email, _ = _seed_v2_chat_http_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)
    monkeypatch.setattr(chat_routes, "get_llm_service", lambda: _FakeRevenueLLMService())

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={"message": "今天生意怎么样？"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["intent"] == "revenue_query"
    assert "AI已根据真实流水汇总" in payload["reply"]
