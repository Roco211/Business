# Phase 8 实施计划：火山引擎 LLM 集成

## 概述

Phase 7已完成功能场景API骨架，但所有AI能力(ASR/OCR/Vision/LLM)仍处于stub/mock状态。**Phase 8的核心任务是将这些stub替换为真正的火山引擎大模型能力**。

## 当前状态

| 能力 | 当前状态 | Phase 8目标 |
|------|---------|------------|
| ASR (语音转文字) | mock/stub | Volcano Engine ASR API |
| OCR (票据识别) | mock/stub | Volcano Engine OCR API |
| Vision (图片识别) | mock/stub | Volcano Engine Vision API |
| LLM (意图识别/回复生成) | mock/stub | Volcano Engine LLM API |
| Response Streaming | stub | 真正SSE流式 |

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│  Service Layer (v2_voice.py, v2_photo.py, v2_receipt...)   │
├─────────────────────────────────────────────────────────────┤
│  Provider Gateway (asr_gateway.py, ocr_gateway.py...)       │
├─────────────────────────────────────────────────────────────┤
│  Real Provider (asr_real_provider.py, ocr_real_provider...)│
│  ├── VolcanoEngine ASR Provider                            │
│  ├── VolcanoEngine OCR Provider                            │
│  ├── VolcanoEngine Vision Provider                         │
│  └── VolcanoEngine LLM Provider  ← 新增                    │
├─────────────────────────────────────────────────────────────┤
│  Config (config.py) - 环境变量配置                          │
└─────────────────────────────────────────────────────────────┘
```

## Phase 8 任务清单

### P0 - 基础设施 (8h)

- [ ] **T1**: 创建 `llm_provider.py` - Volcano LLM Provider基类
- [ ] **T2**: 创建 `llm_real_provider.py` - 真正的火山引擎LLM调用
- [ ] **T3**: 在 `config.py` 添加LLM相关配置
- [ ] **T4**: 创建性能统计追踪 (`llm_call_logs` 扩展)

### P0 - ASR集成 (4h)

- [ ] **T5**: 配置火山引擎ASR API (audio/quick-digest模型)
- [ ] **T6**: 在 `asr_real_provider.py` 接入火山引擎
- [ ] **T7**: `v2_voice.py` 使用真正的ASR Provider
- [ ] **T8**: CLI测试语音转文字功能

### P0 - OCR集成 (4h)

- [ ] **T9**: 配置火山引擎OCR API (receipt模型)
- [ ] **T10**: 在 `ocr_real_provider.py` 接入火山引擎
- [ ] **T11**: `v2_receipt_documents.py` 使用真正的OCR
- [ ] **T12**: CLI测试票据识别功能

### P0 - Vision集成 (4h)

- [ ] **T13**: 配置火山引擎Vision API
- [ ] **T14**: 在 `vision_real_provider.py` 接入火山引擎
- [ ] **T15**: `v2_photo.py` 使用真正的Vision Provider
- [ ] **T16**: CLI测试图片识别功能

### P0 - LLM Chat集成 (6h)

- [ ] **T17**: 创建 `v2_llm.py` 服务层
- [ ] **T18**: 重构 `process_voice_stock_query` 使用真正LLM
- [ ] **T19**: 流式响应优化 (首包延迟<2s)
- [ ] **T20**: 会话上下文管理 (session-based history)

### P1 - 性能优化 (4h)

- [ ] **T21**: Prompt优化 (从150 tokens压缩到30 tokens)
- [ ] **T22**: History限制 (从20 messages限制到2)
- [ ] **T23**: HTTP连接池复用
- [ ] **T24**: Latency指标采集和告警

## 配置要求

环境变量配置:
```bash
# ASR Configuration
ASR_PROVIDER=volcano
ASR_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/audio/quick-digest
ASR_PROVIDER_API_KEY=xxx
ASR_PROVIDER_MODEL=ep-xxxxxxxx

# OCR Configuration
OCR_PROVIDER=volcano
OCR_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/ocr/invoice
OCR_PROVIDER_API_KEY=xxx
OCR_PROVIDER_MODEL=ep-xxxxxxxx

# Vision Configuration
VISION_PROVIDER=volcano
VISION_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
VISION_PROVIDER_API_KEY=xxx
VISION_PROVIDER_MODEL=ep-xxxxxxxx

# LLM Configuration
LLM_PROVIDER=volcano
LLM_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
LLM_PROVIDER_API_KEY=xxx
LLM_PROVIDER_MODEL=ep-20260416043519-v4vzq
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.7
```

## 性能基准

| 指标 | 当前 (Stub) | 目标 (Volcano) |
|------|------------|---------------|
| ASR First Token | <100ms | <2s |
| OCR Process Time | <100ms | <3s |
| Vision Response | <100ms | <3s |
| LLM First Token | <100ms | <5s |
| LLM Full Response | <100ms | <8s |

## 实施顺序

### 阶段1: LLM Provider基础设施
1. 创建 `llm_real_provider.py`
2. 在 `config.py` 添加LLM配置
3. 基础性能追踪

### 阶段2: ASR/OCR/Vision接入
1. ASR Provider配置和接入
2. OCR Provider配置和接入
3. Vision Provider配置和接入

### 阶段3: 业务场景真LLM化
1. `v2_voice.py` - 真实ASR + LLM意图识别
2. `v2_photo.py` - 真实Vision + LLM分析
3. `v2_receipt_documents.py` - 真实OCR + LLM结构化

### 阶段4: 性能调优
1. Prompt压缩
2. History截断
3. Connection pooling
4. Latency指标

## 验证步骤

```bash
# 1. 测试ASR
curl -X POST http://localhost:8001/api/v2/voice/stock-query \
  -F "audio=@test_audio.webm" \
  -F "shop_id=shop_test"

# 2. 测试OCR
curl -X POST http://localhost:8001/api/v2/receipt-documents \
  -F "media=@receipt.jpg" \
  -F "shop_id=shop_test"

# 3. 测试Vision
curl -X POST http://localhost:8001/api/v2/photo/stock-query \
  -F "photo=@product.jpg" \
  -F "shop_id=shop_test"

# 4. 性能基准测试
python3 scripts/benchmark_llm_latency.py
```

##预估工作量

| 任务 | 预估时间 |
|------|---------|
| LLM Provider基础设施 | 8h |
| ASR集成 | 4h |
| OCR集成 | 4h |
| Vision集成 | 4h |
| LLM Chat集成 | 6h |
| 性能优化 | 4h |
| **总计** | **~30h** |

## 下一步行动

**选项A**: 并行子代理 - 同时启动ASR/OCR/Vision/LLM四个子代理并行开发
**选项B**: MVP单点突破 - 先完成LLM Provider基础设施，验证模式后复制到ASR/OCR/Vision
**选项C**: 业务场景驱动 - 先完成Voice场景端到端真LLM化，验证用户体验后铺开

**推荐: 选项B** - 先建立LLM Provider标准，然后其他provider遵循相同pattern。
