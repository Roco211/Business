from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorEnvelope
from app.contracts.session import SessionBootstrapData
from app.db.session import get_db_session
from app.services.bootstrap import ensure_shop_context

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "/bootstrap",
    response_model=DataEnvelope[SessionBootstrapData],
    responses={401: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def bootstrap_session(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[SessionBootstrapData]:
    context = ensure_shop_context(
        db_session,
        shop_id=auth.shop_id,
        owner_actor_id=auth.actor_id,
    )
    if context is None:
        raise LookupError(auth.shop_id)

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=context.session.session_id,
            session_type=context.session.session_type,
            title=context.session.title,
            participants=context.session.participants,
        )
    )
