# Business Commercial Mock Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Business 项目中仍可能进入运行时的 mock/demo/stub 路径替换为真实可商用第三方服务或非 mock 实现，并确保生产环境无法误用 mock。

**Architecture:** 采用“先门禁、后替换、再验收”的方式推进：先建立 APP_ENV=production 的强校验，防止 mock 配置启动；再逐步接入真实对象存储、真实短信验证码、真实 OCR/Vision/ASR 或客户端 ASR 文本方案；最后拆分 local-demo 与 real-provider 验收脚本。所有关键业务写操作继续走确认单，不允许 AI 或第三方服务直接落账。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, React H5/Vite, DeepSeek chat/completions, 火山方舟 Ark/Doubao, S3-compatible Object Storage（火山 TOS/OSS/COS/S3 任选）, 商用短信服务（火山短信/阿里云短信/腾讯云短信任选）, Docker.

---

## 0. 执行前约定

### 环境与安全

- 仓库路径：`/root/business-clone`
- 分支：`hermes/ai-native-saas-rewrite`
- Python 命令：必须使用 `python3`
- 后端测试：必须带 `PYTHONPATH=backend`
- 禁止提交真实 API Key、短信密钥、对象存储密钥、数据库连接串、Redis 连接串。
- 文档、日志、提交信息里如需提及密钥，一律写 `[REDACTED]`。
- 不提交未跟踪文件 `dashboard.jpg`。

### 用户需要配合提供的真实服务

用户需要择一确认或提供以下服务信息：

1. 对象存储
   - 推荐优先级：火山 TOS > 阿里 OSS > 腾讯 COS > 任意 S3-compatible
   - 需要：endpoint、region、bucket、access key、secret key、public base URL 或 CDN 域名

2. 短信验证码
   - 推荐优先级：火山短信 > 阿里云短信 > 腾讯云短信
   - 需要：access key、secret key、签名、模板 ID、区域/endpoint

3. ASR
   - P0 推荐：客户端手机系统 ASR 转文字，后端只接收 `voice_text`
   - 如果坚持服务端 ASR：需要明确可用 endpoint、model/endpoint id、请求体音频字段格式、鉴权方式

4. OCR/Vision
   - 当前已接火山方舟 `doubao-seed-2-0-pro-260215`
   - 需要生产环境 Ark API Key 与 Endpoint 配置，通过环境变量注入

---

## Task 1: 生产环境 mock 门禁

**Files:**
- Modify: `backend/app/core/config.py`
- Modify/Create: `backend/app/services/system_readiness.py`（如果当前文件存在则扩展；不存在则创建）
- Test: `backend/tests/test_production_mock_guardrails.py`

### 目标

在 `APP_ENV=production` 时，禁止以下配置启动或判定为 ready：

- `OBJECT_STORAGE_PROVIDER=mock`
- `OCR_PROVIDER` 为空或 `mock`
- `VISION_PROVIDER` 为空或 `mock`
- `OCR_ALLOW_MOCK_FALLBACK=1`
- `VISION_ALLOW_MOCK_FALLBACK=1`
- `ASR_ALLOW_MOCK_FALLBACK=1` 且服务端 ASR 启用
- `LLM_PROVIDER=mock`
- `LLM_ALLOW_MOCK_FALLBACK=1`
- 演示验证码万能码在 production 可用

### Steps

- [x] Step 1: 写失败测试 `backend/tests/test_production_mock_guardrails.py`

测试用例必须覆盖：

```python
import os
import pytest

from app.core.config import Settings


def test_production_rejects_mock_object_storage():
    settings = Settings(app_env="production", object_storage_provider="mock")
    violations = settings.production_mock_violations()
    assert any(v["key"] == "OBJECT_STORAGE_PROVIDER" for v in violations)


def test_production_rejects_empty_ocr_provider():
    settings = Settings(app_env="production", ocr_provider="", ocr_allow_mock_fallback=False)
    violations = settings.production_mock_violations()
    assert any(v["key"] == "OCR_PROVIDER" for v in violations)


def test_production_rejects_ocr_mock_fallback():
    settings = Settings(app_env="production", ocr_provider="volcano", ocr_allow_mock_fallback=True)
    violations = settings.production_mock_violations()
    assert any(v["key"] == "OCR_ALLOW_MOCK_FALLBACK" for v in violations)


def test_production_rejects_vision_mock_fallback():
    settings = Settings(app_env="production", vision_provider="volcano", vision_allow_mock_fallback=True)
    violations = settings.production_mock_violations()
    assert any(v["key"] == "VISION_ALLOW_MOCK_FALLBACK" for v in violations)


def test_production_accepts_real_deepseek_ark_and_s3_config():
    settings = Settings(
        app_env="production",
        object_storage_provider="s3-compatible",
        object_storage_bucket="business-prod-media",
        object_storage_endpoint_url="https://tos.example.com",
        object_storage_region="cn-beijing",
        object_storage_access_key_id="configured",
        object_storage_secret_access_key="configured",
        ocr_provider="volcano",
        ocr_provider_api_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        ocr_provider_api_key="configured",
        ocr_provider_model="doubao-seed-2-0-pro-260215",
        ocr_allow_mock_fallback=False,
        vision_provider="volcano",
        vision_provider_api_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        vision_provider_api_key="configured",
        vision_provider_model="doubao-seed-2-0-pro-260215",
        vision_allow_mock_fallback=False,
        llm_provider="deepseek",
        llm_provider_api_url="https://api.deepseek.com/v1/chat/completions",
        llm_provider_api_key="configured",
        llm_provider_model="deepseek-v4-flash",
        llm_allow_mock_fallback=False,
    )
    assert settings.production_mock_violations() == []
```

