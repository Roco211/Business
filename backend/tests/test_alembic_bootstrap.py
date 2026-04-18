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
    assert "media_uploads" in inspector.get_table_names()
    assert "ocr_documents" in inspector.get_table_names()
    assert "session_stream_events" in inspector.get_table_names()
    assert "owner_accounts" in inspector.get_table_names()
    assert "shop_memberships" in inspector.get_table_names()
    assert "auth_sessions" in inspector.get_table_names()
    assert "v2_media_assets" in inspector.get_table_names()
    assert "v2_model_call_logs" in inspector.get_table_names()
    assert "v2_session_stream_events" in inspector.get_table_names()
    assert {"shop_id", "name", "timezone"} <= {column["name"] for column in inspector.get_columns("shops")}
    assert {"session_id", "shop_id", "participants", "last_event_seq"} <= {
        column["name"] for column in inspector.get_columns("sessions")
    }
    assert {"last_event_seq"} <= {
        column["name"] for column in inspector.get_columns("v2_conversation_sessions")
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
    assert {"media_id", "shop_id", "media_type", "status", "public_url"} <= {
        column["name"] for column in inspector.get_columns("media_uploads")
    }
    assert {"media_asset_id", "tenant_id", "shop_id", "context_session_id", "uploaded_by_account_id"} <= {
        column["name"] for column in inspector.get_columns("v2_media_assets")
    }
    assert {"model_call_log_id", "tenant_id", "shop_id", "context_session_id", "provider_type", "model_name"} <= {
        column["name"] for column in inspector.get_columns("v2_model_call_logs")
    }
    assert {"ocr_document_id", "shop_id", "media_id", "document_type", "status", "extracted_fields"} <= {
        column["name"] for column in inspector.get_columns("ocr_documents")
    }
    assert {"event_id", "session_id", "seq", "event_type", "payload"} <= {
        column["name"] for column in inspector.get_columns("session_stream_events")
    }
    assert {"actor_id", "email", "password_hash", "password_salt", "status"} <= {
        column["name"] for column in inspector.get_columns("owner_accounts")
    }
    assert {"membership_id", "shop_id", "actor_id", "role", "is_default_shop"} <= {
        column["name"] for column in inspector.get_columns("shop_memberships")
    }
    assert {"auth_session_id", "shop_id", "actor_id", "session_token_hash", "expires_at"} <= {
        column["name"] for column in inspector.get_columns("auth_sessions")
    }
    assert {"event_id", "tenant_id", "shop_id", "session_id", "seq", "event_type", "payload"} <= {
        column["name"] for column in inspector.get_columns("v2_session_stream_events")
    }
    assert {"last_error_code", "last_error_message", "processed_at", "updated_at"} <= {
        column["name"] for column in inspector.get_columns("v2_outbox_events")
    }
    assert inspector.get_foreign_keys("sessions")[0]["referred_table"] == "shops"

    auth_session_fks = inspector.get_foreign_keys("auth_sessions")
    membership_fk = next(
        fk
        for fk in auth_session_fks
        if fk["referred_table"] == "shop_memberships"
        and set(fk["constrained_columns"]) == {"shop_id", "actor_id"}
    )
    assert set(membership_fk["referred_columns"]) == {"shop_id", "actor_id"}

    message_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    task_indexes = {index["name"] for index in inspector.get_indexes("task_runs")}
    inventory_item_indexes = {index["name"] for index in inspector.get_indexes("inventory_items")}
    inventory_event_indexes = {index["name"] for index in inspector.get_indexes("inventory_events")}
    audit_log_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    media_upload_indexes = {index["name"] for index in inspector.get_indexes("media_uploads")}
    ocr_document_indexes = {index["name"] for index in inspector.get_indexes("ocr_documents")}
    session_stream_indexes = {index["name"] for index in inspector.get_indexes("session_stream_events")}
    auth_session_indexes = {index["name"] for index in inspector.get_indexes("auth_sessions")}
    v2_session_stream_indexes = {index["name"] for index in inspector.get_indexes("v2_session_stream_events")}
    assert "ix_messages_session_created_at" in message_indexes
    assert "ix_task_runs_session_updated_at" in task_indexes
    assert "ix_task_runs_source_message_id" in task_indexes
    assert "ix_inventory_items_shop_id_name" in inventory_item_indexes
    assert "ix_inventory_events_shop_id_item_created_at" in inventory_event_indexes
    assert "ix_audit_logs_shop_id_created_at" in audit_log_indexes
    assert "ix_media_uploads_shop_id_created_at" in media_upload_indexes
    assert "ix_ocr_documents_shop_id_created_at" in ocr_document_indexes
    assert "ix_session_stream_events_session_id_seq" in session_stream_indexes
    assert "ix_auth_sessions_actor_id" in auth_session_indexes
    assert "ix_auth_sessions_shop_id" in auth_session_indexes
    assert "ix_v2_session_stream_events_session_id_seq" in v2_session_stream_indexes
