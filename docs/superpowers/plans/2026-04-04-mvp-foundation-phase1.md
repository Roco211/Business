# MVP Foundation Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前仓库从“文档蓝图 + 展示站”推进到“可施工的 MVP 工程骨架”，落地移动端、后端、基础设施与最小验证入口。

**Architecture:** 先以最小可运行骨架为目标，分别建立 `apps/mobile`、`backend`、`infra/docker` 三条主线；后端用 FastAPI + Pydantic 固化第一批合同，移动端用 Expo + React Navigation 建立三主页面壳层，基础设施用 Docker Compose 显式化本地依赖。业务主链路、真实 provider、数据库迁移与实时事件都留到后续阶段。

**Tech Stack:** Python, FastAPI, Pydantic, pytest, Celery, Docker Compose, Expo, React Native, TypeScript, React Navigation, Jest, React Native Testing Library

---

### Task 1: 仓库约定与基础设施模板

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `infra/docker/docker-compose.yml`
- Create: `infra/docker/README.md`

- [ ] **Step 1: 更新 `.gitignore`，让 worktree 和后续工程产物不会污染主仓库**

```gitignore
__pycache__/
*.pyc
showcase_app/.deps/
showcase_app/__pycache__/
.worktrees/
apps/mobile/node_modules/
apps/mobile/.expo/
apps/mobile/dist/
backend/.pytest_cache/
backend/.venv/
```

- [ ] **Step 2: 写入 `.env.example`，固定后续服务命名与最小环境变量边界**

```dotenv
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8001

MYSQL_DATABASE=ai_store_manager
MYSQL_USER=aism
MYSQL_PASSWORD=aism_password
MYSQL_ROOT_PASSWORD=root_password
MYSQL_PORT=3306

REDIS_PORT=6379

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

DEFAULT_SHOP_ID=shop_default
DEFAULT_OWNER_ACTOR_ID=owner_default
DEFAULT_SESSION_ID=sess_default
```

- [ ] **Step 3: 写入 `infra/docker/docker-compose.yml`，先把本地依赖和骨架服务显式化**

```yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    ports:
      - "${MYSQL_PORT}:3306"

  redis:
    image: redis:7
    ports:
      - "${REDIS_PORT}:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":${MINIO_CONSOLE_PORT}"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports:
      - "${MINIO_API_PORT}:9000"
      - "${MINIO_CONSOLE_PORT}:9001"

  api:
    build:
      context: ../..
      dockerfile: backend/Dockerfile
    env_file:
      - ../../.env.example
    command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8001
    ports:
      - "8001:8001"
    depends_on:
      - mysql
      - redis
      - minio

  worker:
    build:
      context: ../..
      dockerfile: backend/Dockerfile
    env_file:
      - ../../.env.example
    command: celery -A app.workers.celery_app.celery_app worker --loglevel=info
    depends_on:
      - redis
```

- [ ] **Step 4: 写入 `infra/docker/README.md`，说明这个目录在 Phase 1 的职责**

```md
# Infra Docker

这个目录只负责 Phase 1 的本地基础设施骨架：

- MySQL
- Redis
- MinIO
- API 服务
- Worker 服务

当前阶段的目标是先固定服务边界和环境变量，不追求生产级部署。
```

- [ ] **Step 5: 验证 Docker 配置可被解析**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- 命令退出码为 `0`
- 输出包含 `mysql`、`redis`、`minio`、`api`、`worker`

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example infra/docker/docker-compose.yml infra/docker/README.md
git commit -m "chore: add phase 1 infra templates"
```

### Task 2: 后端应用骨架与健康检查

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/router.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/contracts/__init__.py`
- Create: `backend/app/contracts/system.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: 先写健康检查失败测试**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_payload() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试，确认它因后端骨架缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_health.py -q
```

Expected:

- `ModuleNotFoundError` 或导入失败
- 不能出现误通过

- [ ] **Step 3: 写最小后端实现让测试通过**

`backend/requirements.txt`

```txt
fastapi==0.115.12
uvicorn==0.34.0
pydantic==2.11.3
celery==5.4.0
pytest==8.3.5
httpx==0.28.1
```

`backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend /app
```

`backend/app/contracts/system.py`

```python
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
```

`backend/app/__init__.py`

```python
"""Backend application package."""
```

`backend/app/core/__init__.py`

```python
"""Core backend utilities."""
```

`backend/app/api/__init__.py`

```python
"""API package."""
```

`backend/app/api/routes/__init__.py`

```python
"""HTTP route modules."""
```

`backend/app/contracts/__init__.py`

```python
"""Response and request contracts."""
```

`backend/app/api/routes/health.py`