- [x] Step 2: 运行测试确认失败

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_production_mock_guardrails.py -q
```

预期：失败，因为 `production_mock_violations()` 尚未实现。

- [x] Step 3: 在 `Settings` 增加 `production_mock_violations()`

实现要求：

```python
def production_mock_violations(self) -> list[dict[str, str]]:
    if self.app_env.strip().lower() != "production":
        return []
    violations: list[dict[str, str]] = []

    def add(key: str, message: str) -> None:
        violations.append({"key": key, "message": message})

    if self.normalized_object_storage_provider() == "mock":
        add("OBJECT_STORAGE_PROVIDER", "production requires real object storage")

    if self.llm_provider.strip().lower() in {"", "mock"}:
        add("LLM_PROVIDER", "production requires real LLM provider")
    if self.llm_allow_mock_fallback:
        add("LLM_ALLOW_MOCK_FALLBACK", "production cannot allow LLM mock fallback")

    if self.ocr_provider.strip().lower() in {"", "mock"}:
        add("OCR_PROVIDER", "production requires real OCR provider")
    if self.ocr_allow_mock_fallback:
        add("OCR_ALLOW_MOCK_FALLBACK", "production cannot allow OCR mock fallback")

    if self.vision_provider.strip().lower() in {"", "mock"}:
        add("VISION_PROVIDER", "production requires real Vision provider")
    if self.vision_allow_mock_fallback:
        add("VISION_ALLOW_MOCK_FALLBACK", "production cannot allow Vision mock fallback")

    if self.asr_provider.strip().lower() not in {"", "client", "client-asr", "disabled", "none"} and self.asr_allow_mock_fallback:
        add("ASR_ALLOW_MOCK_FALLBACK", "production cannot allow ASR mock fallback when server ASR is enabled")

    return violations
```

- [x] Step 4: 将生产门禁接入 readiness

如果存在 `system_readiness.py`，增加 `mock_guardrails` check。
如果没有，则创建最小检查服务，要求 readiness API 输出：

```json
{
  "key": "mock_guardrails",
  "status": "ready|degraded",
  "summary": "production mock guardrails passed|production mock configuration detected",
  "details": {
    "violation_count": 0,
    "violations": [{"key": "OCR_PROVIDER", "message": "..."}]
  }
}
```

不能输出 secret 原文。

- [x] Step 5: 运行测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_production_mock_guardrails.py backend/tests/test_production_readiness_config.py -q
```

- [x] Step 6: 提交

```bash
cd /root/business-clone
git add backend/app/core/config.py backend/app/services/system_readiness.py backend/tests/test_production_mock_guardrails.py
git commit -m "guard: block mock providers in production"
```

---

## Task 2: 对象存储接入真实 S3-compatible/TOS

**Files:**
- Modify: `backend/app/services/object_storage.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_object_storage_provider.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

### 目标

将对象存储从默认 mock 切到可商用 S3-compatible 配置；mock 仅 local-demo/test 使用。

### Steps

- [x] Step 1: 写对象存储配置测试

覆盖：

```python
def test_production_s3_requires_bucket_endpoint_and_credentials():
    settings = Settings(app_env="production", object_storage_provider="s3-compatible")
    with pytest.raises(ObjectStorageConfigurationError):
        build_object_storage(settings)


