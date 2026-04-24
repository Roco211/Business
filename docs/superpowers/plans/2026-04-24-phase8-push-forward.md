# Phase 8 推进计划：火山引擎 LLM 深度集成

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Phase 7 的 mock/stub AI 能力（ASR/OCR/Vision/LLM）全部替换为真正的火山引擎大模型

**架构:** Provider Gateway + Real Provider 模式，支持自动降级和性能追踪

**技术栈:** Volcano Engine SDK, FastAPI, asyncio, aiohttp

---

## 当前状态

| Provider | 当前状态 | 目标状态 |
|----------|----------|----------|
| LLM | ✅ Provider基类已完成 | Stream响应优化 |
| ASR | ⏳ Stub | Volcano ASR API |
| OCR | ⏳ Stub | Volcano OCR API |
| Vision | ⏳ Stub | Volcano Vision API |

---

## 任务清单

### Task 1: 修复 V2 数据注入脚本
**目标:** 让 bootstrap_v2_trial_data.py 成功运行，创建演示数据

**Files:**
- Fix: `backend/scripts/bootstrap_v2_trial_data.py`

- [ ] **Step 1: 修复 V2InventoryStockSnapshot 字段**

读取模型定义，使用正确字段名:
```python
items = [
    V2InventoryStockSnapshot(
        shop_id=shop_id,
        sku="TOOL-HAMMER-001",
        name="高精度锤子", 
        current_quantity=15,  # 不是 quantity
        low_stock_threshold=5,
        unit_price=39.9,
        recorded_at=utc_now(),
    ),
    # ... 其他商品
]
```

- [ ] **Step 2: 验证数据库写入**

运行: `cd backend && PYTHONPATH=. python3 scripts/bootstrap_v2_trial_data.py`

预期输出:
```
✅ V2 Trial data seeded!
Login: demo@aistoremanager.com / demo123
```

---

### Task 2: LLM 配置完善
**目标:** 在 config.py 添加完整的 LLM 配置支持

**Files:**
- Modify: `backend/app/core/config.py`
- New: `backend/app/services/v2_config_provider.py` (Provider配置管理)

- [ ] **Step 1: 添加 LLM 配置类**

```python
# 在 config.py 添加
class LLMSettings(BaseSettings):
    provider: str = "volcano"
    api_url: str = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    api_key: str = ""
    model: str = "ep-20260416043519-v4vzq"  # 豆包-lite-128k
    max_tokens: int = 150
    temperature: float = 0.3
    request_timeout: float = 30.0
```

- [ ] **Step 2: Provider 配置管理器**

创建 `v2_config_provider.py` 统一管理 ASR/OCR/Vision/LLM 配置

---

### Task 3: LLM Service 层连接
**目标:** 让 v2_llm.py 使用真正的 LLM Provider

**Files:**
- Modify: `backend/app/services/v2_llm.py`
- Test: `backend/tests/test_v2_llm_real.py`

- [ ] **Step 1: 重构 Intent Service 使用真 LLM**

```python
class V2IntentService:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        self.fallback = V2RuleBasedIntentService()  # 降级方案
    
    async def classify(self, text: str) -> IntentResult:
        try:
            return await self._llm_classify(text)
        except LLMError:
            return await self.fallback.classify(text)
```

- [ ] **Step 2: 创建端到端测试脚本**

```bash
curl -X POST http://localhost:8001/api/v2/chat \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "test", "content": "查一下库存"}' \
  --no-buffer
```

---

### Task 4: ASR Provider 接入火山引擎
**目标:** 配置并接入 Volcano ASR API

**Files:**
- Modify: `backend/app/services/v2_asr_real_provider.py`
- Modify: `backend/app/services/v2_voice.py`
- Config: `.env` ASR配置

- [ ] **Step 1: 配置火山 ASR**

```bash
# .env
ASR_PROVIDER=volcano
ASR_API_URL=https://ark.cn-beijing.volces.com/api/v3/audio/quick-digest
ASR_API_KEY=${VOLCANO_API_KEY}
ASR_MODEL=ep-xxxxxxxx
```

- [ ] **Step 2: 实现 ASR Real Provider**

```python
class VolcanoASRProvider:
    async def transcribe(self, audio_data: bytes) -> str:
        # 调用火山 ASR API
        # audio/quick-digest 模型
        pass
```

---

### Task 5: OCR/Vision Provider 接入
**目标:** 配置并接入 Volcano OCR & Vision API

