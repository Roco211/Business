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
    V2LogoutData,
    V2MeData,
    V2RefreshRequest,
    V2ShopData,
    V2ShopListData,
    V2TenantData,
    V2TenantListData,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.v2_identity import (
    authenticate_v2_account,
    get_v2_account,
    issue_v2_auth_session,
    list_v2_accessible_shops,
    list_v2_tenants_for_account,
    revoke_v2_auth_session,
    rotate_v2_auth_session,
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
    # Handle different auth methods
    account = None
    if payload.auth_method == "email_password":
        if not payload.email or not payload.password:
            return _unauthorized()
        account = authenticate_v2_account(db_session, payload.email, payload.password)
    elif payload.auth_method == "phone_code":
        # Demo mode: accept any phone with code "888888"
        if not payload.phone or payload.verification_code != "888888":
            return _unauthorized()
        # For demo: use default owner account directly without phone lookup
        from app.core.config import get_settings
        settings = get_settings()
        from app.models import V2Account
        # Try to find by default owner email in settings first, otherwise get first active account
        demo_email = settings.seed_owner_email or "owner@example.com"
        account = db_session.query(V2Account).filter(V2Account.email == demo_email).first()
        if account is None:
            # Fallback: get any active account
            account = db_session.query(V2Account).filter(V2Account.status == "active").first()
        if account is None:
            return _unauthorized()
    elif payload.auth_method == "phone_password":
        # Phone + password auth
        if not payload.phone or not payload.password:
            return _unauthorized()
        from app.models import V2Account
        from app.services.password import verify_password
        account = db_session.query(V2Account).filter(V2Account.phone == payload.phone).first()
        if account is None or not verify_password(payload.password, account.password_hash):
            return _unauthorized()
    
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
            refresh_token=issued.refresh_token,
            token_type="Bearer",
            account_id=issued.account_id,
        )
    )


@router.post("/auth/refresh", response_model=V2DataEnvelope[V2LoginData], responses={401: {"model": V2ErrorEnvelope}})
def refresh_v2(
    payload: V2RefreshRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2LoginData] | JSONResponse:
    issued = rotate_v2_auth_session(
        db_session,
        refresh_token=payload.refresh_token,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    if issued is None:
        return _unauthorized()

    return V2DataEnvelope(
        data=V2LoginData(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            token_type="Bearer",
            account_id=issued.account_id,
        )
    )


@router.post("/auth/logout", response_model=V2DataEnvelope[V2LogoutData], responses={401: {"model": V2ErrorEnvelope}})
def logout_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2LogoutData] | JSONResponse:
    revoked = revoke_v2_auth_session(
        db_session,
        auth_session_id=account.auth_session_id,
    )
    if not revoked:
        return _unauthorized()

    return V2DataEnvelope(data=V2LogoutData(status="logged_out"))


@router.get("/me", response_model=V2DataEnvelope[V2MeData])
def me_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2MeData] | JSONResponse:
    current_account = get_v2_account(db_session, account.account_id)
    if current_account is None:
        return _unauthorized()

    return V2DataEnvelope(
        data=V2MeData(
            account_id=current_account.account_id,
            email=current_account.email,
            display_name=current_account.display_name,
            status=current_account.status,
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