def test_s3_compatible_provider_builds_with_required_config(fake_s3_client):
    provider = S3CompatibleObjectStorageProvider(
        bucket="business-prod-media",
        endpoint_url="https://tos.example.com",
        region="cn-beijing",
        access_key_id="configured",
        secret_access_key="configured",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=600,
        s3_client=fake_s3_client,
    )
    target = provider.create_upload_target(object_key="tenants/t1/shops/s1/media/m1/a.jpg", content_type="image/jpeg")
    assert target.object_key.endswith("a.jpg")
    assert target.public_url == "https://cdn.example.com/tenants/t1/shops/s1/media/m1/a.jpg"
```

- [x] Step 2: 运行测试确认当前行为

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_object_storage_provider.py -q
```

- [x] Step 3: 确认 `object_storage.py` 的 S3-compatible 分支完整可用

重点确认：

- `create_upload_target()` 使用 presigned put_object URL
- `verify_object()` 使用 head_object
- `read_object_bytes()` 使用 get_object
- 错误信息不输出 access key / secret

- [x] Step 4: 更新 `.env.example`

新增/整理：

```bash
OBJECT_STORAGE_PROVIDER=s3-compatible
OBJECT_STORAGE_BUCKET=business-prod-media
OBJECT_STORAGE_ENDPOINT_URL=https://tos-cn-beijing.volces.com
OBJECT_STORAGE_REGION=cn-beijing
OBJECT_STORAGE_ACCESS_KEY_ID=
OBJECT_STORAGE_SECRET_ACCESS_KEY=
OBJECT_STORAGE_PUBLIC_BASE_URL=https://media.example.com
OBJECT_STORAGE_PRESIGN_TTL_SECONDS=600
```

local-demo 单独注释：

```bash
# Local demo only:
# OBJECT_STORAGE_PROVIDER=mock
```

- [ ] Step 5: 用用户提供的真实对象存储配置做一次非破坏性验收

当前状态：待用户提供真实 TOS/OSS/COS/S3-compatible endpoint、region、bucket、access key、secret key、public base URL 后执行；不得在仓库或日志记录真实值。

命令格式，不记录真实值：

```bash
cd /root/business-clone
OBJECT_STORAGE_PROVIDER=s3-compatible \
OBJECT_STORAGE_BUCKET=... \
OBJECT_STORAGE_ENDPOINT_URL=... \
OBJECT_STORAGE_REGION=... \
OBJECT_STORAGE_ACCESS_KEY_ID=[REDACTED] \
OBJECT_STORAGE_SECRET_ACCESS_KEY=[REDACTED] \
OBJECT_STORAGE_PUBLIC_BASE_URL=... \
PYTHONPATH=backend python3 - <<'PY'
from app.core.config import get_settings
from app.services.object_storage import build_object_storage
settings = get_settings()
provider = build_object_storage(settings)
target = provider.create_upload_target(
    object_key="health-check/business-object-storage-check.txt",
    content_type="text/plain",
)
print({"ok": True, "upload_url_prefix": target.upload_url.split(':', 1)[0], "public_url_configured": bool(target.public_url)})
PY
```

注意：不要把真实签名 URL 打印出来。

- [x] Step 6: 运行媒体相关测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_object_storage_provider.py backend/tests/test_v2_media_ai_platform.py -q
```

- [ ] Step 7: 提交

```bash
git add backend/app/services/object_storage.py backend/app/core/config.py backend/.env.example backend/tests/test_object_storage_provider.py backend/tests/test_v2_media_ai_platform.py
git commit -m "feat: require real object storage for production"
```

---

## Task 3: 短信验证码替换 888888 演示登录

**Files:**
- Create: `backend/app/services/sms_provider.py`
- Create: `backend/app/services/verification_codes.py`
- Modify: `backend/app/api/v2/routes/identity.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `apps/h5/src/App.tsx`
- Modify: `apps/h5/src/api.ts`
- Test: `backend/tests/test_v2_identity_sms_login.py`

### 目标

生产环境使用真实短信验证码；local-demo 才允许 888888。

### 设计

新增两个后端服务：

1. `sms_provider.py`
   - `SmsProvider` protocol
   - `DemoSmsProvider`
   - `VolcengineSmsProvider` 或通用 `HttpSmsProvider`

2. `verification_codes.py`
   - 生成 6 位验证码
   - hash 后存储，不能明文存 DB
   - TTL 默认 5 分钟
   - 验证成功后一次性消费
   - 限流：同手机号 60 秒内不能重复发送，同 IP/手机号每天上限

当前实现说明：已实现生产禁用 888888、验证码发送接口、hash 后内存存储与一次性消费；V2Account 尚无 phone 字段，生产验证码通过后暂只映射到配置的 owner 账号，后续需补手机号绑定 schema/migration。

### Steps

- [x] Step 1: 写失败测试

测试至少覆盖：

