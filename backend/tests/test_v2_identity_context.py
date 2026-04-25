import hashlib
from datetime import datetime, timezone
UTC = timezone.utc

from app.models import V2Account, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_v2_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        310_000,
    ).hex()


def seed_v2_identity(
    db_session,
    *,
    account_id: str,
    email: str,
    password: str,
    tenants: list[tuple[str, str]],
    shops: dict[str, list[tuple[str, str]]],
    accessible_shops: list[str] | None = None,
    role_key: str = "owner",
) -> None:
    now = _utc_now_naive()
    salt_hex = "11" * 16
    db_session.add(
        V2Account(
            account_id=account_id,
            email=email,
            display_name="Owner",
            password_hash=_hash_v2_password(password, salt_hex),
            password_salt=salt_hex,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    for tenant_id, tenant_name in tenants:
        membership_id = f"mship_{tenant_id}"
        db_session.add(
            V2Tenant(
                tenant_id=tenant_id,
                name=tenant_name,
                slug=tenant_id,
                status="active",
                plan_code="trial",
                owner_account_id=account_id,
                created_at=now,
                updated_at=now,
            )
        )
        db_session.add(
            V2TenantMembership(
                membership_id=membership_id,
                tenant_id=tenant_id,
                account_id=account_id,
                role_key=role_key,
                status="active",
                joined_at=now,
                updated_at=now,
            )
        )
        for shop_id, shop_name in shops.get(tenant_id, []):
            db_session.add(
                V2Shop(
                    shop_id=shop_id,
                    tenant_id=tenant_id,
                    code=shop_id,
                    name=shop_name,
                    locale="zh-CN",
                    timezone="Asia/Shanghai",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            if accessible_shops is None or shop_id in accessible_shops:
                db_session.add(
                    V2ShopAccess(
                        shop_access_id=f"access_{shop_id}",
                        tenant_id=tenant_id,
                        shop_id=shop_id,
                        membership_id=membership_id,
                        access_level="write",
                        status="active",
                        created_at=now,
                    )
                )

    db_session.commit()


def login_v2(client, *, email: str = "owner@example.com", password: str = "dev-password") -> str:
    response = client.post(
        "/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    return payload.get("access_token") or payload.get("accessToken")


def test_v2_health_returns_versioned_envelope(client) -> None:
    response = client.get("/api/v2/health")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "status": "ok",
            "api_version": "v2",
        }
    }


def test_v2_schema_supports_account_multiple_tenants_and_tenant_multiple_shops(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2Account, V2Shop, V2Tenant, V2TenantMembership

    account = V2Account(
        account_id="acct_001",
        email="owner@example.com",
        display_name="Owner",
        password_hash="hash",
        password_salt="salt",
        status="active",
    )
    tenant_a = V2Tenant(
        tenant_id="tenant_a",
        name="A 商家",
        slug="tenant-a",
        status="active",
        plan_code="trial",
        owner_account_id="acct_001",
    )
    tenant_b = V2Tenant(
        tenant_id="tenant_b",
        name="B 商家",
        slug="tenant-b",
        status="active",
        plan_code="trial",
        owner_account_id="acct_001",
    )
    shop_a1 = V2Shop(
        shop_id="shop_a1",
        tenant_id="tenant_a",
        code="a-1",
        name="A 一号店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
    )
    shop_a2 = V2Shop(
        shop_id="shop_a2",
        tenant_id="tenant_a",
        code="a-2",
        name="A 二号店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
    )
    db_session.add_all(
        [
            account,
            tenant_a,
            tenant_b,
            V2TenantMembership(
                membership_id="mship_a",
                tenant_id="tenant_a",
                account_id="acct_001",
                role_key="owner",
                status="active",
            ),
            V2TenantMembership(
                membership_id="mship_b",
                tenant_id="tenant_b",
                account_id="acct_001",
                role_key="owner",
                status="active",
            ),
            shop_a1,
            shop_a2,
        ]
    )
    db_session.commit()

    memberships = db_session.scalars(
        select(V2TenantMembership).where(V2TenantMembership.account_id == "acct_001")
    ).all()
    shops = db_session.scalars(select(V2Shop).where(V2Shop.tenant_id == "tenant_a")).all()

    assert {membership.tenant_id for membership in memberships} == {"tenant_a", "tenant_b"}
    assert {shop.shop_id for shop in shops} == {"shop_a1", "shop_a2"}


def test_v2_login_returns_account_session_without_shop_binding(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家"), ("tenant_b", "B 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
    )

    response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert (payload.get("token_type") or payload.get("tokenType")) == "Bearer"
    assert (payload.get("account_id") or payload.get("accountId")) == "acct_001"
    assert payload.get("refresh_token") or payload.get("refreshToken")
    assert "tenant_id" not in payload
    assert "shop_id" not in payload


def test_v2_login_returns_refresh_token(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )

    response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert response.status_code == 200
    refresh_payload = response.json()["data"]
    assert refresh_payload.get("refresh_token") or refresh_payload.get("refreshToken")


def test_v2_me_returns_authenticated_account_profile(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )
    token = login_v2(client)

    response = client.get(
        "/api/v2/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["account_id"] == "acct_001"
    assert payload["email"] == "owner@example.com"
    assert "tenant_id" not in payload
    assert "shop_id" not in payload


def test_v2_logout_revokes_auth_and_context_sessions(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
        accessible_shops=["shop_a1"],
    )
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    login_payload = login_response.json()["data"]
    token = login_payload.get("access_token") or login_payload.get("accessToken")
    select_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    context_payload = select_response.json()["data"]
    context_token = context_payload.get("context_token") or context_payload.get("contextToken")

    logout_response = client.post(
        "/api/v2/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {token}"})
    context_response = client.get(
        "/api/v2/context/current",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert logout_response.status_code == 200
    assert me_response.status_code == 401
    assert context_response.status_code == 401


def test_v2_refresh_rotates_auth_session(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    login_payload = login_response.json()["data"]
    old_access_token = login_payload.get("access_token") or login_payload.get("accessToken")
    old_refresh_token = login_payload.get("refresh_token") or login_payload.get("refreshToken")

    refresh_response = client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    refresh_payload = refresh_response.json()["data"]
    new_access_token = refresh_payload.get("access_token") or refresh_payload.get("accessToken")

    old_me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {old_access_token}"})
    new_me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {new_access_token}"})

    assert refresh_response.status_code == 200
    new_refresh_payload = refresh_response.json()["data"]
    assert (new_refresh_payload.get("refresh_token") or new_refresh_payload.get("refreshToken")) != old_refresh_token
    assert old_me_response.status_code == 401
    assert new_me_response.status_code == 200


def test_v2_me_tenants_and_tenant_shops_use_membership_boundaries(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家"), ("tenant_b", "B 商家")],
        shops={
            "tenant_a": [("shop_a1", "A 一号店"), ("shop_a2", "A 二号店")],
            "tenant_b": [("shop_b1", "B 一号店")],
        },
        accessible_shops=["shop_a1", "shop_b1"],
    )
    token = login_v2(client)

    tenants_response = client.get("/api/v2/me/tenants", headers={"Authorization": f"Bearer {token}"})
    shops_response = client.get(
        "/api/v2/tenants/tenant_a/shops",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert tenants_response.status_code == 200
    assert {tenant["tenant_id"] for tenant in tenants_response.json()["data"]["tenants"]} == {
        "tenant_a",
        "tenant_b",
    }
    assert shops_response.status_code == 200
    assert [shop["shop_id"] for shop in shops_response.json()["data"]["shops"]] == ["shop_a1"]


def test_v2_context_select_rejects_shop_without_access(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店"), ("shop_a2", "A 二号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client)

    response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a2"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "shop_access_denied"


def test_v2_context_select_creates_explicit_context_session(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client)

    response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert (payload.get("tenant_id") or payload.get("tenantId")) == "tenant_a"
    assert (payload.get("shop_id") or payload.get("shopId")) == "shop_a1"
    assert (payload.get("membership_id") or payload.get("membershipId")) == "mship_tenant_a"
    assert (payload.get("context_token") or payload.get("contextToken")) == (payload.get("context_session_id") or payload.get("contextSessionId"))
    assert "inventory:read" in payload["permissions"]


def test_v2_context_current_requires_context_token(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client)

    response = client.get(
        "/api/v2/context/current",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"


def test_v2_context_current_returns_selected_context(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client)
    select_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    context_payload = select_response.json()["data"]
    context_token = context_payload.get("context_token") or context_payload.get("contextToken")

    response = client.get(
        "/api/v2/context/current",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Context-Token": context_token,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert (payload.get("context_session_id") or payload.get("contextSessionId")) == context_token
    assert (payload.get("tenant_id") or payload.get("tenantId")) == "tenant_a"
    assert (payload.get("shop_id") or payload.get("shopId")) == "shop_a1"



def _select_context_for_role(client, db_session, *, role_key: str) -> tuple[str, dict[str, str], dict]:
    email = f"{role_key}@example.com"
    seed_v2_identity(
        db_session,
        account_id=f"acct_{role_key}",
        email=email,
        password="dev-password",
        tenants=[(f"tenant_{role_key}", f"Tenant {role_key}")],
        shops={f"tenant_{role_key}": [(f"shop_{role_key}", f"Shop {role_key}")]},
        accessible_shops=[f"shop_{role_key}"],
        role_key=role_key,
    )
    token = login_v2(client, email=email)
    response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": f"tenant_{role_key}", "shop_id": f"shop_{role_key}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    context_token = payload.get("context_token") or payload.get("contextToken")
    headers = {"Authorization": f"Bearer {token}", "X-Context-Token": context_token}
    return token, headers, payload


def test_v2_context_select_snapshots_clerk_permissions(client, db_session) -> None:
    _, _, payload = _select_context_for_role(client, db_session, role_key="clerk")

    assert (payload.get("role_key") or payload.get("roleKey")) == "clerk"
    assert "sales:write" in payload["permissions"]
    assert "ai:write" in payload["permissions"]
    assert "finance:read" not in payload["permissions"]
    assert "exports:sales" not in payload["permissions"]
    assert "confirmations:approve" not in payload["permissions"]


def test_v2_context_select_snapshots_finance_permissions(client, db_session) -> None:
    _, _, payload = _select_context_for_role(client, db_session, role_key="finance")

    assert (payload.get("role_key") or payload.get("roleKey")) == "finance"
    assert "finance:read" in payload["permissions"]
    assert "exports:finance" in payload["permissions"]
    assert "exports:inventory" not in payload["permissions"]
    assert "inventory:write" not in payload["permissions"]
    assert "sales:write" not in payload["permissions"]
    assert "confirmations:approve" not in payload["permissions"]


def test_v2_rbac_denies_clerk_finance_summary(client, db_session) -> None:
    _, headers, _ = _select_context_for_role(client, db_session, role_key="clerk")

    response = client.get("/api/v2/finance/summary", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_v2_rbac_denies_finance_inventory_write(client, db_session) -> None:
    _, headers, _ = _select_context_for_role(client, db_session, role_key="finance")

    response = client.post(
        "/api/v2/inventory/items",
        headers=headers,
        json={"sku": "RBAC-FIN-001", "name": "财务无权新增商品", "default_unit": "个"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_v2_rbac_allows_owner_finance_summary_and_inventory_write(client, db_session) -> None:
    _, headers, _ = _select_context_for_role(client, db_session, role_key="owner")

    finance_response = client.get("/api/v2/finance/summary", headers=headers)
    create_response = client.post(
        "/api/v2/inventory/items",
        headers=headers,
        json={"sku": "RBAC-OWN-001", "name": "老板可新增商品", "default_unit": "个"},
    )

    assert finance_response.status_code == 200
    assert create_response.status_code == 200
    assert create_response.json()["data"]["item"]["name"] == "老板可新增商品"
