from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import SessionRecord, Shop
from app.services.bootstrap import ensure_default_context


def create_test_session(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'bootstrap.db').as_posix()}"
    engine = create_engine(
        database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory()


def test_ensure_default_context_creates_shop_and_session(tmp_path) -> None:
    engine, db_session = create_test_session(tmp_path)
    try:
        context = ensure_default_context(db_session)

        assert context.shop.shop_id == "shop_default"
        assert context.shop.low_confidence_threshold == Decimal("0.8500")
        assert context.session.session_id == "sess_default"
        assert context.session.participants == ["xiaoya", "laoli"]

        shops = db_session.scalars(select(Shop)).all()
        sessions = db_session.scalars(select(SessionRecord)).all()
        assert len(shops) == 1
        assert len(sessions) == 1
    finally:
        db_session.close()
        engine.dispose()


def test_ensure_default_context_is_idempotent(tmp_path) -> None:
    engine, db_session = create_test_session(tmp_path)
    try:
        first = ensure_default_context(db_session)
        second = ensure_default_context(db_session)

        assert first.shop.shop_id == second.shop.shop_id
        assert first.session.session_id == second.session.session_id
        assert len(db_session.scalars(select(Shop)).all()) == 1
        assert len(db_session.scalars(select(SessionRecord)).all()) == 1
    finally:
        db_session.close()
        engine.dispose()


def test_ensure_default_context_recovers_from_shop_creation_race(tmp_path) -> None:
    engine, db_session = create_test_session(tmp_path)
    competing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )()

    original_get = db_session.get
    race_triggered = False

    def racing_get(model, identity, *args, **kwargs):
        nonlocal race_triggered
        result = original_get(model, identity, *args, **kwargs)

        if not race_triggered and model is Shop and identity == "shop_default" and result is None:
            competing_session.add(
                Shop(
                    shop_id="shop_default",
                    name="演示店铺",
                    owner_name="默认老板",
                    industry="retail",
                    locale="zh-CN",
                    timezone="Asia/Shanghai",
                    require_price_confirmation=True,
                    require_new_item_confirmation=True,
                    low_confidence_threshold=Decimal("0.8500"),
                    default_low_stock_threshold=None,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            competing_session.commit()
            race_triggered = True

        return result

    db_session.get = racing_get  # type: ignore[method-assign]

    try:
        context = ensure_default_context(db_session)

        assert context.shop.shop_id == "shop_default"
        assert context.session.session_id == "sess_default"
        assert len(db_session.scalars(select(Shop)).all()) == 1
    finally:
        competing_session.close()
        db_session.close()
        engine.dispose()