```python
def test_demo_phone_login_accepts_888888_only_in_local_demo(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")
    response = client.post("/api/v2/auth/login", json={
        "auth_method": "phone_code",
        "phone": "13800000000",
        "verification_code": "888888",
    })
    assert response.status_code == 200


def test_production_rejects_888888_without_sent_code(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")
    response = client.post("/api/v2/auth/login", json={
        "auth_method": "phone_code",
        "phone": "13800000000",
        "verification_code": "888888",
    })
    assert response.status_code == 401


def test_send_code_endpoint_uses_sms_provider(client, fake_sms_provider):
    response = client.post("/api/v2/auth/verification-codes", json={"phone": "13800000000"})
    assert response.status_code == 200
    assert fake_sms_provider.sent_messages
```

- [x] Step 2: 增加发送验证码接口

建议接口：

```http
POST /api/v2/auth/verification-codes
{
  "phone": "13800000000"
}
```

响应：

```json
{
  "ok": true,
  "expires_in_seconds": 300
}
```

- [x] Step 3: 修改登录逻辑

`identity.py` 中 `phone_code`：

- local-demo + `888888`：允许
- production：必须查验验证码记录
- 验证成功：绑定/查找手机号对应 account
- 不再 fallback 到“第一个 active account”

- [x] Step 4: 前端登录页改造

`apps/h5/src/App.tsx`：

- production 不再默认填 13800000000 / 888888
- 增加“获取验证码”按钮
- demo mode 才显示“演示验证码 888888”

`apps/h5/src/api.ts`：

```ts
sendVerificationCode: (phone: string) => request<{ ok: boolean; expires_in_seconds: number }>('/api/v2/auth/verification-codes', {
  method: 'POST',
  body: JSON.stringify({ phone })
})
```

- [ ] Step 5: 真实短信沙箱/测试号验收

当前状态：待用户提供短信服务商、签名、模板 ID、测试手机号与凭证后执行；命令和日志不得打印真实密钥。

用户提供短信服务后，用真实测试手机号发送一次验证码。
命令中不打印密钥。

- [x] Step 6: 测试

已执行：
```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_v2_identity_sms_login.py backend/tests/test_v2_identity_context.py backend/tests/test_production_mock_guardrails.py backend/tests/test_object_storage_provider.py backend/tests/test_v2_media_ai_platform.py -q
cd apps/h5 && npm run build
```

- [ ] Step 7: 提交

```bash
git add backend/app/services/sms_provider.py backend/app/services/verification_codes.py backend/app/api/v2/routes/identity.py backend/app/core/config.py backend/.env.example apps/h5/src/App.tsx apps/h5/src/api.ts backend/tests/test_v2_identity_sms_login.py
git commit -m "feat: replace demo phone login with real verification codes"
```

---

## Task 4: OCR/Vision 禁用生产 mock fallback，并保留 local-demo mock

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/ocr_gateway.py`
- Modify: `backend/app/services/vision_gateway.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_ocr_gateway.py`
- Test: `backend/tests/test_vision_gateway.py`
- Test: `backend/tests/test_provider_trial_preflight.py`

### 目标

生产环境 OCR/Vision 必须使用真实 Ark/Doubao 或其它真实 provider。local-demo/test 可以使用 mock。

### Steps

- [ ] Step 1: 写失败测试

```python
def test_production_ocr_empty_provider_fails():
    settings = Settings(app_env="production", ocr_provider="", ocr_allow_mock_fallback=False)
    with pytest.raises(OcrProviderError):
        build_ocr_gateway(settings)


def test_production_vision_mock_provider_fails():
    settings = Settings(app_env="production", vision_provider="mock", vision_allow_mock_fallback=False)
    with pytest.raises(VisionProviderError):
        build_vision_gateway(settings)


def test_local_demo_ocr_can_use_mock():
    settings = Settings(app_env="development", app_runtime_mode="local-demo", ocr_provider="mock", ocr_allow_mock_fallback=True)
    gateway = build_ocr_gateway(settings)
    assert gateway.primary_provider.__class__.__name__ == "MockOcrProvider"
```

- [ ] Step 2: 修改 config 默认值

建议：

- `.env.example` 保持真实 volcano
- `Settings` 中 OCR/Vision fallback 默认可根据 APP_ENV 区分：production 默认 False，development/local-demo 可 True

- [ ] Step 3: 确保 Ark provider 配置缺失时报错，不回退 mock

`ocr_gateway.py` / `vision_gateway.py`：

- provider 是 `volcano/doubao/ark` 但缺 key：如果 fallback disabled，报错
- provider 是 `mock` 但 fallback disabled：报错

- [ ] Step 4: 运行测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_ocr_gateway.py backend/tests/test_vision_gateway.py backend/tests/test_provider_trial_preflight.py backend/tests/test_ark_multimodal_provider.py -q
```

