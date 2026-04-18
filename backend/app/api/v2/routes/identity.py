from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.identity import (
    V2ContextData,
    V2ContextSelectRequest,
    V2LoginData,
    V2LoginRequest,
    V2ShopData,
    V2ShopListData,
    V2TenantData,
    V2TenantListData,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.v2_identity import (
    authenticate_v2_account,
    issue_v2_auth_session,
    list_v2_accessible_shops,
    list_v2_tenants_for_account,
    select_v2_context,
)

router = APIRouter(prefix="/api/v2", tags=["v2-identity"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="unauthorized", message="Unauthorized")
        ).model_dump(),
    )


@router.post("/auth/login", response_model=V2DataEnvelope[V2LoginData], responses={401: {"model": V2ErrorEnvelope}})
def login_v2(
    payload: V2LoginRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2LoginData] | JSONResponse:
    account = authenticate_v2_account(db_session, payload.email, payload.password)
    if account is None:
        return _unauthorized()

    issued = issue_v2_auth_session(
        db_session,
        account_id=account.account_id,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    return V2DataEnvelope(
        data=V2LoginData(
            access_token=issued.access_token,
            token_type="Bearer",
            account_id=issued.account_id,
        )
    )


@router.get("/me/tenants", response_model=V2DataEnvelope[V2TenantListData])
def me_tenants_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2TenantListData]:
    tenants = [
        V2TenantData(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            role_key=membership.role_key,
        )
        for tenant, membership in list_v2_tenants_for_account(db_session, account.account_id)
    ]
    return V2DataEnvelope(data=V2TenantListData(tenants=tenants))


@router.get("/tenants/{tenant_id}/shops", response_model=V2DataEnvelope[V2ShopListData])
def tenant_shops_v2(
    tenant_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ShopListData]:
    shops = [
        V2ShopData(
            shop_id=shop.shop_id,
            tenant_id=shop.tenant_id,
            code=shop.code,
            name=shop.name,
            access_level=access.access_level,
        )
        for shop, access, _ in list_v2_accessible_shops(
            db_session,
            account_id=account.account_id,
            tenant_id=tenant_id,
        )
    ]
    return V2DataEnvelope(data=V2ShopListData(shops=shops))


@router.post("/context/select", response_model=V2DataEnvelope[V2ContextData], responses={403: {"model": V2ErrorEnvelope}})
def select_context_v2(
    payload: V2ContextSelectRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ContextData] | JSONResponse:
    context_session = select_v2_context(
        db_session,
        auth_session_id=account.auth_session_id,
        account_id=account.account_id,
        tenant_id=payload.tenant_id,
        shop_id=payload.shop_id,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    if context_session is None:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="shop_access_denied", message="Shop access denied")
            ).model_dump(),
        )

    permissions = context_session.permission_snapshot["permissions"]
    role_key = context_session.permission_snapshot["role_key"]
    return V2DataEnvelope(
        data=V2ContextData(
            context_token=context_session.context_session_id,
            context_session_id=context_session.context_session_id,
            account_id=context_session.account_id,
            tenant_id=context_session.tenant_id,
            shop_id=context_session.shop_id,
            membership_id=context_session.membership_id,
            role_key=role_key,
            permissions=permissions,
        )
    )


@router.get("/context/current", response_model=V2DataEnvelope[V2ContextData], responses={403: {"model": V2ErrorEnvelope}})
def current_context_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
) -> V2DataEnvelope[V2ContextData] | JSONResponse:
    if context.account_id != account.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2ContextData(
            context_token=context.context_session_id,
            context_session_id=context.context_session_id,
            account_id=context.account_id,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            membership_id=context.membership_id,
            role_key=context.role_key,
            permissions=list(context.permissions),
        )
    )
