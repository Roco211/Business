"""
AI五金店大管家 - 后端服务
集成火山引擎大模型的五金店库存管理AI系统
"""
import json
import os
import time
import threading
from collections import deque
from datetime import datetime
from contextlib import asynccontextmanager

import asyncio
import json as json_lib
from typing import List
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from demo_app.database import (
    db, init_db, seed_default_shop, _new_id, _now,
    create_user, get_user_by_username, get_user_by_phone, get_user_by_email,
    update_user_login, create_verification_code, verify_code,
    create_session, get_session, delete_session, hash_password, verify_password
)
from demo_app.llm_service import classify_intent, extract_entities, generate_response, chat_reply, chat_stream


# ── Pydantic Models ────────────────────────────────────────────────────

# Authentication Models
class SendCodeRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    code_type: str = "login"  # login, register, reset_password

class VerifyCodeRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    code: str = Field(..., min_length=6, max_length=6)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    phone: str | None = None
    email: str | None = None
    nickname: str | None = None
    code: str = Field(..., min_length=6, max_length=6)

class LoginRequest(BaseModel):
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    password: str | None = None
    code: str | None = None  # For verification code login

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: str | None = None
    username: str | None = None
    nickname: str | None = None
    token: str | None = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    intent: str
    action: str
    data: dict | None = None

class ItemCreate(BaseModel):
    name: str
    category: str = ""
    default_unit: str = "件"
    current_stock: float = 0
    unit_price: float = 0
    low_stock_threshold: float = 5

class StockInRequest(BaseModel):
    item_id: str
    quantity: float
    unit_price: float | None = None
    reason: str = ""

class StockOutRequest(BaseModel):
    item_id: str
    quantity: float
    reason: str = ""

class CorrectionRequest(BaseModel):
    item_id: str
    target_stock: float
    reason: str

class ApproveRequest(BaseModel):
    confirmation_id: str
    approved: bool = True
    # For editing fields before approval
    item_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None


# ── WebSocket Connection Manager ───────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ── App Lifecycle ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    info = seed_default_shop()
    app.state.shop_id = info["shop_id"]
    app.state.session_id = info["session_id"]
    app.state.ws_manager = manager
    print(f"[Startup] Shop: {info['shop_id']}, Session: {info['session_id']}")
    yield

SHOP_ID = "shop_default"

app = FastAPI(
    title="AI五金店大管家",
    description="集成火山引擎大模型的智能五金店库存管理系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Logging Middleware + Debug Server on 8082 ──────────────────

REQUEST_LOGS = deque(maxlen=200)  # ring buffer of recent requests
LOG_LOCK = threading.Lock()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    # Read body for logging (non-streaming only)
    body_bytes = await request.body()
    body_text = ""
    if body_bytes and len(body_bytes) < 4096:
        try:
            body_text = body_bytes.decode("utf-8", errors="replace")
        except Exception:
            body_text = "<binary>"

    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 1)

    entry = {
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
        "query": str(request.query_params) if request.query_params else "",
        "body": body_text[:500] if body_text else "",
    }
    with LOG_LOCK:
        REQUEST_LOGS.appendleft(entry)

    return response


def _run_admin_server():
    """Admin dashboard server on port 8082 with full management UI."""
    import uvicorn
    from fastapi import FastAPI as AdminApp
    from fastapi.staticfiles import StaticFiles as AdminStatic
    from fastapi.responses import HTMLResponse as AdminHTML

    admin_app = AdminApp(title="AI Store Manager Admin")

    # Load admin HTML
    _admin_html_path = os.path.join(BASE_DIR, "admin", "index.html")
    _admin_html = ""
    if os.path.isfile(_admin_html_path):
        with open(_admin_html_path, "r", encoding="utf-8") as f:
            _admin_html = f.read()

    # Admin static assets (if any)
    _admin_static_dir = os.path.join(BASE_DIR, "admin", "static")
    if os.path.isdir(_admin_static_dir):
        admin_app.mount("/static", AdminStatic(directory=_admin_static_dir), name="admin-static")

    @admin_app.get("/")
    def admin_dashboard():
        if _admin_html:
            return AdminHTML(content=_admin_html)
        return AdminHTML(content="<h1>Admin dashboard not found</h1>")

    @admin_app.get("/api/logs")
    def get_logs(limit: int = 100):
        with LOG_LOCK:
            return list(REQUEST_LOGS)[:limit]

    @admin_app.post("/api/clear")
    def clear_logs():
        with LOG_LOCK:
            REQUEST_LOGS.clear()
        return {"ok": True}

    @admin_app.get("/api/admin/users")
    def admin_list_users():
        """List all registered users."""
        try:
            with db() as conn:
                rows = conn.execute(
                    "SELECT user_id, shop_id, username, phone, email, nickname, status, created_at, last_login_at FROM users ORDER BY created_at DESC LIMIT 200"
                ).fetchall()
                return {
                    "data": [{
                        "user_id": r["user_id"],
                        "shop_id": r["shop_id"],
                        "username": r["username"],
                        "phone": r["phone"],
                        "email": r["email"],
                        "nickname": r["nickname"],
                        "status": r["status"] or "active",
                        "created_at": r["created_at"],
                        "last_login_at": r["last_login_at"],
                    } for r in rows]
                }
        except Exception as e:
            return {"data": [], "error": str(e)}

    # Proxy endpoints for admin dashboard to call main app APIs
    @admin_app.get("/api/v1/{path:path}")
    async def proxy_get(path: str, request: Request):
        """Proxy GET requests to main app."""
        import httpx
        params = dict(request.query_params)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:8081/api/v1/{path}", params=params)
            return resp.json()

    @admin_app.post("/api/v1/{path:path}")
    async def proxy_post(path: str, request: Request):
        """Proxy POST requests to main app."""
        import httpx
        body = await request.json()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"http://127.0.0.1:8081/api/v1/{path}", json=body)
            return resp.json()

    uvicorn.run(admin_app, host="0.0.0.0", port=8082, log_level="warning")


# Start admin server in background thread with its own event loop
def _start_admin():
    import asyncio as _aio
    loop = _aio.new_event_loop()
    _aio.set_event_loop(loop)
    _run_admin_server()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_admin_thread = threading.Thread(target=_start_admin, daemon=True)
_admin_thread.start()
print("[Admin] Dashboard starting on http://0.0.0.0:8082")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ── Health & Info ──────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "shop_id": SHOP_ID, "llm": "volcengine"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json_lib.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "subscribe":
                # Subscribe to specific events
                await websocket.send_json({"type": "subscribed", "channels": message.get("channels", [])})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Authentication Endpoints ──────────────────────────────────────────