- [ ] Step 5: 用真实 Ark Key 做非破坏性 OCR/Vision 健康检查

使用现有：

```bash
cd /root/business-clone
ARK_API_KEY=[REDACTED] PYTHONPATH=backend python3 backend/scripts/evaluate_ark_multimodal.py --repeats 1
```

确保输出报告不含 key。

- [ ] Step 6: 提交

```bash
git add backend/app/core/config.py backend/app/services/ocr_gateway.py backend/app/services/vision_gateway.py backend/.env.example backend/tests/test_ocr_gateway.py backend/tests/test_vision_gateway.py backend/tests/test_provider_trial_preflight.py
git commit -m "guard: disable OCR and vision mock fallback in production"
```

---

## Task 5: ASR 改为客户端 ASR 文本入口，服务端 ASR 默认禁用

**Files:**
- Modify: `backend/app/contracts/v2/chat.py` 或当前 chat request contract 文件
- Modify: `backend/app/api/v2/routes/chat.py`
- Modify: `backend/app/services/asr_gateway.py`
- Modify: `backend/app/core/config.py`
- Modify: `apps/h5/src/App.tsx`
- Modify: `apps/h5/src/api.ts`
- Test: `backend/tests/test_v2_client_asr_chat.py`

### 目标

P0 不再依赖服务端 ASR mock。客户端用手机系统语音输入得到文字，后端按 `input_type=voice_text` 处理。

### Steps

- [ ] Step 1: 写测试

```python
def test_chat_accepts_client_asr_text(client, auth_headers):
    response = client.post(
        "/api/v2/chat",
        headers=auth_headers,
        json={
            "message": "帮我查一下螺丝刀库存",
            "input_type": "voice_text",
            "source": "client_asr",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reply"]
```

- [ ] Step 2: Chat request contract 增加字段

```python
input_type: Literal["text", "voice_text"] = "text"
source: str | None = None
```

- [ ] Step 3: chat.py 记录来源但不调用 ASR

如果 `input_type=voice_text`：

- 校验 message 非空
- 正常交给 DeepSeek Main Agent
- audit/model call log 记录 source=`client_asr`

- [ ] Step 4: 服务端 ASR gateway production 默认禁用

推荐配置：

```bash
ASR_PROVIDER=client
ASR_ALLOW_MOCK_FALLBACK=0
```

`ASR_PROVIDER=mock` 仅 local-demo/test。

- [ ] Step 5: H5 增加语音文本来源标记

短期无需录音上传，只提示用户使用手机键盘语音输入。
如果未来做原生 App，再接系统 ASR SDK。

- [ ] Step 6: 测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_v2_client_asr_chat.py backend/tests/test_v2_chat_http_confirmation_flow.py -q
cd apps/h5 && npm run build
```

- [ ] Step 7: 提交

```bash
git add backend/app/api/v2/routes/chat.py backend/app/core/config.py apps/h5/src/App.tsx apps/h5/src/api.ts backend/tests/test_v2_client_asr_chat.py
git commit -m "feat: use client ASR text for voice chat"
```

---

## Task 6: 清理 `v2_photo.py` 旧图片/票据 stub

**Files:**
- Modify: `backend/app/services/v2_photo.py`
- Modify: 调用 `v2_photo.py` 的 route/service 文件，按实际搜索结果修改
- Test: `backend/tests/test_v2_voice_photo_http_confirmation_flow.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`
- Test: `backend/tests/test_ark_multimodal_provider.py`

### 目标

旧的图片/票据 stub 不再进入运行时。图片识别统一走 OCR/Vision gateway。

### Steps

- [ ] Step 1: 查找调用方

```bash
cd /root/business-clone
rg "process_photo_stock_in|_extract_text_from_image|extract_receipt|v2_photo" backend/app backend/tests
```

- [ ] Step 2: 写失败测试

测试要证明上传/图片处理不会返回固定样例：

```python
def test_photo_stock_in_uses_ocr_gateway_not_stub(monkeypatch, client, auth_headers):
    called = {"ocr": False}

    class FakeGateway:
        def extract_purchase_receipt(self, media_input):
            called["ocr"] = True
            return OcrExtraction(
                provider_name="fake-real-ocr",
                receipt_number="R-1",
                supplier_name="真实供应商",
                purchased_at=None,
                line_items=[],
                total_amount=None,
                confidence=0.91,
                low_confidence_fields=[],
                used_fallback=False,
                raw_payload={},
            )

    monkeypatch.setattr("app.services.v2_receipt_documents.get_default_ocr_gateway", lambda: FakeGateway())
    # call actual receipt/photo endpoint here
    assert called["ocr"] is True
