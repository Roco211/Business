from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_v2_baseline_schema(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "alembic.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert "alembic_version" in table_names
    assert "v2_accounts" in table_names
    assert "v2_tenants" in table_names
    assert "v2_shops" in table_names
    assert "v2_context_sessions" in table_names
    assert "v2_conversation_sessions" in table_names
    assert "v2_messages" in table_names
    assert "v2_task_runs" in table_names
    assert "v2_clarifications" in table_names
    assert "v2_confirmations" in table_names
    assert "v2_task_drafts" in table_names
    assert "v2_inventory_items" in table_names
    assert "v2_inventory_stock_snapshots" in table_names
    assert "v2_inventory_ledger_events" in table_names
    assert "v2_audit_logs" in table_names
    assert "v2_outbox_events" in table_names
    assert "v2_session_stream_events" in table_names
    assert "v2_media_assets" in table_names
    assert "v2_documents" in table_names
    assert "v2_model_call_logs" in table_names
    assert "v2_sales_orders" in table_names
    assert "v2_sales_order_lines" in table_names
    assert "v2_purchase_orders" in table_names
    assert "v2_purchase_order_lines" in table_names
    assert "v2_customers" in table_names
    assert "v2_suppliers" in table_names
    assert "v2_export_jobs" in table_names

    assert not any(
        table_name in table_names
        for table_name in {
            "shops",
            "sessions",
            "messages",
            "task_runs",
            "inventory_items",
            "inventory_events",
            "audit_logs",
            "media_uploads",
            "ocr_documents",
            "owner_accounts",
            "shop_memberships",
            "auth_sessions",
            "pilot_controls",
        }
    )

    assert {"tenant_id", "owner_account_id", "plan_code", "status"} <= {
        column["name"] for column in inspector.get_columns("v2_tenants")
    }
    assert {"session_id", "tenant_id", "shop_id", "last_event_seq"} <= {
        column["name"] for column in inspector.get_columns("v2_conversation_sessions")
    }
    assert {"inventory_item_id", "tenant_id", "sku", "name", "status"} <= {
        column["name"] for column in inspector.get_columns("v2_inventory_items")
    }
    assert {"event_id", "tenant_id", "shop_id", "session_id", "seq", "event_type", "payload"} <= {
        column["name"] for column in inspector.get_columns("v2_session_stream_events")
    }
    assert {"last_error_code", "last_error_message", "processed_at", "updated_at"} <= {
        column["name"] for column in inspector.get_columns("v2_outbox_events")
    }
