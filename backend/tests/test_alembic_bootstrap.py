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
    assert "messages" in inspector.get_table_names()
    assert "task_runs" in inspector.get_table_names()
    assert "inventory_items" in inspector.get_table_names()
    assert "inventory_events" in inspector.get_table_names()
    assert "audit_logs" in inspector.get_table_names()
    assert "session_stream_events" in inspector.get_table_names()
    assert {"shop_id", "name", "timezone"} <= {column["name"] for column in inspector.get_columns("shops")}
    assert {"session_id", "shop_id", "participants", "last_event_seq"} <= {
        column["name"] for column in inspector.get_columns("sessions")
    }
    assert {"message_id", "session_id", "message_type", "client_request_id", "task_run_id"} <= {
        column["name"] for column in inspector.get_columns("messages")
    }
    assert {"task_run_id", "session_id", "source_message_id", "task_type", "status"} <= {
        column["name"] for column in inspector.get_columns("task_runs")
    }
    assert {"item_id", "shop_id", "name", "default_unit", "current_stock"} <= {
        column["name"] for column in inspector.get_columns("inventory_items")
    }
    assert {"inventory_event_id", "shop_id", "item_id", "event_type", "quantity_after"} <= {
        column["name"] for column in inspector.get_columns("inventory_events")
    }
    assert {"audit_log_id", "shop_id", "scope", "action", "metadata"} <= {
        column["name"] for column in inspector.get_columns("audit_logs")
    }
    assert {"event_id", "session_id", "seq", "event_type", "payload"} <= {
        column["name"] for column in inspector.get_columns("session_stream_events")
    }
    assert inspector.get_foreign_keys("sessions")[0]["referred_table"] == "shops"

    message_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    task_indexes = {index["name"] for index in inspector.get_indexes("task_runs")}
    inventory_item_indexes = {index["name"] for index in inspector.get_indexes("inventory_items")}
    inventory_event_indexes = {index["name"] for index in inspector.get_indexes("inventory_events")}
    audit_log_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    session_stream_indexes = {index["name"] for index in inspector.get_indexes("session_stream_events")}
    assert "ix_messages_session_created_at" in message_indexes
    assert "ix_task_runs_session_updated_at" in task_indexes
    assert "ix_task_runs_source_message_id" in task_indexes
    assert "ix_inventory_items_shop_id_name" in inventory_item_indexes
    assert "ix_inventory_events_shop_id_item_created_at" in inventory_event_indexes
    assert "ix_audit_logs_shop_id_created_at" in audit_log_indexes
    assert "ix_session_stream_events_session_id_seq" in session_stream_indexes
