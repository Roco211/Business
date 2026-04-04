from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_shops_and_sessions(tmp_path) -> None:
    database_path = tmp_path / "alembic.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)

    assert "shops" in inspector.get_table_names()
    assert "sessions" in inspector.get_table_names()
    assert {"shop_id", "name", "timezone"} <= {column["name"] for column in inspector.get_columns("shops")}
    assert {"session_id", "shop_id", "participants", "last_event_seq"} <= {
        column["name"] for column in inspector.get_columns("sessions")
    }
    assert inspector.get_foreign_keys("sessions")[0]["referred_table"] == "shops"