@app.post("/api/v1/auth/send-code")
def send_verification_code(req: SendCodeRequest):
    """Send verification code (mock: 888888)"""
    if not req.phone and not req.email:
        return {"success": False, "message": "请提供手机号或邮箱"}
    
    # Create verification code
    code = create_verification_code(
        phone=req.phone,
        email=req.email,
        code_type=req.code_type
    )
    
    # In real implementation, send SMS or email here
    # For demo, we just return success with hint
    return {
        "success": True,
        "message": f"验证码已发送（演示模式：验证码为 {code}）",
        "code": code  # Only for demo! Remove in production
    }


@app.post("/api/v1/auth/verify-code")
def verify_verification_code(req: VerifyCodeRequest):
    """Verify verification code"""
    if not req.phone and not req.email:
        return {"success": False, "message": "请提供手机号或邮箱"}
    
    is_valid = verify_code(
        phone=req.phone,
        email=req.email,
        code=req.code
    )
    
    if is_valid:
        return {"success": True, "message": "验证码验证成功"}
    else:
        return {"success": False, "message": "验证码无效或已过期"}


@app.post("/api/v1/auth/register", response_model=LoginResponse)
def register(req: RegisterRequest):
    """User registration"""
    # Check if verification code is valid
    is_valid = verify_code(
        phone=req.phone,
        email=req.email,
        code=req.code
    )
    
    if not is_valid:
        return LoginResponse(
            success=False,
            message="验证码无效或已过期"
        )
    
    # Check if user already exists
    if get_user_by_username(req.username):
        return LoginResponse(
            success=False,
            message="用户名已存在"
        )
    
    if req.phone and get_user_by_phone(req.phone):
        return LoginResponse(
            success=False,
            message="手机号已注册"
        )
    
    if req.email and get_user_by_email(req.email):
        return LoginResponse(
            success=False,
            message="邮箱已注册"
        )
    
    # Create user
    password_hash = hash_password(req.password)
    user_id = create_user(
        shop_id=SHOP_ID,
        username=req.username,
        password_hash=password_hash,
        phone=req.phone,
        email=req.email,
        nickname=req.nickname
    )
    
    # Create session
    token = create_session(user_id)
    
    return LoginResponse(
        success=True,
        message="注册成功",
        user_id=user_id,
        username=req.username,
        nickname=req.nickname,
        token=token
    )


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """User login (password or verification code)"""
    user = None
    
    # Find user by username, phone, or email
    if req.username:
        user = get_user_by_username(req.username)
    elif req.phone:
        user = get_user_by_phone(req.phone)
    elif req.email:
        user = get_user_by_email(req.email)
    
    if not user:
        return LoginResponse(
            success=False,
            message="用户不存在"
        )
    
    # Check login method
    if req.password:
        # Password login
        if not verify_password(req.password, user["password_hash"]):
            return LoginResponse(
                success=False,
                message="密码错误"
            )
    elif req.code:
        # Verification code login
        is_valid = verify_code(
            phone=req.phone,
            email=req.email,
            code=req.code
        )
        if not is_valid:
            return LoginResponse(
                success=False,
                message="验证码无效或已过期"
            )
    else:
        return LoginResponse(
            success=False,
            message="请提供密码或验证码"
        )
    
    # Update last login
    update_user_login(user["user_id"])
    
    # Create session
    token = create_session(user["user_id"])
    
    return LoginResponse(
        success=True,
        message="登录成功",
        user_id=user["user_id"],
        username=user["username"],
        nickname=user["nickname"],
        token=token
    )


@app.post("/api/v1/auth/logout")
def logout(token: str = None):
    """User logout"""
    if token:
        delete_session(token)
    return {"success": True, "message": "已退出登录"}


@app.get("/api/v1/auth/me")
def get_current_user(token: str = None):
    """Get current user info"""
    if not token:
        return {"success": False, "message": "未提供令牌"}
    
    session = get_session(token)
    if not session:
        return {"success": False, "message": "会话无效或已过期"}
    
    return {
        "success": True,
        "data": {
            "user_id": session["user_id"],
            "username": session["username"],
            "nickname": session["nickname"],
            "shop_id": session["shop_id"]
        }
    }


# ── AI Chat Endpoint (Main entry point) ───────────────────────────────

@app.post("/api/v1/chat", response_model=ChatResponse)
def ai_chat(req: ChatRequest):
    """
    Main AI chat endpoint. Uses LLM to:
    1. Classify intent
    2. Extract entities
    3. Execute action
    4. Generate natural language response
    """
    session_id = req.session_id or _get_default_session()
    user_msg = req.message.strip()

    # Step 1: Classify intent
    intent_result = classify_intent(user_msg)
    intent = intent_result["intent"]

    # Step 2: Route by intent
    if intent == "stock_in":
        return _handle_stock_in(user_msg, session_id)
    elif intent == "stock_out":
        return _handle_stock_out(user_msg, session_id)
    elif intent == "stock_query":
        return _handle_stock_query(user_msg, session_id)
    elif intent == "item_create":
        return _handle_item_create(user_msg, session_id)
    elif intent == "correction":
        return _handle_correction(user_msg, session_id)
    elif intent == "list_items":
        return _handle_list_items(session_id)
    elif intent == "low_stock":
        return _handle_low_stock(session_id)
    else:
        return _handle_general_chat(user_msg, session_id)


def _get_default_session() -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT session_id FROM sessions WHERE shop_id = ? LIMIT 1", (SHOP_ID,)
        ).fetchone()
        return row["session_id"] if row else "sess_default"


# ── Handler Functions ──────────────────────────────────────────────────

