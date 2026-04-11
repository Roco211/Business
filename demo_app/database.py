"""
SQLite database layer for the AI Hardware Store Manager.
Lightweight alternative to MySQL — no external DB needed.
"""
import sqlite3
import json
import uuid
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/data/store.db")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_name TEXT NOT NULL DEFAULT '老板',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory_items (
            item_id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            default_unit TEXT DEFAULT '件',
            current_stock REAL NOT NULL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            low_stock_threshold REAL DEFAULT 5,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE TABLE IF NOT EXISTS inventory_events (
            event_id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT DEFAULT '件',
            unit_price REAL DEFAULT 0,
            reason TEXT DEFAULT '',
            source TEXT DEFAULT 'ai',
            task_run_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
            FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            title TEXT DEFAULT '五金店工作群',
            created_at TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'text',
            text TEXT,
            task_run_id TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS task_runs (
            task_run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            assigned_employee_id TEXT DEFAULT 'xiaoya',
            transcript TEXT,
            result_summary TEXT,
            error_code TEXT,
            error_message TEXT,
            payload TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS confirmations (
            confirmation_id TEXT PRIMARY KEY,
            task_run_id TEXT NOT NULL,
            confirmation_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            fields TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE TABLE IF NOT EXISTS confirmations (
            confirmation_id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            confirmation_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            request_data TEXT,
            response_data TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );
        """)


def seed_default_shop(shop_id: str = "shop_hardware", name: str = "五金百货店"):
    with db() as conn:
        existing = conn.execute(
            "SELECT shop_id FROM shops WHERE shop_id = ?", (shop_id,)
        ).fetchone()
        if not existing:
            now = _now()
            conn.execute(
                "INSERT INTO shops (shop_id, name, owner_name, created_at) VALUES (?, ?, ?, ?)",
                (shop_id, name, "老板", now),
            )
            session_id = _new_id("sess")
            conn.execute(
                "INSERT INTO sessions (session_id, shop_id, title, created_at) VALUES (?, ?, ?, ?)",
                (session_id, shop_id, "五金店工作群", now),
            )
            # Seed some common hardware store items
            items = [
                ("螺丝钉 M6", "紧固件", "盒", 50, 8.0),
                ("螺母 M6", "紧固件", "包", 30, 5.0),
                ("铁丝 1mm", "线材", "卷", 15, 12.0),
                ("砂纸 180目", "打磨", "张", 100, 1.5),
                ("生料带", "水暖", "卷", 40, 2.0),
                ("电线 2.5mm²", "电气", "米", 200, 3.5),
                ("开关面板", "电气", "个", 25, 15.0),
                ("水管接头 DN20", "水暖", "个", 35, 6.0),
                ("万能胶", "粘合剂", "支", 20, 12.0),
                ("油漆刷 2寸", "涂装", "把", 18, 5.0),
            ]
            for name_item, cat, unit, stock, price in items:
                item_id = _new_id("item")
                conn.execute(
                    """INSERT INTO inventory_items
                    (item_id, shop_id, name, category, default_unit, current_stock, unit_price, low_stock_threshold, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 5, 1, ?, ?)""",
                    (item_id, shop_id, name_item, cat, unit, stock, price, now, now),
                )
            return {"shop_id": shop_id, "session_id": session_id}
        else:
            row = conn.execute(
                "SELECT session_id FROM sessions WHERE shop_id = ? LIMIT 1", (shop_id,)
            ).fetchone()
            return {"shop_id": shop_id, "session_id": row["session_id"] if row else None}
