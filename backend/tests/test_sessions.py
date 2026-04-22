from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal

from app.api.deps.auth import AuthenticatedContext
from app.api.routes import sessions as session_routes
from app.db.session import get_session_factory
from app.models import OwnerAccount, SessionRecord, Shop, ShopMembership
from app.services.auth_sessions import issue_auth_session
from app.services.bootstrap import BootstrapContext
from conftest import auth_headers, login_and_get_token


def _build_seeded_context(*, shop_id: str, session_id: str) -> BootstrapContext:
    now = datetime.now(UTC).replace(tzinfo=None)
    shop = Shop(
        shop_id=shop_id,
        name="Seeded Shop",
        owner_name="Owner",
        industry="retail",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        require_price_confirmation=True,
        require_new_item_confirmation=True,
        low_confidence_threshold=Decimal("0.8500"),
        default_low_stock_threshold=None,
        created_at=now,
        updated_at=now,
    )
    session = SessionRecord(
        session_id=session_id,
        shop_id=shop_id,
        session_type="workgroup",
        title="Seeded Session",
        participants=["xiaoya"],
        last_event_seq=0,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    return BootstrapContext(shop=shop, session=session)


def test_session_bootstrap_accepts_real_login_token(client, monkeypatch) -> None:
    token = login_and_get_token(client, monkeypatch)

    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session_id"] == "sess_default"
    assert payload["session_type"] == "workgroup"
    assert payload["title"] == "数字员工工作群"
    assert payload["participants"] == ["xiaoya", "laoli"]


def test_session_bootstrap_unauthorized_returns_error_envelope(client) -> None:
    response = client.post("/api/v1/sessions/bootstrap")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Unauthorized",
            "details": [],
        }
    }


def test_openapi_documents_401_for_session_bootstrap(client) -> None:
    response = client.get("/openapi.json")

    responses = response.json()["paths"]["/api/v1/sessions/bootstrap"]["post"]["responses"]

    assert "401" in responses


def test_session_bootstrap_accepts_matching_seeded_fallback_without_default_id_check(
    db_session,
    monkeypatch,
) -> None:
    auth = AuthenticatedContext(
        actor_id="owner_seeded",
        shop_id="shop_seeded",
        auth_session_id="auth_seeded",
        role="owner",
    )
    monkeypatch.setattr(
        session_routes,
        "ensure_shop_context",
        lambda _db_session, *, shop_id, owner_actor_id: (
            _build_seeded_context(shop_id="shop_seeded", session_id="sess_seeded")
            if shop_id == "shop_seeded" and owner_actor_id == "owner_seeded"
            else None
        ),
    )

    response = session_routes.bootstrap_session(auth=auth, db_session=db_session)

    assert response.data.session_id == "sess_seeded"
    assert response.data.title == "Seeded Session"


def test_session_bootstrap_returns_404_envelope_when_authenticated_shop_has_no_session(client) -> None:
    db_session = get_session_factory()()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        shop = Shop(
            shop_id="shop_no_session",
            name="No Session Shop",
            owner_name="Owner",
            industry="retail",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            require_price_confirmation=True,
            require_new_item_confirmation=True,
            low_confidence_threshold=Decimal("0.8500"),
            default_low_stock_threshold=None,
            created_at=now,
            updated_at=now,
        )
        owner = OwnerAccount(
            actor_id="owner_no_session",
            email="no-session@example.com",
            display_name="No Session Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
        membership = ShopMembership(
            membership_id="mship_no_session",
            shop_id=shop.shop_id,
            actor_id=owner.actor_id,
            role="owner",
            is_default_shop=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(shop)
        db_session.add(owner)
        db_session.add(membership)
        db_session.commit()

        token = issue_auth_session(
            db_session,
            actor_id=owner.actor_id,
            shop_id=shop.shop_id,
            ttl_minutes=30,
        ).access_token
    finally:
        db_session.close()

    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_not_found",
            "message": "Session not found",
            "details": [],
        }
    }