def _handle_stock_in(user_msg: str, session_id: str) -> ChatResponse:
    """Handle stock-in operations via natural language."""
    entities = extract_entities(user_msg, "stock_in")
    items = entities.get("items", [])

    if not items:
        reply = generate_response(user_msg, {"success": False, "error": "没有识别到商品信息"})
        return ChatResponse(reply=reply, intent="stock_in", action="error",
                          data={"error": "未识别到商品"})

    results = []
    with db() as conn:
        for item_info in items:
            name = item_info.get("name", "")
            qty = float(item_info.get("quantity", 0))
            unit = item_info.get("unit", "件")
            price = item_info.get("price")

            if not name or qty <= 0:
                continue

            # Find or create item
            item = conn.execute(
                "SELECT * FROM inventory_items WHERE shop_id = ? AND name LIKE ? AND is_active = 1",
                (SHOP_ID, f"%{name}%")
            ).fetchone()

            if not item:
                # Create new item
                item_id = _new_id("item")
                now = _now()
                conn.execute(
                    """INSERT INTO inventory_items
                    (item_id, shop_id, name, default_unit, current_stock, unit_price, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item_id, SHOP_ID, name, unit, qty, price or 0, now, now)
                )
                item_name = name
            else:
                item_id = item["item_id"]
                item_name = item["name"]
                new_stock = item["current_stock"] + qty
                conn.execute(
                    "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
                    (new_stock, _now(), item_id)
                )

            # Record event
            event_id = _new_id("evt")
            conn.execute(
                """INSERT INTO inventory_events
                (event_id, shop_id, item_id, event_type, quantity, unit, unit_price, reason, source, created_at)
                VALUES (?, ?, ?, 'stock_in', ?, ?, ?, ?, 'ai', ?)""",
                (event_id, SHOP_ID, item_id, qty, unit, price or 0,
                 entities.get("note", "AI入库"), _now())
            )

            # Audit log
            log_id = _new_id("log")
            conn.execute(
                """INSERT INTO audit_logs (log_id, shop_id, event_type, entity_type, entity_id, details, created_at)
                VALUES (?, ?, 'stock_in', 'item', ?, ?, ?)""",
                (log_id, SHOP_ID, item_id,
                 json.dumps({"name": item_name, "quantity": qty, "unit": unit}, ensure_ascii=False),
                 _now())
            )

            results.append({"name": item_name, "quantity": qty, "unit": unit})

    action_result = {"success": True, "action": "入库", "items": results}
    reply = generate_response(user_msg, action_result)
    
    # WebSocket broadcast removed for synchronous compatibility
    
    return ChatResponse(reply=reply, intent="stock_in", action="stock_in", data=action_result)


def _handle_stock_out(user_msg: str, session_id: str) -> ChatResponse:
    """Handle stock-out operations."""
    entities = extract_entities(user_msg, "stock_out")
    items = entities.get("items", [])

    if not items:
        reply = generate_response(user_msg, {"success": False, "error": "没有识别到商品信息"})
        return ChatResponse(reply=reply, intent="stock_out", action="error")

    results = []
    with db() as conn:
        for item_info in items:
            name = item_info.get("name", "")
            qty = float(item_info.get("quantity", 0))

            if not name or qty <= 0:
                continue

            item = conn.execute(
                "SELECT * FROM inventory_items WHERE shop_id = ? AND name LIKE ? AND is_active = 1",
                (SHOP_ID, f"%{name}%")
            ).fetchone()

            if not item:
                results.append({"name": name, "error": "商品不存在"})
                continue

            if item["current_stock"] < qty:
                results.append({
                    "name": item["name"],
                    "error": f"库存不足（当前{item['current_stock']}{item['default_unit']}）"
                })
                continue

            new_stock = item["current_stock"] - qty
            conn.execute(
                "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
                (new_stock, _now(), item["item_id"])
            )

            event_id = _new_id("evt")
            conn.execute(
                """INSERT INTO inventory_events
                (event_id, shop_id, item_id, event_type, quantity, unit, reason, source, created_at)
                VALUES (?, ?, ?, 'stock_out', ?, ?, ?, 'ai', ?)""",
                (event_id, SHOP_ID, item["item_id"], qty, item["default_unit"],
                 entities.get("reason", "AI出库"), _now())
            )

            log_id = _new_id("log")
            conn.execute(
                """INSERT INTO audit_logs (log_id, shop_id, event_type, entity_type, entity_id, details, created_at)
                VALUES (?, ?, 'stock_out', 'item', ?, ?, ?)""",
                (log_id, SHOP_ID, item["item_id"],
                 json.dumps({"name": item["name"], "quantity": qty}, ensure_ascii=False), _now())
            )

            results.append({"name": item["name"], "quantity": qty, "remaining": new_stock})

    action_result = {"success": True, "action": "出库", "items": results}
    reply = generate_response(user_msg, action_result)
    
    # WebSocket broadcast removed for synchronous compatibility
    
    return ChatResponse(reply=reply, intent="stock_out", action="stock_out", data=action_result)


def _handle_stock_query(user_msg: str, session_id: str) -> ChatResponse:
    """Handle stock query."""
    entities = extract_entities(user_msg, "stock_query")
    item_name = entities.get("item_name", "")
    query_type = entities.get("query_type", "specific")

    with db() as conn:
        if query_type == "all" or not item_name:
            items = conn.execute(
                "SELECT * FROM inventory_items WHERE shop_id = ? AND is_active = 1 ORDER BY name",
                (SHOP_ID,)
            ).fetchall()
            results = [{"name": i["name"], "stock": i["current_stock"], "unit": i["default_unit"],
                        "low": i["current_stock"] <= i["low_stock_threshold"]} for i in items]
        else:
            items = conn.execute(
                "SELECT * FROM inventory_items WHERE shop_id = ? AND name LIKE ? AND is_active = 1",
                (SHOP_ID, f"%{item_name}%")
            ).fetchall()
            results = [{"name": i["name"], "stock": i["current_stock"], "unit": i["default_unit"],
                        "low": i["current_stock"] <= i["low_stock_threshold"]} for i in items]

    action_result = {"success": True, "action": "查询", "items": results}
    reply = generate_response(user_msg, action_result)
    return ChatResponse(reply=reply, intent="stock_query", action="query", data=action_result)


def _handle_item_create(user_msg: str, session_id: str) -> ChatResponse:
    """Handle new item creation."""
    entities = extract_entities(user_msg, "item_create")
    name = entities.get("name", "")
    if not name:
        reply = "老板，请告诉我新商品的名称。"
        return ChatResponse(reply=reply, intent="item_create", action="error")

    with db() as conn:
        existing = conn.execute(
            "SELECT item_id FROM inventory_items WHERE shop_id = ? AND name = ? AND is_active = 1",
            (SHOP_ID, name)
        ).fetchone()
        if existing:
            reply = f"老板，{name} 已经在库存里了。"
            return ChatResponse(reply=reply, intent="item_create", action="error",
                              data={"error": "商品已存在"})

        item_id = _new_id("item")
        now = _now()
        conn.execute(
            """INSERT INTO inventory_items
            (item_id, shop_id, name, category, default_unit, current_stock, unit_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, SHOP_ID, name,
             entities.get("category", ""),
             entities.get("unit", "件"),
             float(entities.get("initial_stock", 0)),
             float(entities.get("price", 0)),
             now, now)
        )

        log_id = _new_id("log")
        conn.execute(
            """INSERT INTO audit_logs (log_id, shop_id, event_type, entity_type, entity_id, details, created_at)
            VALUES (?, ?, 'item_create', 'item', ?, ?, ?)""",
            (log_id, SHOP_ID, item_id,
             json.dumps(entities, ensure_ascii=False), now)
        )

    action_result = {"success": True, "action": "添加商品", "item": {"name": name, **entities}}
    reply = generate_response(user_msg, action_result)
    
    # WebSocket broadcast removed for synchronous compatibility
    
    return ChatResponse(reply=reply, intent="item_create", action="create", data=action_result)


