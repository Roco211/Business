# 13. Provider 决策与替换策略

本文件解决的问题是：

**在正式接入真实 ASR / OCR / 识图 / 推理能力前，当前项目到底用什么 provider 策略开工。**

---

## 1. 当前阶段的总决策

当前项目统一采用：

- **基础设施真实**
- **AI 能力 mock-first**

也就是：

- MySQL 真实
- Redis 真实
- Celery 真实
- MinIO 真实
- WebSocket 真实
- ASR / OCR / 识图 / 自由推理暂时 mock

这样做的目的：

- 先验证系统骨架
- 先验证业务状态机
- 先验证确认链和账本
- 避免早期被供应商波动绑架

---

## 2. 当前阶段的 provider 矩阵

| 能力 | 当前阶段决策 | 进入试点前再决定 |
|---|---|---|
| Auth | `MockAuthProvider` | 正式账号体系 |
| Object Storage | `MinIO` | S3 兼容云存储 |
| Queue | `Celery + Redis` | 保持不变或做运维升级 |
| Router | `RuleFirstRouter` | 可选 LLM Router |
| Summarizer | `TemplateSummarizer` | 可选 LLM Summarizer |
| ASR | `MockAsrProvider` | 单一真实 ASR 供应商 |
| OCR | `MockOcrProvider` | 单一真实 OCR 供应商 |
| Vision | `MockVisionProvider` | 单一真实识图供应商 |

关键原则：

- 当前阶段每类能力只保留一个接口
- 当前阶段不做多 provider 并行竞争
- 进入试点前再选择真实 vendor

---

## 3. 为什么当前不直接拍死真实供应商

当前最重要的风险不是“到底接哪家更准”，而是：

- runtime 是否稳定
- task state 是否清楚
- confirmation 是否可用
- inventory event 和 audit log 是否正确

如果这些还没稳，就算真实 provider 接进来，也只是在一个不稳的系统里放入更昂贵的不确定性。

所以当前阶段的决策是：

**先把 provider 变成可插拔能力，再考虑哪家最适合上线。**

---

## 4. 当前阶段推荐的 provider 接口

### 4.1 ASR

```py
class AsrProvider(Protocol):
    async def transcribe(self, media_url: str, locale: str) -> dict: ...
```

返回至少包含：

- `text`
- `confidence`
- `language`
- `raw_provider_payload`

### 4.2 OCR

```py
class OcrProvider(Protocol):
    async def extract_purchase_receipt(self, media_url: str) -> dict: ...
```

返回至少包含：

- `fields`
- `low_confidence_fields`
- `raw_text`
- `raw_provider_payload`

### 4.3 Vision

```py
class VisionProvider(Protocol):
    async def recognize_product(self, media_url: str, shop_id: str) -> dict: ...
```

返回至少包含：

- `candidates`
- `top_confidence`
- `raw_provider_payload`

### 4.4 Router / Summarizer

```py
class RouterProvider(Protocol):
    async def route(self, text: str, input_kind: str) -> dict: ...


class SummarizerProvider(Protocol):
    async def summarize_task(self, task_payload: dict) -> str: ...
```

当前阶段建议：

- Router 先规则优先
- Summarizer 先模板优先

不要求一开始就接 LLM。

---

## 5. Mock provider 的实现要求

Mock 不是随便写个假返回值。

当前阶段 mock provider 必须能稳定覆盖下面几类场景：

- 正常成功
- 低置信返回
- 明确失败
- 耗时较长
- 新商品未命中
- OCR 部分字段模糊

建议通过 fixture 驱动：

```text
backend/tests/fixtures/providers/
  asr/
  ocr/
  vision/
```

每个 fixture 至少支持：

- `success`
- `low_confidence`
- `failure`

---

## 6. 当前阶段对真实 provider 的约束

进入真实 provider 接入前，要求先满足下面约束：

- 只能选一个主 provider，不做双供应商并行
- 必须能返回置信度或低置信线索
- 必须能映射到内部错误码
- 必须能在超时或失败时提供可恢复错误
- 不允许让 provider payload 直接穿透到前端模型

也就是说：

- 外部 provider 是实现细节
- 内部 contract 才是系统真相

---

## 7. 当前阶段的错误码映射要求

所有 provider 异常最终都要收敛到内部错误码，例如：

- `asr_failed`
- `ocr_failed`
- `recognition_low_confidence`
- `media_upload_failed`

当前阶段不允许：

- 前端直接显示供应商原始错误
- task state 里混入供应商私有状态名

---

## 8. 切换到真实 provider 的时机

只有满足下面条件，才建议从 mock 切到真实 provider：

- P0 语音入库闭环已跑通
- 确认链已跑通
- `InventoryEvent` 和 `AuditLog` 已稳定
- WebSocket 回写已稳定
- 基础测试用例已经覆盖主流程

否则不建议切。

---

## 9. 当前阶段明确不做的 provider 复杂度

- 多供应商自动竞速
- 供应商级 fallback tree
- 每个员工绑定不同模型
- 插件市场式 provider 自动注册
- shell / 文件系统 / 任意命令型工具接入业务后端

---

## 10. 当前阶段最终结论

本项目在正式施工阶段的 provider 策略可以总结成一句话：

**先把 provider 做成稳定接口和 deterministic mock，让系统骨架可施工；真实供应商选择推迟到试点准备阶段。**
