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

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            shop_id TEXT,
            username TEXT UNIQUE,
            phone TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            nickname TEXT,
            avatar_url TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE TABLE IF NOT EXISTS verification_codes (
            code_id TEXT PRIMARY KEY,
            phone TEXT,
            email TEXT,
            code TEXT NOT NULL,
            code_type TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            session_token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
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
            event_subtype TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_verification_codes_phone ON verification_codes(phone);
        CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON verification_codes(email);
        CREATE INDEX IF NOT EXISTS idx_verification_codes_code ON verification_codes(code);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);

        CREATE TABLE IF NOT EXISTS token_usage (
            id TEXT PRIMARY KEY,
            shop_id TEXT,
            user_id TEXT,
            model TEXT,
            endpoint TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_shop ON token_usage(shop_id);
        CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id);
        CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at);
        """)


def seed_default_shop():
    """Seed a default shop and session for demo purposes."""
    with db() as conn:
        # Check if default shop exists
        row = conn.execute(
            "SELECT shop_id FROM shops WHERE shop_id = 'shop_default'"
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO shops (shop_id, name, owner_name, created_at) VALUES (?, ?, ?, ?)",
                ("shop_default", "演示五金店", "老板", _now())
            )

        # Check if default session exists
        row = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = 'sess_default'"
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO sessions (session_id, shop_id, title, created_at) VALUES (?, ?, ?, ?)",
                ("sess_default", "shop_default", "五金店工作群", _now())
            )

        return {"shop_id": "shop_default", "session_id": "sess_default"}


# ── User Authentication Functions ─────────────────────────────────────

def create_user(shop_id: str, username: str, password_hash: str, 
                phone: str = None, email: str = None, nickname: str = None) -> str:
    """Create a new user"""
    user_id = _new_id("user")
    with db() as conn:
        conn.execute(
            """INSERT INTO users 
            (user_id, shop_id, username, phone, email, password_hash, nickname, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, shop_id, username, phone, email, password_hash, nickname, _now(), _now())
        )
    return user_id


def get_user_by_username(username: str) -> dict:
    """Get user by username"""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_phone(phone: str) -> dict:
    """Get user by phone"""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict:
    """Get user by email"""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict:
    """Get user by ID"""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def update_user_login(user_id: str):
    """Update user last login time"""
    with db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE user_id = ?",
            (_now(), user_id)
        )


# ── Verification Code Functions ───────────────────────────────────────

def create_verification_code(phone: str = None, email: str = None, 
                            code_type: str = "login", expires_minutes: int = 5) -> str:
    """Create a verification code"""
    code_id = _new_id("code")
    code = "888888"  # Mock code for demo
    expires_at = datetime.now().timestamp() + (expires_minutes * 60)
    
    with db() as conn:
        conn.execute(
            """INSERT INTO verification_codes 
            (code_id, phone, email, code, code_type, expires_at, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code_id, phone, email, code, code_type, expires_at, _now())
        )
    return code


def verify_code(phone: str = None, email: str = None, code: str = None) -> bool:
    """Verify a verification code"""
    with db() as conn:
        query = "SELECT * FROM verification_codes WHERE code = ? AND used = 0 AND expires_at > ?"
        params = [code, datetime.now().timestamp()]
        
        if phone:
            query += " AND phone = ?"
            params.append(phone)
        elif email:
            query += " AND email = ?"
            params.append(email)
        
        row = conn.execute(query, params).fetchone()
        
        if row:
            # Mark code as used
            conn.execute(
                "UPDATE verification_codes SET used = 1 WHERE code_id = ?",
                (row["code_id"],)
            )
            return True
    return False


# ── Session Functions ───────────────────────────────────────────────

def create_session(user_id: str, expires_hours: int = 24) -> str:
    """Create a user session"""
    session_token = _new_id("token")
    expires_at = datetime.now().timestamp() + (expires_hours * 3600)
    
    with db() as conn:
        conn.execute(
            """INSERT INTO user_sessions 
            (session_token, user_id, expires_at, created_at) 
            VALUES (?, ?, ?, ?)""",
            (session_token, user_id, expires_at, _now())
        )
    return session_token


def get_session(session_token: str) -> dict:
    """Get session by token"""
    with db() as conn:
        row = conn.execute(
            """SELECT us.*, u.username, u.nickname, u.shop_id 
            FROM user_sessions us 
            JOIN users u ON us.user_id = u.user_id 
            WHERE us.session_token = ? AND us.expires_at > ?""",
            (session_token, datetime.now().timestamp())
        ).fetchone()
        return dict(row) if row else None


def delete_session(session_token: str):
    """Delete a session"""
    with db() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE session_token = ?",
            (session_token,)
        )


def cleanup_expired_sessions():
    """Clean up expired sessions"""
    with db() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE expires_at <= ?",
            (datetime.now().timestamp(),)
        )


# ── Password Hashing (Simple for Demo) ───────────────────────────────

def hash_password(password: str) -> str:
    """Simple password hash for demo (use bcrypt in production)"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed


def log_token_usage(shop_id: str, user_id: str, model: str, endpoint: str,
                    prompt_tokens: int, completion_tokens: int, latency_ms: int):
    """Log LLM token usage for billing and monitoring."""
    with db() as conn:
        conn.execute(
            """INSERT INTO token_usage (id, shop_id, user_id, model, endpoint,
               prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_new_id("tok"), shop_id, user_id, model, endpoint,
             prompt_tokens, completion_tokens, prompt_tokens + completion_tokens,
             latency_ms, _now())
        )