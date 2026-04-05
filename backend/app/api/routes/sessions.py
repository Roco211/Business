from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorEnvelope
from app.contracts.session import SessionBootstrapData
from app.db.session import get_db_session
from app.models import SessionRecord
from app.services.bootstrap import ensure_default_context

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
    session_record = db_session.scalar(
        select(SessionRecord)
        .where(SessionRecord.shop_id == auth.shop_id)
        .order_by(SessionRecord.created_at.asc(), SessionRecord.session_id.asc())
    )
    if session_record is None:
        context = ensure_default_context(db_session)
        if context.shop.shop_id == auth.shop_id:
            session_record = context.session
        else:
            raise LookupError(auth.shop_id)

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=session_record.session_id,
            session_type=session_record.session_type,
            title=session_record.title,
            participants=session_record.participants,
        )
    )