def _handle_correction(user_msg: str, session_id: str) -> ChatResponse:
    """Handle stock correction."""
    entities = extract_entities(user_msg, "correction")
    item_name = entities.get("item_name", "")
    target = entities.get("target_stock")
    reason = entities.get("reason", "AI修正")

    if not item_name or target is None:
        reply = "老板，请告诉我要修正哪个商品以及正确的数量。"
        return ChatResponse(reply=reply, intent="correction", action="error")

    with db() as conn:
        item = conn.execute(
            "SELECT * FROM inventory_items WHERE shop_id = ? AND name LIKE ? AND is_active = 1",
            (SHOP_ID, f"%{item_name}%")
        ).fetchone()
        if not item:
            reply = f"老板，没有找到 {item_name}。"
            return ChatResponse(reply=reply, intent="correction", action="error")

        old_stock = item["current_stock"]
        conn.execute(
            "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
            (float(target), _now(), item["item_id"])
        )

        event_id = _new_id("evt")
        conn.execute(
            """INSERT INTO inventory_events
            (event_id, shop_id, item_id, event_type, quantity, unit, reason, source, created_at)
            VALUES (?, ?, ?, 'correction', ?, ?, ?, 'manual', ?)""",
            (event_id, SHOP_ID, item["item_id"],
             float(target) - old_stock, item["default_unit"], reason, _now())
        )

        log_id = _new_id("log")
        conn.execute(
            """INSERT INTO audit_logs (log_id, shop_id, event_type, entity_type, entity_id, details, created_at)
            VALUES (?, ?, 'correction', 'item', ?, ?, ?)""",
            (log_id, SHOP_ID, item["item_id"],
             json.dumps({"old": old_stock, "new": target, "reason": reason}, ensure_ascii=False),
             _now())
        )

    action_result = {
        "success": True, "action": "修正",
        "item": item["name"], "old_stock": old_stock, "new_stock": target
    }
    reply = generate_response(user_msg, action_result)
    
    # WebSocket broadcast removed for synchronous compatibility
    
    return ChatResponse(reply=reply, intent="correction", action="correction", data=action_result)


def _handle_list_items(session_id: str) -> ChatResponse:
    """Handle list all items."""
    with db() as conn:
        items = conn.execute(
            "SELECT * FROM inventory_items WHERE shop_id = ? AND is_active = 1 ORDER BY category, name",
            (SHOP_ID,)
        ).fetchall()
        results = [{
            "item_id": i["item_id"], "name": i["name"], "category": i["category"],
            "stock": i["current_stock"], "unit": i["default_unit"],
            "price": i["unit_price"], "low": i["current_stock"] <= i["low_stock_threshold"]
        } for i in items]

    action_result = {"success": True, "action": "列表", "items": results}
    reply = generate_response("列出所有库存商品", action_result)
    return ChatResponse(reply=reply, intent="list_items", action="list", data=action_result)


def _handle_low_stock(session_id: str) -> ChatResponse:
    """Handle low stock alerts."""
    with db() as conn:
        items = conn.execute(
            """SELECT * FROM inventory_items
            WHERE shop_id = ? AND is_active = 1 AND current_stock <= low_stock_threshold
            ORDER BY current_stock ASC""",
            (SHOP_ID,)
        ).fetchall()
        results = [{
            "name": i["name"], "stock": i["current_stock"], "unit": i["default_unit"],
            "threshold": i["low_stock_threshold"]
        } for i in items]

    action_result = {"success": True, "action": "低库存预警", "items": results}
    reply = generate_response("查看低库存商品", action_result)
    return ChatResponse(reply=reply, intent="low_stock", action="low_stock", data=action_result)


def _handle_general_chat(user_msg: str, session_id: str) -> ChatResponse:
    """Handle general conversation."""
    # Build history
    history = []
    with db() as conn:
        rows = conn.execute(
            """SELECT actor_type, text FROM messages
            WHERE session_id = ? ORDER BY created_at DESC LIMIT 10""",
            (session_id,)
        ).fetchall()
        for row in reversed(rows):
            role = "assistant" if row["actor_type"] == "agent" else "user"
            if row["text"]:
                history.append({"role": role, "content": row["text"]})

    reply = chat_reply(user_msg, history)

    # Save message
    with db() as conn:
        msg_id = _new_id("msg")
        conn.execute(
            "INSERT INTO messages (message_id, session_id, actor_type, actor_id, message_type, text, created_at) VALUES (?, ?, 'owner', 'boss', 'text', ?, ?)",
            (msg_id, session_id, user_msg, _now())
        )
        reply_id = _new_id("msg")
        conn.execute(
            "INSERT INTO messages (message_id, session_id, actor_type, actor_id, message_type, text, created_at) VALUES (?, ?, 'agent', 'xiaoya', 'text', ?, ?)",
            (reply_id, session_id, reply, _now())
        )

    return ChatResponse(reply=reply, intent="general_chat", action="chat")


