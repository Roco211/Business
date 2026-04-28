from test_v2_identity_context import seed_v2_identity


class FakeSmsProvider:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str]] = []

    def send_verification_code(self, *, phone: str, code: str) -> None:
        self.sent_messages.append((phone, code))


def _seed_owner(db_session, *, account_id: str = "acct_sms_owner", email: str = "owner@example.com") -> None:
    seed_v2_identity(
        db_session,
        account_id=account_id,
        email=email,
        password="dev-password",
        tenants=[("tenant_sms", "短信测试租户")],
        shops={"tenant_sms": [("shop_sms", "短信测试门店")]},
    )


def test_demo_phone_login_accepts_888888_only_in_local_demo(client, db_session, monkeypatch):
    _seed_owner(db_session)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")

    response = client.post(
        "/api/v2/auth/login",
        json={
            "auth_method": "phone_code",
            "phone": "13800000000",
            "verification_code": "888888",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["accountId"] == "acct_sms_owner"


def test_production_rejects_888888_without_sent_code(client, db_session, monkeypatch):
    _seed_owner(db_session)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")

    response = client.post(
        "/api/v2/auth/login",
        json={
            "auth_method": "phone_code",
            "phone": "13800000000",
            "verification_code": "888888",
        },
    )

    assert response.status_code == 401


def test_send_code_endpoint_uses_sms_provider(client, monkeypatch):
    fake_sms_provider = FakeSmsProvider()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")

    from app.services import sms_provider

    monkeypatch.setattr(sms_provider, "get_default_sms_provider", lambda settings: fake_sms_provider)

    response = client.post("/api/v2/auth/verification-codes", json={"phone": "13800000000"})

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True, "expires_in_seconds": 300}
    assert len(fake_sms_provider.sent_messages) == 1
    sent_phone, sent_code = fake_sms_provider.sent_messages[0]
    assert sent_phone == "13800000000"
    assert sent_code != "888888"
    assert len(sent_code) == 6
    assert sent_code.isdigit()


def test_production_phone_code_login_consumes_sent_verification_code(client, db_session, monkeypatch):
    _seed_owner(db_session)
    fake_sms_provider = FakeSmsProvider()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")

    from app.services import sms_provider

    monkeypatch.setattr(sms_provider, "get_default_sms_provider", lambda settings: fake_sms_provider)

    send_response = client.post("/api/v2/auth/verification-codes", json={"phone": "13800000000"})
    assert send_response.status_code == 200
    sent_code = fake_sms_provider.sent_messages[0][1]

    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "auth_method": "phone_code",
            "phone": "13800000000",
            "verification_code": sent_code,
        },
    )
    replay_response = client.post(
        "/api/v2/auth/login",
        json={
            "auth_method": "phone_code",
            "phone": "13800000000",
            "verification_code": sent_code,
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["data"]["accountId"] == "acct_sms_owner"
    assert replay_response.status_code == 401
