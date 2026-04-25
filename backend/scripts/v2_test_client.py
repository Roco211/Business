"""Shared V2 API test client for CLI acceptance scripts.

Keeps Phase 8/9/10 scripts aligned with the current V2 auth contract:
phone-code demo login -> tenant/shop discovery -> context selection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class V2AuthContext:
    token: str
    account_id: str | None
    tenant_id: str
    shop_id: str
    context_token: str

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @property
    def context_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Context-Token": self.context_token,
        }


class V2TestClient:
    def __init__(
        self,
        base: str = "http://127.0.0.1:8001/api/v2",
        *,
        phone: str = "13800138000",
        verification_code: str = "888888",
        timeout: float = 10,
    ) -> None:
        self.base = base.rstrip("/")
        self.phone = phone
        self.verification_code = verification_code
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._auth_context: V2AuthContext | None = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "V2TestClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def data(response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        body = response.json()
        data = body.get("data")
        if not isinstance(data, dict):
            raise AssertionError(f"Response missing object data: {body}")
        return data

    @staticmethod
    def pick(data: dict[str, Any], *names: str) -> Any:
        for name in names:
            if name in data and data[name] not in (None, ""):
                return data[name]
        raise KeyError(f"Missing any of fields {names}; available={sorted(data.keys())}")

    def login(self) -> dict[str, Any]:
        response = self._client.post(
            f"{self.base}/auth/login",
            json={
                "auth_method": "phone_code",
                "phone": self.phone,
                "verification_code": self.verification_code,
            },
        )
        return self.data(response)

    def get_auth_context(self) -> V2AuthContext:
        if self._auth_context is not None:
            return self._auth_context

        login_data = self.login()
        token = str(self.pick(login_data, "accessToken", "access_token"))
        account_id_value = login_data.get("accountId") or login_data.get("account_id")
        account_id = str(account_id_value) if account_id_value is not None else None
        auth_headers = {"Authorization": f"Bearer {token}"}

        tenants_data = self.data(self._client.get(f"{self.base}/me/tenants", headers=auth_headers))
        tenants = tenants_data.get("tenants") or []
        if not tenants:
            raise AssertionError("No accessible tenants returned by /me/tenants")
        tenant_id = str(tenants[0].get("tenant_id") or tenants[0].get("tenantId"))

        shops_data = self.data(self._client.get(f"{self.base}/tenants/{tenant_id}/shops", headers=auth_headers))
        shops = shops_data.get("shops") or []
        if not shops:
            raise AssertionError(f"No accessible shops returned for tenant {tenant_id}")
        shop_id = str(shops[0].get("shop_id") or shops[0].get("shopId"))

        context_data = self.data(
            self._client.post(
                f"{self.base}/context/select",
                headers=auth_headers,
                json={"tenant_id": tenant_id, "shop_id": shop_id},
            )
        )
        context_token = str(
            self.pick(
                context_data,
                "contextToken",
                "contextSessionId",
                "context_token",
                "context_session_id",
            )
        )

        self._auth_context = V2AuthContext(
            token=token,
            account_id=account_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            context_token=context_token,
        )
        return self._auth_context

    def get(self, path: str, *, context: bool = True, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if context:
            headers.update(self.get_auth_context().context_headers)
        return self._client.get(f"{self.base}{path}", headers=headers, **kwargs)

    def post(self, path: str, *, context: bool = True, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if context:
            headers.update(self.get_auth_context().context_headers)
        return self._client.post(f"{self.base}{path}", headers=headers, **kwargs)