```

- [ ] Step 3: 删除或改造 stub 函数

删除/替换这些逻辑：

- `Stub: Return simulated extraction result`
- `Stub for receipt extraction`
- 固定返回 `螺丝刀` / `测试供应商` / `250.0`

改为：

- 商品图：调用 `get_default_vision_gateway().recognize_product(...)`
- 采购票据：调用 `get_default_ocr_gateway().extract_purchase_receipt(...)`
- 识别后生成待确认单，不直接入库

- [ ] Step 4: 运行测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_v2_voice_photo_http_confirmation_flow.py backend/tests/test_v2_media_ai_platform.py backend/tests/test_ark_multimodal_provider.py -q
```

- [ ] Step 5: 提交

```bash
git add backend/app/services/v2_photo.py backend/app/api/v2 backend/tests/test_v2_voice_photo_http_confirmation_flow.py backend/tests/test_v2_media_ai_platform.py
git commit -m "refactor: route photo extraction through real AI gateways"
```

---

## Task 7: 拆分 local-demo 验收与 real-provider 生产验收脚本

**Files:**
- Modify: `backend/scripts/run_backend_preflight.sh`
- Create: `backend/scripts/run_real_provider_preflight.sh`
- Modify: `backend/scripts/run_docker_backend_acceptance.sh`
- Modify: `backend/scripts/run_lightweight_stability_check.py`
- Remove or update: 过期脚本引用，例如已删除测试 `test_v2_chat_confirmation_first.py`
- Test: `backend/tests/test_preflight_scripts_static.py`

### 目标

脚本命名和行为不能误导：

- local-demo 可以 mock
- real-provider preflight 必须真实 DeepSeek/Ark/ObjectStorage/SMS 配置
- Docker mock acceptance 不能被当成生产验收

### Steps

- [x] Step 1: 写静态测试

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_preflight_does_not_reference_deleted_tests():
    script = (ROOT / "backend/scripts/run_backend_preflight.sh").read_text()
    assert "test_v2_chat_confirmation_first.py" not in script


def test_real_provider_preflight_does_not_force_mock_providers():
    script = (ROOT / "backend/scripts/run_real_provider_preflight.sh").read_text()
    assert "LLM_PROVIDER=mock" not in script
    assert "OCR_PROVIDER=mock" not in script
    assert "VISION_PROVIDER=mock" not in script
```

- [x] Step 2: 更新 `run_backend_preflight.sh`

改成 local/test preflight，明确输出：

```bash
log "profile: local-demo/mock preflight; this does not validate commercial providers"
```

删除不存在测试。

- [x] Step 3: 新增 `run_real_provider_preflight.sh`

要求检查：

- DeepSeek provider configured
- Ark OCR/Vision configured
- ObjectStorage real provider configured
- SMS provider configured 或明确 SMS_REAL_PREFLIGHT=0 跳过
- APP_ENV=production 下 `production_mock_violations()` 为空

- [x] Step 4: Docker acceptance 改名或增加提示

如果暂不改文件名，至少输出：

```bash
log "starting backend container with mock providers for local acceptance only"
```

- [x] Step 5: 运行脚本测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_preflight_scripts_static.py -q
bash backend/scripts/run_backend_preflight.sh
```

- [x] Step 6: 提交

```bash
git add backend/scripts/run_backend_preflight.sh backend/scripts/run_real_provider_preflight.sh backend/scripts/run_docker_backend_acceptance.sh backend/scripts/run_lightweight_stability_check.py backend/tests/test_preflight_scripts_static.py
git commit -m "chore: split mock and real provider preflight scripts"
```

---

## Task 8: Demo seed 脚本加生产保护

**Files:**
- Modify: `backend/scripts/bootstrap_v2_trial_data.py`
- Test: `backend/tests/test_demo_seed_scripts.py`

### 目标

演示数据脚本保留，但 production 环境禁止执行。

### Steps

- [x] Step 1: 写测试

```python
def test_bootstrap_trial_data_refuses_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from backend.scripts import bootstrap_v2_trial_data
    with pytest.raises(SystemExit) as exc:
        bootstrap_v2_trial_data.ensure_not_production()
    assert exc.value.code != 0
```

- [x] Step 2: 实现 `ensure_not_production()`

```python
def ensure_not_production() -> None:
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise SystemExit("Refusing to seed trial data in production")
```

在 `__main__` 最开始调用。

- [x] Step 3: 更新脚本文案

开头打印：

```text
Bootstrapping V2 Trial Data for local-demo/trial only
```

