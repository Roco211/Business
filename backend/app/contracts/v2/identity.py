from pydantic import BaseModel, Field
from typing import Literal


class V2LoginRequest(BaseModel):
    # Support both email/password and phone/verification_code auth
    email: str | None = None
    password: str | None = None
    phone: str | None = None
    verification_code: str | None = None
    auth_method: Literal["email_password", "phone_code", "phone_password"] = "email_password"


class V2LoginData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    account_id: str


class V2RefreshRequest(BaseModel):
    refresh_token: str


class V2MeData(BaseModel):
    account_id: str
    email: str
    display_name: str
    status: str


class V2LogoutData(BaseModel):
    status: str


class V2TenantData(BaseModel):
    tenant_id: str
    name: str
    role_key: str


class V2TenantListData(BaseModel):
    tenants: list[V2TenantData]


class V2ShopData(BaseModel):
    shop_id: str
    tenant_id: str
    code: str
    name: str
    access_level: str


class V2ShopListData(BaseModel):
    shops: list[V2ShopData]


class V2ContextSelectRequest(BaseModel):
    tenant_id: str
    shop_id: str


class V2ContextData(BaseModel):
    context_token: str
    context_session_id: str
    account_id: str
    tenant_id: str
    shop_id: str
    membership_id: str
    role_key: str
    permissions: list[str]