```python
from fastapi import APIRouter

from app.contracts.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
```

`backend/app/api/router.py`

```python
from fastapi import APIRouter

from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
```

`backend/app/main.py`

```python
from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
    )
    app.include_router(api_router)
    return app
```

`backend/tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
```

- [ ] **Step 4: 重新运行健康检查测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_health.py -q
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile backend/app backend/tests
git commit -m "feat: add backend healthcheck skeleton"
```

### Task 3: Mock Auth 与 Session Bootstrap 最小合同

**Files:**
- Create: `backend/app/contracts/common.py`
- Create: `backend/app/contracts/auth.py`
- Create: `backend/app/contracts/session.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/api/routes/sessions.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/test_sessions.py`

- [ ] **Step 1: 先写路由测试，定义 mock-login 与 session bootstrap 的最小外部行为**

`backend/tests/test_auth.py`

```python
def test_mock_login_returns_default_owner_context(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={"shop_id": "shop_default"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"] == "mock_owner_token"
    assert payload["owner_actor_id"] == "owner_default"
    assert payload["shop_id"] == "shop_default"
```

`backend/tests/test_sessions.py`

```python
def test_session_bootstrap_returns_default_workgroup(client) -> None:
    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session_id"] == "sess_default"
    assert payload["session_type"] == "workgroup"
    assert payload["participants"] == ["xiaoya", "laoli"]
```

- [ ] **Step 2: 运行测试，确认它们因路由缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_auth.py backend/tests/test_sessions.py -q
```

Expected:

- `404` 相关失败

- [ ] **Step 3: 写最小合同、配置和路由实现**

`backend/app/core/config.py`

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    default_shop_id: str = os.getenv("DEFAULT_SHOP_ID", "shop_default")
    default_owner_actor_id: str = os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default")
    default_session_id: str = os.getenv("DEFAULT_SESSION_ID", "sess_default")


def get_settings() -> Settings:
    return Settings()
```

`backend/app/contracts/common.py`

```python
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    data: T
```

`backend/app/contracts/auth.py`

```python
from pydantic import BaseModel


class MockLoginRequest(BaseModel):
    shop_id: str


class MockLoginData(BaseModel):
    access_token: str
    token_type: str
    owner_actor_id: str
    shop_id: str
    shop_name: str
```

`backend/app/contracts/session.py`

```python
from pydantic import BaseModel


class SessionBootstrapData(BaseModel):
    session_id: str
    session_type: str
    title: str
    participants: list[str]
```

`backend/app/api/routes/auth.py`

```python
from fastapi import APIRouter, Depends

from app.contracts.auth import MockLoginData, MockLoginRequest
from app.contracts.common import DataEnvelope
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/mock-login", response_model=DataEnvelope[MockLoginData])
def mock_login(
    payload: MockLoginRequest,
    settings: Settings = Depends(get_settings),
) -> DataEnvelope[MockLoginData]:
    return DataEnvelope(
        data=MockLoginData(
            access_token="mock_owner_token",
            token_type="Bearer",
            owner_actor_id=settings.default_owner_actor_id,
            shop_id=payload.shop_id or settings.default_shop_id,
            shop_name="演示店铺",
        )
    )
```

`backend/app/api/routes/sessions.py`

```python
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.contracts.common import DataEnvelope
from app.contracts.session import SessionBootstrapData
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/bootstrap", response_model=DataEnvelope[SessionBootstrapData])
def bootstrap_session(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> DataEnvelope[SessionBootstrapData]:
    if authorization != "Bearer mock_owner_token":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=settings.default_session_id,
            session_type="workgroup",
            title="数字员工工作群",
            participants=["xiaoya", "laoli"],
        )
    )
```

`backend/app/api/router.py`

```python
from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
```

- [ ] **Step 4: 重新运行路由测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_auth.py backend/tests/test_sessions.py -q
```

Expected:

- `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/contracts backend/app/api/routes backend/app/api/router.py backend/tests/test_auth.py backend/tests/test_sessions.py
git commit -m "feat: add mock auth and session bootstrap routes"
```

### Task 4: Worker、Runtime 与 Fixture 骨架

**Files:**
- Create: `backend/app/runtime/__init__.py`
- Create: `backend/app/runtime/README.md`
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/celery_app.py`
- Create: `backend/tests/test_worker_bootstrap.py`
- Create: `backend/tests/fixtures/providers/asr/README.md`
- Create: `backend/tests/fixtures/providers/asr/success.json`
- Create: `backend/tests/fixtures/providers/asr/low_confidence.json`
- Create: `backend/tests/fixtures/providers/asr/failure.json`
- Create: `backend/tests/fixtures/providers/ocr/README.md`
- Create: `backend/tests/fixtures/providers/ocr/success.json`
- Create: `backend/tests/fixtures/providers/ocr/low_confidence.json`
- Create: `backend/tests/fixtures/providers/ocr/failure.json`
- Create: `backend/tests/fixtures/providers/vision/README.md`
- Create: `backend/tests/fixtures/providers/vision/success.json`
- Create: `backend/tests/fixtures/providers/vision/low_confidence.json`
- Create: `backend/tests/fixtures/providers/vision/failure.json`

- [ ] **Step 1: 先写 worker bootstrap 测试，固定 Celery app 命名**

```python
from app.workers.celery_app import celery_app


def test_celery_app_uses_expected_name() -> None:
    assert celery_app.main == "ai_store_manager"
```

- [ ] **Step 2: 运行测试，确认它因 worker 骨架缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_worker_bootstrap.py -q
```

Expected:

- 导入失败

- [ ] **Step 3: 写最小 worker / runtime / fixture 骨架**

`backend/app/workers/celery_app.py`

```python
from celery import Celery

celery_app = Celery("ai_store_manager")
```

`backend/app/runtime/__init__.py`

```python
"""Runtime package boundary for future orchestrator code."""
```

`backend/app/workers/__init__.py`

```python
"""Worker package boundary."""
```

`backend/app/runtime/README.md`

```md
# Runtime Skeleton

Phase 1 只建立 runtime 包边界，不实现完整 orchestrator。

后续阶段将在这里继续落地：

- Router
- PolicyGuard
- ToolRunner
- Summarizer
```

`backend/tests/fixtures/providers/asr/README.md`

```md
# ASR Fixtures

这个目录固定三类最小样例：

- `success.json`
- `low_confidence.json`
- `failure.json`
```

`backend/tests/fixtures/providers/asr/success.json`

```json
{
  "text": "今天进来三箱可乐",
  "confidence": 0.96,
  "language": "zh-CN"
}
```

`backend/tests/fixtures/providers/asr/low_confidence.json`

```json
{
  "text": "今天进来三箱可乐",
  "confidence": 0.62,
  "language": "zh-CN"
}
```

`backend/tests/fixtures/providers/asr/failure.json`

```json
{
  "error_code": "asr_failed",
  "message": "Mock ASR failed"
}
```

`backend/tests/fixtures/providers/ocr/success.json`

```json
{
  "fields": {
    "items": [
      { "name": "可乐", "quantity": 3, "unit": "箱", "price": 41.0 }
    ]
  },
  "low_confidence_fields": []
}
```

`backend/tests/fixtures/providers/ocr/low_confidence.json`

```json
{
  "fields": {
    "items": [
      { "name": "可乐", "quantity": 3, "unit": "箱", "price": null }
    ]
  },
  "low_confidence_fields": ["items[0].price"]
}
```

`backend/tests/fixtures/providers/ocr/failure.json`

```json
{
  "error_code": "ocr_failed",
  "message": "Mock OCR failed"
}
```

`backend/tests/fixtures/providers/ocr/README.md`

```md
# OCR Fixtures

这个目录固定三类最小样例：

- `success.json`
- `low_confidence.json`
- `failure.json`
```

`backend/tests/fixtures/providers/vision/success.json`

```json
{
  "candidates": [
    { "name": "红牛 250ml", "confidence": 0.93 }
  ],
  "top_confidence": 0.93
}
```

`backend/tests/fixtures/providers/vision/low_confidence.json`

```json
{
  "candidates": [
    { "name": "红牛 250ml", "confidence": 0.61 }
  ],
  "top_confidence": 0.61
}
```

`backend/tests/fixtures/providers/vision/failure.json`

```json
{
  "error_code": "recognition_failed",
  "message": "Mock vision failed"
}
```

`backend/tests/fixtures/providers/vision/README.md`

```md
# Vision Fixtures

这个目录固定三类最小样例：

- `success.json`
- `low_confidence.json`
- `failure.json`
```

- [ ] **Step 4: 重新运行 worker bootstrap 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_worker_bootstrap.py -q
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime backend/app/workers backend/tests/test_worker_bootstrap.py backend/tests/fixtures/providers
git commit -m "feat: add runtime and worker scaffolds"
```

### Task 5: 移动端 Expo 壳层与三主页面

**Files:**
- Create: `apps/mobile/package.json`
- Create: `apps/mobile/app.json`
- Create: `apps/mobile/babel.config.js`
- Create: `apps/mobile/tsconfig.json`
- Create: `apps/mobile/jest.config.js`
- Create: `apps/mobile/App.tsx`
- Create: `apps/mobile/src/app/navigation/RootNavigator.tsx`
- Create: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Create: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Create: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- Create: `apps/mobile/__tests__/App.test.tsx`

- [ ] **Step 1: 先写移动端渲染测试，固定三主页面心智**

```tsx
import { render, screen } from "@testing-library/react-native";

import App from "../App";

test("renders the three primary screen labels", () => {
  render(<App />);

  expect(screen.getByText("工作台")).toBeTruthy();
  expect(screen.getByText("工作群")).toBeTruthy();
  expect(screen.getByText("账本")).toBeTruthy();
});
```

- [ ] **Step 2: 安装依赖并运行测试，确认它因移动端骨架缺失而失败**

Run:

```powershell
npm --prefix apps/mobile install
npm --prefix apps/mobile test -- --runInBand
```

Expected:

- 初次运行前因为文件缺失或脚本缺失而失败

- [ ] **Step 3: 写最小 Expo + React Navigation 实现**

`apps/mobile/package.json`

```json
{
  "name": "@ai-store-manager/mobile",
  "private": true,
  "version": "0.1.0",
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "test": "jest"
  },
  "dependencies": {
    "expo": "~53.0.7",
    "react": "19.0.0",
    "react-native": "0.79.2",
    "@react-navigation/native": "^7.1.6",
    "@react-navigation/bottom-tabs": "^7.3.10",
    "react-native-safe-area-context": "^5.4.0",
    "react-native-screens": "^4.11.1"
  },
  "devDependencies": {
    "@testing-library/react-native": "^13.2.0",
    "@types/jest": "^29.5.14",
    "@types/react": "^19.0.10",
    "jest": "^29.7.0",
    "jest-expo": "~53.0.5",
    "typescript": "^5.8.3"
  }
}
```

`apps/mobile/app.json`

```json
{
  "expo": {
    "name": "AI Store Manager",
    "slug": "ai-store-manager-mobile",
    "version": "0.1.0"
  }
}
```

`apps/mobile/babel.config.js`

```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
  };
};
```

`apps/mobile/jest.config.js`

```js
module.exports = {
  preset: "jest-expo",
};
```

`apps/mobile/tsconfig.json`

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true
  }
}
```