- [x] Step 4: 运行测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_demo_seed_scripts.py -q
```

- [x] Step 5: 提交

```bash
git add backend/scripts/bootstrap_v2_trial_data.py backend/tests/test_demo_seed_scripts.py
git commit -m "guard: prevent demo seed data in production"
```

---

## Task 9: H5 demo mode 开关

**Files:**
- Modify: `apps/h5/src/App.tsx`
- Modify: `apps/h5/.env.example`（如果存在；不存在则创建）
- Test: H5 build

### 目标

生产前端不显示默认演示手机号/验证码；local demo 才显示。

### Steps

- [x] Step 1: 增加 Vite 环境变量

```ts
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === '1'
```

- [x] Step 2: 登录页初始值改为

```ts
const [phone, setPhone] = useState(DEMO_MODE ? '13800000000' : '')
const [code, setCode] = useState(DEMO_MODE ? '888888' : '')
```

按钮文案：

```tsx
{DEMO_MODE ? '演示登录（888888）' : '登录'}
```

- [x] Step 3: `.env.example`

```bash
VITE_API_BASE_URL=
VITE_DEMO_MODE=0
```

local demo 可设置：

```bash
VITE_DEMO_MODE=1
```

- [x] Step 4: build 验证

```bash
cd /root/business-clone/apps/h5
npm run build
```

- [x] Step 5: 提交

```bash
cd /root/business-clone
git add apps/h5/src/App.tsx apps/h5/.env.example
git commit -m "feat: gate H5 demo login behind demo mode"
```

---

## Task 10: 商业化真实 provider 总验收

**Files:**
- Create: `docs/commercial/REAL_PROVIDER_ACCEPTANCE.md`
- Create/Modify: `backend/scripts/run_real_provider_preflight.sh`

### 目标

提供一套不泄露密钥的真实 provider 验收流程，覆盖：

- DeepSeek Main Agent
- Ark OCR
- Ark Vision
- Object Storage
- SMS verification
- Production mock guardrails
- H5 build
- 后端核心 HTTP flow

### Steps

- [ ] Step 1: 文档化真实 provider 环境变量

写入 `docs/commercial/REAL_PROVIDER_ACCEPTANCE.md`：

```bash
APP_ENV=production
APP_RUNTIME_MODE=production
LLM_PROVIDER=deepseek
LLM_PROVIDER_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_PROVIDER_API_KEY=[REDACTED]
LLM_PROVIDER_MODEL=deepseek-v4-flash
LLM_ALLOW_MOCK_FALLBACK=0

OCR_PROVIDER=volcano
OCR_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
OCR_PROVIDER_API_KEY=[REDACTED]
OCR_PROVIDER_MODEL=doubao-seed-2-0-pro-260215
OCR_ALLOW_MOCK_FALLBACK=0

VISION_PROVIDER=volcano
VISION_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
VISION_PROVIDER_API_KEY=[REDACTED]
VISION_PROVIDER_MODEL=doubao-seed-2-0-pro-260215
VISION_ALLOW_MOCK_FALLBACK=0

ASR_PROVIDER=client
ASR_ALLOW_MOCK_FALLBACK=0

OBJECT_STORAGE_PROVIDER=s3-compatible
OBJECT_STORAGE_BUCKET=...
OBJECT_STORAGE_ENDPOINT_URL=...
OBJECT_STORAGE_REGION=...
OBJECT_STORAGE_ACCESS_KEY_ID=[REDACTED]
OBJECT_STORAGE_SECRET_ACCESS_KEY=[REDACTED]
OBJECT_STORAGE_PUBLIC_BASE_URL=...

SMS_PROVIDER=...
SMS_ACCESS_KEY_ID=[REDACTED]
SMS_SECRET_ACCESS_KEY=[REDACTED]
SMS_SIGN_NAME=...
SMS_TEMPLATE_ID=...
```

- [ ] Step 2: 总验收命令

```bash
cd /root/business-clone
python3 -m compileall -q backend/app backend/scripts
PYTHONPATH=backend python3 -m pytest backend/tests -q
cd apps/h5 && npm run build
cd /root/business-clone && bash backend/scripts/run_real_provider_preflight.sh
```

- [ ] Step 3: 密钥扫描

```bash
cd /root/business-clone
python3 - <<'PY'
from pathlib import Path
import re
patterns = [
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'AKLT[A-Za-z0-9_-]{20,}'),
    re.compile(r'(SECRET|TOKEN|PASSWORD|API_KEY)\s*=\s*[^\s\[]+', re.I),
]
violations = []
for path in Path('.').rglob('*'):
    if path.is_dir() or '.git' in path.parts or 'node_modules' in path.parts:
        continue
    try:
        text = path.read_text(errors='ignore')
    except Exception:
        continue
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(0)
            if '[REDACTED]' in value or 'example' in value.lower() or 'placeholder' in value.lower():
                continue
            violations.append((str(path), value[:80]))