@app.post("/api/v1/chat/stream")
async def ai_chat_stream(req: ChatRequest):
    """
    Streaming AI chat endpoint using Server-Sent Events (SSE).
    Sends tokens as they arrive from the LLM.
    """
    session_id = req.session_id or _get_default_session()
    user_msg = req.message.strip()

    # First classify intent to determine if it's a tool call or chat
    intent_result = classify_intent(user_msg)
    intent = intent_result["intent"]

    # For tool-based intents, use non-streaming (they need DB operations)
    tool_intents = {"stock_in", "stock_out", "stock_query", "item_create", "correction", "list_items", "low_stock"}

    if intent in tool_intents:
        # Execute tool and stream the response
        async def generate_tool_response():
            # Send intent first
            yield f"data: {json_lib.dumps({'type': 'intent', 'intent': intent})}\n\n"

            # Execute the tool
            if intent == "stock_in":
                result = _handle_stock_in(user_msg, session_id)
            elif intent == "stock_out":
                result = _handle_stock_out(user_msg, session_id)
            elif intent == "stock_query":
                result = _handle_stock_query(user_msg, session_id)
            elif intent == "item_create":
                result = _handle_item_create(user_msg, session_id)
            elif intent == "correction":
                result = _handle_correction(user_msg, session_id)
            elif intent == "list_items":
                result = _handle_list_items(session_id)
            elif intent == "low_stock":
                result = _handle_low_stock(session_id)
            else:
                result = ChatResponse(reply="操作完成", intent=intent, action="unknown")

            # Stream the reply character by character for effect
            reply = result.reply
            for char in reply:
                yield f"data: {json_lib.dumps({'type': 'token', 'content': char})}\n\n"
                await asyncio.sleep(0.02)  # Small delay for visual effect

            # Send final data
            yield f"data: {json_lib.dumps({'type': 'done', 'intent': result.intent, 'action': result.action, 'data': result.data})}\n\n"

        return StreamingResponse(
            generate_tool_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # For general chat, stream from LLM
    async def generate_stream():
        # Send intent
        yield f"data: {json_lib.dumps({'type': 'intent', 'intent': 'general_chat'})}\n\n"

        # Get history for context
        history = []
        with db() as conn:
            rows = conn.execute(
                """SELECT actor_type, text FROM messages
                WHERE session_id = ? ORDER BY created_at DESC LIMIT 10""",
                (session_id,)
            ).fetchall()
            for row in reversed(rows):
                role = "assistant" if row["actor_type"] == "agent" else "user"
                if row["text"]:
                    history.append({"role": role, "content": row["text"]})

        # Stream tokens from LLM
        full_reply = ""
        import queue
        import threading

        token_queue = queue.Queue()
        stream_done = threading.Event()

        def stream_worker():
            try:
                for token in chat_stream(user_msg, history):
                    token_queue.put(token)
            except Exception as e:
                print(f"[Stream Worker Error] {e}")
                token_queue.put(_chat_fallback_reply(user_msg))
            finally:
                stream_done.set()

        thread = threading.Thread(target=stream_worker)
        thread.start()

        # Yield tokens as they arrive
        while not stream_done.is_set() or not token_queue.empty():
            try:
                token = token_queue.get(timeout=0.1)
                full_reply += token
                yield f"data: {json_lib.dumps({'type': 'token', 'content': token})}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.05)

        thread.join(timeout=5)

        # Save messages to DB
        with db() as conn:
            msg_id = _new_id("msg")
            conn.execute(
                "INSERT INTO messages (message_id, session_id, actor_type, actor_id, message_type, text, created_at) VALUES (?, ?, 'owner', 'boss', 'text', ?, ?)",
                (msg_id, session_id, user_msg, _now())
            )
            reply_id = _new_id("msg")
            conn.execute(
                "INSERT INTO messages (message_id, session_id, actor_type, actor_id, message_type, text, created_at) VALUES (?, ?, 'agent', 'xiaoya', 'text', ?, ?)",
                (reply_id, session_id, full_reply, _now())
            )

        # Send done
        yield f"data: {json_lib.dumps({'type': 'done', 'intent': 'general_chat', 'action': 'chat'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ── REST API: Inventory Items ──────────────────────────────────────────

@app.get("/api/v1/items")
def list_items(
    category: str | None = None,
    low_stock: bool = False,
    search: str | None = None,
):
    with db() as conn:
        query = "SELECT * FROM inventory_items WHERE shop_id = ? AND is_active = 1"
        params = [SHOP_ID]
        if category:
            query += " AND category = ?"
            params.append(category)
        if low_stock:
            query += " AND current_stock <= low_stock_threshold"
        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")
        query += " ORDER BY category, name"
        rows = conn.execute(query, params).fetchall()
        return {
            "data": [{
                "item_id": r["item_id"], "name": r["name"], "category": r["category"],
                "default_unit": r["default_unit"], "current_stock": r["current_stock"],
                "unit_price": r["unit_price"], "low_stock_threshold": r["low_stock_threshold"],
                "is_low_stock": r["current_stock"] <= r["low_stock_threshold"],
                "created_at": r["created_at"], "updated_at": r["updated_at"],
            } for r in rows]
        }


@app.post("/api/v1/items")
def create_item(item: ItemCreate):
    with db() as conn:
        existing = conn.execute(
            "SELECT item_id FROM inventory_items WHERE shop_id = ? AND name = ? AND is_active = 1",
            (SHOP_ID, item.name)
        ).fetchone()
        if existing:
            raise HTTPException(400, f"商品 '{item.name}' 已存在")

        item_id = _new_id("item")
        now = _now()
        conn.execute(
            """INSERT INTO inventory_items
            (item_id, shop_id, name, category, default_unit, current_stock, unit_price, low_stock_threshold, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, SHOP_ID, item.name, item.category, item.default_unit,
             item.current_stock, item.unit_price, item.low_stock_threshold, now, now)
        )
        return {"data": {"item_id": item_id, "name": item.name}}


@app.get("/api/v1/items/{item_id}")
def get_item(item_id: str):
    with db() as conn:
        r = conn.execute(
            "SELECT * FROM inventory_items WHERE item_id = ? AND shop_id = ?",
            (item_id, SHOP_ID)
        ).fetchone()
        if not r:
            raise HTTPException(404, "商品不存在")
        return {
            "data": {
                "item_id": r["item_id"], "name": r["name"], "category": r["category"],
                "default_unit": r["default_unit"], "current_stock": r["current_stock"],
                "unit_price": r["unit_price"], "low_stock_threshold": r["low_stock_threshold"],
            }
        }


# ── REST API: Stock Operations ─────────────────────────────────────────

@app.post("/api/v1/stock-in")
def stock_in(req: StockInRequest):
    with db() as conn:
        item = conn.execute(
            "SELECT * FROM inventory_items WHERE item_id = ? AND shop_id = ? AND is_active = 1",
            (req.item_id, SHOP_ID)
        ).fetchone()
        if not item:
            raise HTTPException(404, "商品不存在")

        new_stock = item["current_stock"] + req.quantity
        conn.execute(
            "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
            (new_stock, _now(), req.item_id)
        )

        event_id = _new_id("evt")
        conn.execute(
            """INSERT INTO inventory_events
            (event_id, shop_id, item_id, event_type, quantity, unit, unit_price, reason, source, created_at)
            VALUES (?, ?, ?, 'stock_in', ?, ?, ?, ?, 'api', ?)""",
            (event_id, SHOP_ID, req.item_id, req.quantity, item["default_unit"],
             req.unit_price or item["unit_price"], req.reason or "手动入库", _now())
        )
        return {"data": {"item_id": req.item_id, "name": item["name"],
                        "old_stock": item["current_stock"], "new_stock": new_stock}}


@app.post("/api/v1/stock-out")
def stock_out(req: StockOutRequest):
    with db() as conn:
        item = conn.execute(
            "SELECT * FROM inventory_items WHERE item_id = ? AND shop_id = ? AND is_active = 1",
            (req.item_id, SHOP_ID)
        ).fetchone()
        if not item:
            raise HTTPException(404, "商品不存在")
        if item["current_stock"] < req.quantity:
            raise HTTPException(400, f"库存不足（当前{item['current_stock']}）")

        new_stock = item["current_stock"] - req.quantity
        conn.execute(
            "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
            (new_stock, _now(), req.item_id)
        )

        event_id = _new_id("evt")
        conn.execute(
            """INSERT INTO inventory_events
            (event_id, shop_id, item_id, event_type, quantity, unit, reason, source, created_at)
            VALUES (?, ?, ?, 'stock_out', ?, ?, ?, 'api', ?)""",
            (event_id, SHOP_ID, req.item_id, req.quantity, item["default_unit"],
             req.reason or "手动出库", _now())
        )
        return {"data": {"item_id": req.item_id, "name": item["name"],
                        "old_stock": item["current_stock"], "new_stock": new_stock}}


@app.post("/api/v1/correction")
def correct_stock(req: CorrectionRequest):
    with db() as conn:
        item = conn.execute(
            "SELECT * FROM inventory_items WHERE item_id = ? AND shop_id = ? AND is_active = 1",
            (req.item_id, SHOP_ID)
        ).fetchone()
        if not item:
            raise HTTPException(404, "商品不存在")

        old_stock = item["current_stock"]
        conn.execute(
            "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
            (req.target_stock, _now(), req.item_id)
        )

        event_id = _new_id("evt")
        conn.execute(
            """INSERT INTO inventory_events
            (event_id, shop_id, item_id, event_type, quantity, unit, reason, source, created_at)
            VALUES (?, ?, ?, 'correction', ?, ?, ?, 'manual', ?)""",
            (event_id, SHOP_ID, req.item_id, req.target_stock - old_stock,
             item["default_unit"], req.reason, _now())
        )
        return {"data": {"item_id": req.item_id, "name": item["name"],
                        "old_stock": old_stock, "new_stock": req.target_stock}}


# ── REST API: Events & Audit ───────────────────────────────────────────

@app.get("/api/v1/events")
def list_events(item_id: str | None = None, limit: int = Query(default=50, le=200)):
    with db() as conn:
        query = """SELECT e.*, i.name as item_name FROM inventory_events e
                   JOIN inventory_items i ON e.item_id = i.item_id
                   WHERE e.shop_id = ?"""
        params = [SHOP_ID]
        if item_id:
            query += " AND e.item_id = ?"
            params.append(item_id)
        query += " ORDER BY e.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return {
            "data": [{
                "event_id": r["event_id"], "item_id": r["item_id"],
                "item_name": r["item_name"], "event_type": r["event_type"],
                "quantity": r["quantity"], "unit": r["unit"],
                "unit_price": r["unit_price"], "reason": r["reason"],
                "source": r["source"], "created_at": r["created_at"],
            } for r in rows]
        }


@app.get("/api/v1/audit-logs")
def list_audit_logs(limit: int = Query(default=50, le=200)):
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM audit_logs WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?""",
            (SHOP_ID, limit)
        ).fetchall()
        return {
            "data": [{
                "log_id": r["log_id"], "event_type": r["event_type"],
                "entity_type": r["entity_type"], "entity_id": r["entity_id"],
                "details": json.loads(r["details"]) if r["details"] else None,
                "created_at": r["created_at"],
            } for r in rows]
        }


# ── REST API: Messages & Sessions ──────────────────────────────────────

@app.get("/api/v1/sessions/{session_id}/messages")
def get_messages(session_id: str, limit: int = Query(default=50, le=200)):
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?""",
            (session_id, limit)
        ).fetchall()
        return {
            "data": [{
                "message_id": r["message_id"], "actor_type": r["actor_type"],
                "actor_id": r["actor_id"], "message_type": r["message_type"],
                "text": r["text"], "created_at": r["created_at"],
            } for r in reversed(rows)]
        }


# ── REST API: Dashboard ───────────────────────────────────────────────

@app.get("/api/v1/dashboard")
def dashboard():
    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as c FROM inventory_items WHERE shop_id = ? AND is_active = 1",
            (SHOP_ID,)
        ).fetchone()["c"]

        low = conn.execute(
            """SELECT COUNT(*) as c FROM inventory_items
            WHERE shop_id = ? AND is_active = 1 AND current_stock <= low_stock_threshold""",
            (SHOP_ID,)
        ).fetchone()["c"]

        total_value = conn.execute(
            "SELECT COALESCE(SUM(current_stock * unit_price), 0) as v FROM inventory_items WHERE shop_id = ? AND is_active = 1",
            (SHOP_ID,)
        ).fetchone()["v"]

        today_events = conn.execute(
            """SELECT COUNT(*) as c FROM inventory_events
            WHERE shop_id = ? AND created_at >= date('now', 'start of day')""",
            (SHOP_ID,)
        ).fetchone()["c"]

        categories = conn.execute(
            "SELECT DISTINCT category FROM inventory_items WHERE shop_id = ? AND is_active = 1 AND category != ''",
            (SHOP_ID,)
        ).fetchall()

        return {
            "data": {
                "total_items": total,
                "low_stock_items": low,
                "total_value": round(total_value, 2),
                "today_events": today_events,
                "categories": [c["category"] for c in categories],
            }
        }


@app.get("/api/v1/revenue")
def get_revenue():
    """获取营业额数据 - 按日期统计销售额"""
    with db() as conn:
        # 今日销售额 (出库事件)
        today_revenue = conn.execute(
            """SELECT COALESCE(SUM(quantity * unit_price), 0) as revenue
            FROM inventory_events
            WHERE shop_id = ? AND event_type = 'stock_out' AND created_at >= date('now', 'start of day')""",
            (SHOP_ID,)
        ).fetchone()["revenue"]

        # 本周销售额
        week_revenue = conn.execute(
            """SELECT COALESCE(SUM(quantity * unit_price), 0) as revenue
            FROM inventory_events
            WHERE shop_id = ? AND event_type = 'stock_out' AND created_at >= date('now', 'weekday 0', '-7 days')""",
            (SHOP_ID,)
        ).fetchone()["revenue"]

        # 本月销售额
        month_revenue = conn.execute(
            """SELECT COALESCE(SUM(quantity * unit_price), 0) as revenue
            FROM inventory_events
            WHERE shop_id = ? AND event_type = 'stock_out' AND created_at >= date('now', 'start of month')""",
            (SHOP_ID,)
        ).fetchone()["revenue"]

        # 最近7天每日销售额
        daily_revenue = conn.execute(
            """SELECT date(created_at) as date, SUM(quantity * unit_price) as revenue
            FROM inventory_events
            WHERE shop_id = ? AND event_type = 'stock_out' AND created_at >= date('now', '-7 days')
            GROUP BY date(created_at)
            ORDER BY date(created_at)""",
            (SHOP_ID,)
        ).fetchall()

        # 热销商品 Top5
        top_items = conn.execute(
            """SELECT i.name, SUM(e.quantity) as total_sold, SUM(e.quantity * e.unit_price) as total_revenue
            FROM inventory_events e
            JOIN inventory_items i ON e.item_id = i.item_id
            WHERE e.shop_id = ? AND e.event_type = 'stock_out' AND e.created_at >= date('now', '-30 days')
            GROUP BY e.item_id
            ORDER BY total_revenue DESC
            LIMIT 5""",
            (SHOP_ID,)
        ).fetchall()

        return {
            "data": {
                "today_revenue": round(today_revenue, 2),
                "week_revenue": round(week_revenue, 2),
                "month_revenue": round(month_revenue, 2),
                "daily_revenue": [{"date": r["date"], "revenue": round(r["revenue"], 2)} for r in daily_revenue],
                "top_items": [{"name": r["name"], "total_sold": r["total_sold"], "total_revenue": round(r["total_revenue"], 2)} for r in top_items],
            }
        }


@app.get("/api/v1/transactions")
def get_transactions(limit: int = Query(20, ge=1, le=100)):
    """获取流水记录 - 最近的库存变动"""
    with db() as conn:
        events = conn.execute(
            """SELECT e.*, i.name as item_name
            FROM inventory_events e
            JOIN inventory_items i ON e.item_id = i.item_id
            WHERE e.shop_id = ?
            ORDER BY e.created_at DESC
            LIMIT ?""",
            (SHOP_ID, limit)
        ).fetchall()

        # 统计信息
        stats = conn.execute(
            """SELECT
                COUNT(*) as total_events,
                SUM(CASE WHEN event_type = 'stock_in' THEN quantity ELSE 0 END) as total_in,
                SUM(CASE WHEN event_type = 'stock_out' THEN quantity ELSE 0 END) as total_out,
                SUM(CASE WHEN event_type = 'stock_in' THEN quantity * unit_price ELSE 0 END) as total_in_value,
                SUM(CASE WHEN event_type = 'stock_out' THEN quantity * unit_price ELSE 0 END) as total_out_value
            FROM inventory_events
            WHERE shop_id = ? AND created_at >= date('now', 'start of day')""",
            (SHOP_ID,)
        ).fetchone()

        return {
            "data": {
                "transactions": [{
                    "event_id": r["event_id"],
                    "item_name": r["item_name"],
                    "event_type": r["event_type"],
                    "quantity": r["quantity"],
                    "unit": r["unit"],
                    "unit_price": r["unit_price"],
                    "reason": r["reason"],
                    "created_at": r["created_at"],
                } for r in events],
                "today_stats": {
                    "total_events": stats["total_events"],
                    "total_in": stats["total_in"],
                    "total_out": stats["total_out"],
                    "total_in_value": round(stats["total_in_value"] or 0, 2),
                    "total_out_value": round(stats["total_out_value"] or 0, 2),
                }
            }
        }


@app.get("/api/v1/recommendations")
def get_recommendations():
    """获取AI推荐和分析"""
    with db() as conn:
        # 低库存商品
        low_stock = conn.execute(
            """SELECT name, current_stock, low_stock_threshold, unit_price
            FROM inventory_items
            WHERE shop_id = ? AND is_active = 1 AND current_stock <= low_stock_threshold
            ORDER BY (current_stock / low_stock_threshold) ASC
            LIMIT 5""",
            (SHOP_ID,)
        ).fetchall()

        # 滞销商品 (30天无销售)
        slow_moving = conn.execute(
            """SELECT i.name, i.current_stock, i.unit_price,
                    COALESCE(MAX(e.created_at), '从未销售') as last_sold
            FROM inventory_items i
            LEFT JOIN inventory_events e ON i.item_id = e.item_id AND e.event_type = 'stock_out'
            WHERE i.shop_id = ? AND i.is_active = 1
            GROUP BY i.item_id
            HAVING last_sold < date('now', '-30 days') OR last_sold = '从未销售'
            ORDER BY i.current_stock * i.unit_price DESC
            LIMIT 5""",
            (SHOP_ID,)
        ).fetchall()

        # 库存周转分析
        turnover = conn.execute(
            """SELECT i.name, i.current_stock,
                    COALESCE(SUM(CASE WHEN e.event_type = 'stock_out' THEN e.quantity ELSE 0 END), 0) as sold_30d
            FROM inventory_items i
            LEFT JOIN inventory_events e ON i.item_id = e.item_id AND e.created_at >= date('now', '-30 days')
            WHERE i.shop_id = ? AND i.is_active = 1
            GROUP BY i.item_id
            HAVING i.current_stock > 0
            ORDER BY (sold_30d / i.current_stock) DESC
            LIMIT 5""",
            (SHOP_ID,)
        ).fetchall()

        # 生成建议
        recommendations = []

        if low_stock:
            recommendations.append({
                "type": "urgent",
                "title": "紧急补货提醒",
                "items": [{"name": r["name"], "stock": r["current_stock"], "threshold": r["low_stock_threshold"]} for r in low_stock],
                "action": "立即联系供应商补货"
            })

        if slow_moving:
            recommendations.append({
                "type": "warning",
                "title": "滞销商品预警",
                "items": [{"name": r["name"], "stock": r["current_stock"], "last_sold": r["last_sold"]} for r in slow_moving],
                "action": "考虑促销或调整采购策略"
            })

        if turnover:
            recommendations.append({
                "type": "info",
                "title": "库存周转分析",
                "items": [{"name": r["name"], "stock": r["current_stock"], "sold_30d": r["sold_30d"]} for r in turnover],
                "action": "周转快的商品可适当增加库存"
            })

        # 销售趋势分析
        sales_trend = conn.execute(
            """SELECT date(created_at) as date, SUM(quantity * unit_price) as revenue
            FROM inventory_events
            WHERE shop_id = ? AND event_type = 'stock_out' AND created_at >= date('now', '-7 days')
            GROUP BY date(created_at)
            ORDER BY date(created_at)""",
            (SHOP_ID,)
        ).fetchall()

        if len(sales_trend) >= 2:
            revenues = [r["revenue"] for r in sales_trend]
            avg_revenue = sum(revenues) / len(revenues)
            latest = revenues[-1]
            if latest < avg_revenue * 0.8:
                recommendations.append({
                    "type": "warning",
                    "title": "销售下滑预警",
                    "message": f"昨日销售额 {latest:.0f} 元，低于7日均值 {avg_revenue:.0f} 元",
                    "action": "检查是否有异常或考虑促销活动"
                })
            elif latest > avg_revenue * 1.2:
                recommendations.append({
                    "type": "success",
                    "title": "销售增长良好",
                    "message": f"昨日销售额 {latest:.0f} 元，高于7日均值 {avg_revenue:.0f} 元",
                    "action": "保持当前经营策略"
                })

        return {"data": {"recommendations": recommendations}}


# ── REST API: Confirmations ────────────────────────────────────────────

@app.get("/api/v1/confirmations")
def list_confirmations(status: str | None = None):
    with db() as conn:
        query = """SELECT c.*, t.transcript, t.task_type FROM confirmations c
                   JOIN task_runs t ON c.task_run_id = t.task_run_id
                   WHERE 1=1"""
        params = []
        if status:
            query += " AND c.status = ?"
            params.append(status)
        query += " ORDER BY c.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return {
            "data": [{
                "confirmation_id": r["confirmation_id"],
                "task_run_id": r["task_run_id"],
                "confirmation_type": r["confirmation_type"],
                "status": r["status"],
                "fields": json.loads(r["fields"]) if r["fields"] else None,
                "transcript": r["transcript"],
                "task_type": r["task_type"],
                "created_at": r["created_at"],
            } for r in rows]
        }


@app.post("/api/v1/confirmations/{confirmation_id}/approve")
def approve_confirmation(confirmation_id: str, req: ApproveRequest):
    with db() as conn:
        conf = conn.execute(
            "SELECT * FROM confirmations WHERE confirmation_id = ? AND status = 'pending'",
            (confirmation_id,)
        ).fetchone()
        if not conf:
            raise HTTPException(404, "确认记录不存在或已处理")

        if not req.approved:
            conn.execute(
                "UPDATE confirmations SET status = 'rejected', resolved_at = ? WHERE confirmation_id = ?",
                (_now(), confirmation_id)
            )
            conn.execute(
                "UPDATE task_runs SET status = 'failed', error_code = 'rejected', updated_at = ? WHERE task_run_id = ?",
                (_now(), conf["task_run_id"])
            )
            return {"data": {"confirmation_id": confirmation_id, "status": "rejected"}}

        # Approve: apply the changes
        fields = json.loads(conf["fields"]) if conf["fields"] else {}
        draft_fields = fields.get("draft_fields", {})

        item_name = req.item_name or draft_fields.get("item_name", "")
        quantity = req.quantity if req.quantity is not None else draft_fields.get("quantity", 0)
        unit = req.unit or draft_fields.get("unit", "件")
        unit_price = req.unit_price if req.unit_price is not None else draft_fields.get("price", 0)

        if item_name and quantity:
            # Find or create item
            item = conn.execute(
                "SELECT * FROM inventory_items WHERE shop_id = ? AND name LIKE ? AND is_active = 1",
                (SHOP_ID, f"%{item_name}%")
            ).fetchone()

            if item:
                new_stock = item["current_stock"] + float(quantity)
                conn.execute(
                    "UPDATE inventory_items SET current_stock = ?, updated_at = ? WHERE item_id = ?",
                    (new_stock, _now(), item["item_id"])
                )
                event_id = _new_id("evt")
                conn.execute(
                    """INSERT INTO inventory_events
                    (event_id, shop_id, item_id, event_type, quantity, unit, unit_price, reason, source, created_at)
                    VALUES (?, ?, ?, 'stock_in', ?, ?, ?, '确认入库', 'confirmation', ?)""",
                    (event_id, SHOP_ID, item["item_id"], float(quantity), unit, float(unit_price), _now())
                )
            else:
                item_id = _new_id("item")
                now = _now()
                conn.execute(
                    """INSERT INTO inventory_items
                    (item_id, shop_id, name, default_unit, current_stock, unit_price, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item_id, SHOP_ID, item_name, unit, float(quantity), float(unit_price), now, now)
                )
                event_id = _new_id("evt")
                conn.execute(
                    """INSERT INTO inventory_events
                    (event_id, shop_id, item_id, event_type, quantity, unit, unit_price, reason, source, created_at)
                    VALUES (?, ?, ?, 'stock_in', ?, ?, ?, '确认入库', 'confirmation', ?)""",
                    (event_id, SHOP_ID, item_id, float(quantity), unit, float(unit_price), now)
                )

        conn.execute(
            "UPDATE confirmations SET status = 'approved', resolved_at = ? WHERE confirmation_id = ?",
            (_now(), confirmation_id)
        )
        conn.execute(
            "UPDATE task_runs SET status = 'completed', updated_at = ? WHERE task_run_id = ?",
            (_now(), conf["task_run_id"])
        )
        return {"data": {"confirmation_id": confirmation_id, "status": "approved"}}


# ── H5 Static Assets ──────────────────────────────────────────────────
H5_DIR = os.path.join(BASE_DIR, "static", "h5")
if os.path.isdir(H5_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(H5_DIR, "assets")), name="h5-assets")


def _read_h5_index():
    index_path = os.path.join(H5_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# ── HTML Pages (React H5 SPA) ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return _read_h5_index()


@app.get("/login", response_class=HTMLResponse)
@app.get("/products", response_class=HTMLResponse)
@app.get("/chat", response_class=HTMLResponse)
@app.get("/profile", response_class=HTMLResponse)
def spa_routes():
    """SPA fallback - all app routes return index.html"""
    return _read_h5_index()


# Keep legacy demo accessible at /demo
@app.get("/demo", response_class=HTMLResponse)
def legacy_demo():
    with open(os.path.join(BASE_DIR, "templates", "demo.html"), "r", encoding="utf-8") as f:
        return f.read()