`apps/mobile/App.tsx`

```tsx
import RootNavigator from "./src/app/navigation/RootNavigator";

export default function App() {
  return <RootNavigator />;
}
```

`apps/mobile/src/app/navigation/RootNavigator.tsx`

```tsx
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import DashboardScreen from "../../features/dashboard/screens/DashboardScreen";
import ChatScreen from "../../features/chat/screens/ChatScreen";
import LedgerScreen from "../../features/ledger/screens/LedgerScreen";

const Tab = createBottomTabNavigator();

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator>
        <Tab.Screen name="工作台" component={DashboardScreen} />
        <Tab.Screen name="工作群" component={ChatScreen} />
        <Tab.Screen name="账本" component={LedgerScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
```

`apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`

```tsx
import { Text, View } from "react-native";

export default function DashboardScreen() {
  return (
    <View>
      <Text>工作台</Text>
      <Text>Phase 1 skeleton</Text>
    </View>
  );
}
```

`apps/mobile/src/features/chat/screens/ChatScreen.tsx`

```tsx
import { Text, View } from "react-native";

export default function ChatScreen() {
  return (
    <View>
      <Text>工作群</Text>
      <Text>Phase 1 skeleton</Text>
    </View>
  );
}
```

`apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`

```tsx
import { Text, View } from "react-native";

export default function LedgerScreen() {
  return (
    <View>
      <Text>账本</Text>
      <Text>Phase 1 skeleton</Text>
    </View>
  );
}
```

- [ ] **Step 4: 重新安装依赖并运行移动端测试**

Run:

```powershell
npm --prefix apps/mobile install
npm --prefix apps/mobile test -- --runInBand
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/mobile
git commit -m "feat: add mobile phase 1 shell"
```

### Task 6: 总体验证

- [ ] **Step 1: 运行后端全部测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- 全部后端测试通过

- [ ] **Step 2: 运行移动端测试**

Run:

```powershell
npm --prefix apps/mobile test -- --runInBand
```

Expected:

- 移动端测试通过

- [ ] **Step 3: 重新验证 Docker 配置**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- 退出码为 `0`

- [ ] **Step 4: 检查 git 状态，确认只包含本阶段变更**

Run:

```powershell
git status --short
```

Expected:

- 只显示本阶段预期文件
- 不应误纳入 `claw-code-main/`

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "test: verify phase 1 foundation skeleton"
```