if violations:
    for item in violations[:20]:
        print(item)
    raise SystemExit('SECRET_SCAN_FAILED')
print('SECRET_SCAN_OK')
PY
```

- [ ] Step 4: 提交验收文档

```bash
git add docs/commercial/REAL_PROVIDER_ACCEPTANCE.md backend/scripts/run_real_provider_preflight.sh
git commit -m "docs: add real provider commercial acceptance checklist"
```

---

## Task 11: 最终全量验证、提交、推送

**Files:**
- All changed files

### Steps

- [ ] Step 1: 查看状态，确认不提交 `dashboard.jpg`

```bash
cd /root/business-clone
git status --short
git diff --check
if git diff --cached --name-only | grep -qx 'dashboard.jpg'; then echo 'dashboard.jpg staged unexpectedly'; exit 1; fi
```

- [ ] Step 2: 全量后端测试

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

- [ ] Step 3: H5 build

```bash
cd /root/business-clone/apps/h5
npm run build
```

- [ ] Step 4: OpenAPI 快照

```bash
cd /root/business-clone
PYTHONPATH=backend python3 backend/scripts/generate_openapi_snapshot.py
PYTHONPATH=backend python3 -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [ ] Step 5: 密钥扫描

运行 Task 10 的 `SECRET_SCAN_OK` 脚本。

- [ ] Step 6: 提交剩余变更

```bash
cd /root/business-clone
git add backend apps docs project_docs
git status --short
if git diff --cached --name-only | grep -qx 'dashboard.jpg'; then echo 'dashboard.jpg staged unexpectedly'; exit 1; fi
git commit -m "feat: replace runtime mock paths with commercial providers"
```

- [ ] Step 7: 推送

```bash
git push origin hermes/ai-native-saas-rewrite
```

---

## 实施顺序建议

建议拆成 4 个阶段推进：

### Phase A：先防误用

1. Task 1 生产 mock 门禁
2. Task 7 拆分 mock/real preflight
3. Task 8 demo seed 生产保护
4. Task 9 H5 demo mode 开关

产出：即使还没全部接真实服务，生产环境也不会误启动 mock。

### Phase B：真实基础设施

1. Task 2 对象存储
2. Task 3 短信验证码

产出：用户登录与媒体存储具备商业化基础。

### Phase C：真实 AI 输入链路

1. Task 4 OCR/Vision 生产禁 mock
2. Task 5 客户端 ASR 文本入口
3. Task 6 清理 v2_photo stub

产出：图片、票据、语音文字入口不再使用模拟结果。

### Phase D：验收与推送

1. Task 10 真实 provider 总验收
2. Task 11 全量验证、提交、推送

产出：形成可重复的商业化验收流程。

---

## 风险与取舍

1. 短信验证码可能受备案、签名、模板审核影响。
   - 解决：先抽象 provider，测试用 fake provider，真实短信等待服务审核通过。

2. 对象存储 public URL/CDN 权限可能配置复杂。
   - 解决：先用私有 bucket + presigned URL；public URL 后续接 CDN。

3. 服务端 ASR 暂无已验证可用端点。
   - 解决：P0 使用客户端 ASR 文本，不阻塞产品闭环。

4. OCR/Vision 真实模型有延迟和费用。
   - 解决：保留 local-demo mock，但 production 禁止 fallback；增加模型调用日志和错误提示。

5. 生产门禁可能影响本地测试。
   - 解决：仅 APP_ENV=production 生效；测试/local-demo 不受影响。

---

## 成功标准

完成后应满足：

- `APP_ENV=production` 下 mock provider 或 fallback 配置会被 readiness 标记 degraded，关键场景可直接启动失败或拒绝 ready。
- DeepSeek 主 Agent 使用真实 DeepSeek provider，不存在 LLM mock 默认路径。
- OCR/Vision 生产使用真实 Ark/Doubao，不会回退 mock。
- ASR P0 使用客户端系统 ASR 文本，不依赖服务端 mock。
- 对象存储生产使用真实 S3-compatible/TOS/OSS/COS。
- 手机验证码生产使用真实短信服务，不接受 888888 万能码。
- 图片/票据识别不再返回 `螺丝刀/测试供应商/250.0` 这类固定 stub 数据。
- local-demo/test 仍可使用 mock，但脚本和文档明确标记，不代表商业化验收。
- 全量测试、H5 build、OpenAPI 快照、密钥扫描通过。
