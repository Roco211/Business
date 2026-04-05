from datetime import UTC, datetime, timedelta
import hashlib

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.db.session import get_db_session
from app.main import register_exception_handlers
from app.models import AuthSession
from app.services.bootstrap import ensure_default_context


def test_require_authenticated_context_rejects_expired_token(db_session) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_session] = lambda: db_session
    ensure_default_context(db_session)

    @app.get("/protected")
    def protected(
        auth: AuthenticatedContext = Depends(require_authenticated_context),
    ) -> dict[str, str]:
        return {"shop_id": auth.shop_id}

    expired_token = "expired_token_123"
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AuthSession(
            auth_session_id="auth_expired_001",
            actor_id="owner_default",
            shop_id="shop_default",
            session_token_hash=hashlib.sha256(expired_token.encode("utf-8")).hexdigest(),
            status="active",
            expires_at=now - timedelta(minutes=1),
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_require_authenticated_context_resolves_active_token(db_session) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_session] = lambda: db_session
    ensure_default_context(db_session)

    @app.get("/protected")
    def protected(
        auth: AuthenticatedContext = Depends(require_authenticated_context),
    ) -> dict[str, str]:
        return {"shop_id": auth.shop_id, "actor_id": auth.actor_id}

    token = "active_token_123"
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AuthSession(
            auth_session_id="auth_active_001",
            actor_id="owner_default",
            shop_id="shop_default",
            session_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            status="active",
            expires_at=now + timedelta(minutes=10),
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"shop_id": "shop_default", "actor_id": "owner_default"}


def test_require_authenticated_context_rejects_revoked_token(db_session) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_session] = lambda: db_session
    ensure_default_context(db_session)

    @app.get("/protected")
    def protected(
        auth: AuthenticatedContext = Depends(require_authenticated_context),
    ) -> dict[str, str]:
        return {"shop_id": auth.shop_id}

    token = "revoked_token_123"
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AuthSession(
            auth_session_id="auth_revoked_001",
            actor_id="owner_default",
            shop_id="shop_default",
            session_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            status="active",
            expires_at=now + timedelta(minutes=10),
            revoked_at=now - timedelta(minutes=1),
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_require_authenticated_context_rejects_inactive_session(db_session) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_session] = lambda: db_session
    ensure_default_context(db_session)

    @app.get("/protected")
    def protected(
        auth: AuthenticatedContext = Depends(require_authenticated_context),
    ) -> dict[str, str]:
        return {"shop_id": auth.shop_id}

    token = "inactive_token_123"
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AuthSession(
            auth_session_id="auth_inactive_001",
            actor_id="owner_default",
            shop_id="shop_default",
            session_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            status="inactive",
            expires_at=now + timedelta(minutes=10),
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
