from dataclasses import dataclass

from app.api.v2.routes import chat as chat_routes
from test_v2_chat_http_confirmation_flow import _login_and_select_context, _seed_v2_chat_http_context


@dataclass(frozen=True)
class _FakeIntent:
    intent_type: str = "stock_query"
    item_name: str | None = "测试锤子"
    quantity: int | None = None
    confidence: float = 0.99


@dataclass(frozen=True)
class _FakeGeneratedResponse:
    content: str
    confidence: float = 0.91


class _ClientAsrFakeLLMService:
    def __init__(self) -> None:
        self.seen_messages: list[str] = []

    def parse_intent(self, user_message: str, db_session=None, history=None):
        self.seen_messages.append(user_message)
        return _FakeIntent()

    def generate_business_response(self, query_result, original_text: str, intent_type: str, history=None):
        return _FakeGeneratedResponse(content=f"已按语音文字查询：{original_text}")


def test_chat_accepts_client_asr_text_without_server_asr(client, db_session, monkeypatch):
    tenant_id, shop_id, email, _item_id = _seed_v2_chat_http_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)
    fake_llm = _ClientAsrFakeLLMService()
    monkeypatch.setattr(chat_routes, "get_llm_service", lambda: fake_llm)

    def fail_if_server_asr_is_called(*_args, **_kwargs):
        raise AssertionError("client_asr voice_text must not call server ASR gateway")

    monkeypatch.setattr(chat_routes, "build_asr_gateway", fail_if_server_asr_is_called, raising=False)

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={
            "message": "帮我查一下测试锤子库存",
            "input_type": "voice_text",
            "source": "client_asr",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reply"]
    assert data["input_type"] == "voice_text"
    assert data["source"] == "client_asr"
    assert fake_llm.seen_messages == ["帮我查一下测试锤子库存"]


def test_chat_rejects_blank_client_asr_text(client, db_session):
    tenant_id, shop_id, email, _item_id = _seed_v2_chat_http_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={"message": "  ", "input_type": "voice_text", "source": "client_asr"},
    )

    assert response.status_code == 422