**Files:**
- Modify: `backend/app/services/v2_ocr_real_provider.py`
- Modify: `backend/app/services/v2_vision_real_provider.py`
- Modify: `backend/app/services/v2_photo.py`
- Modify: `backend/app/services/v2_receipt_documents.py`

- [ ] **Step 1: 配置火山 OCR**

```bash
OCR_PROVIDER=volcano
OCR_API_URL=https://ark.cn-beijing.volces.com/api/v3/ocr/invoice
OCR_API_KEY=${VOLCANO_API_KEY}
OCR_MODEL=ep-xxxxxxxx
```

- [ ] **Step 2: 配置火山 Vision**

```bash
VISION_PROVIDER=volcano
VISION_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
VISION_API_KEY=${VOLCANO_API_KEY}
VISION_MODEL=ep-xxxxxxxx
```

---

### Task 6: 性能统计与追踪
**目标:** 添加 LLM 调用性能指标采集

**Files:**
- Modify: `backend/app/services/v2_llm.py` (添加tracing)
- New: `backend/app/services/v2_metrics.py`

- [ ] **Step 1: 添加 Latency/Throughput 追踪**

```python
@dataclass
class LLMCallMetrics:
    latency_ms: float
    tokens_per_second: float
    success: bool
    error_type: Optional[str]
```

---

### Task 7: 场景验证测试
**目标:** 创建完整的场景测试套件

**Files:**
- New: `backend/scripts/test_phase8_scenarios.py`

- [ ] **Step 1: 测试 Voice Stock Query**

```bash
./scripts/test_phase8_scenarios.py --scenario voice_stock_query
```

- [ ] **Step 2: 测试 Photo Stock Query**

```bash
./scripts/test_phase8_scenarios.py --scenario photo_stock_query
```

- [ ] **Step 3: 测试 Receipt OCR**

```bash
./scripts/test_phase8_scenarios.py --scenario receipt_ocr
```

---

## 使用 Superpowers 推进方式

### 方式 1: 子代理驱动开发 (推荐)

为每个 Task 创建独立子代理并行开发:

```python
# 使用 delegate_task 并行启动 4 个子代理
tasks = [
    {"goal": "Task 1: 修复 V2 数据注入脚本", "file": "bootstrap_v2_trial_data.py"},
    {"goal": "Task 2: LLM 配置完善", "file": "config.py"},
    {"goal": "Task 4: ASR Provider 接入", "file": "asr_provider.py"},
    {"goal": "Task 5: OCR/Vision Provider 接入", "file": "ocr_provider.py"},
]
```

### 方式 2: 单文件极速推进

使用 TDD 单文件顺序完成

### 方式 3: Inline Execution

批量执行，使用 executing-plans skill

---

## 验证清单

- [ ] V2 数据注入成功运行
- [ ] LLM 配置完整可用
- [ ] ASR 返回真实转录结果 (非 mock)
- [ ] OCR 识别真实票据文字
- [ ] Vision 识别真实图片内容
- [ ] Stream 响应首包延迟 < 2s
- [ ] Latency 指标可观测

---

## 下一步行动建议

**选项 A: 并行子代理 (推荐)**
- 同时启动 Task 1/4/5/6
- 任务间无依赖，可并行
- 预估总时间: 8h

**选项 B: 单点突破**
- 先完成 Task 1 (数据基础)
- 然后 Task 3 (LLM连接)
- 再 Task 4/5 (ASR/OCR)
- 预估: 6h + 各Provider 4h each

**选项 C: 场景驱动**
- 先完成 Voice Stock Query 端到端
- 验证后复制到其他场景
- 预估: 4h (MVP) + 16h (复制)

**推荐: 选项 A** - 当前 infra 已完整，适合并行推进

---

## 预估工作量

| Task | 预估时间 | 并行度 |
|------|----------|--------|
| Task 1: V2 数据注入 | 1h | A |
| Task 2: LLM 配置完善 | 2h | A |
| Task 3: LLM Service 连接 | 2h | B (依赖T2) |
| Task 4: ASR Provider | 3h | A |
| Task 5: OCR/Vision | 4h | A |
| Task 6: 性能统计 | 2h | B |
| Task 7: 场景验证 | 2h | C |
| **总计** | **~16h** | 并行可压缩到 8h |

---

*Plan created: 2026-04-24*
*Status: Ready for superpowers execution*
