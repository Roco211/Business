## Phase 8 并行任务委派

### Task 1: ✅ 修复V2数据注入脚本
- 状态: 已完成
- 文件: `backend/scripts/bootstrap_v2_trial_data.py`
- 结果: V2数据注入成功，创建了演示账户/租户/店铺/库存数据

### Task 2: ✅ 数据验证
- 验证V2Account创建: demo@aistoremanager.com / demo123
- 验证Shop ID: 19bd221b254746c6a4a7da04
- 验证低库存警报商品: 电动螺丝刀 (qty=3 < threshold=5)

### Task 3: LLM Service层连接 (等待Provider完成后进行)
- 依赖: Task 4/5 完成

### Task 4: ASR Provider接入火山引擎 (并行)
- 子代理: [委派中]
- 目标: `backend/app/services/v2_asr_real_provider.py`
- 需求: 火山ASR API (audio/quick-digest模型)
- 配置: .env ASR配置

### Task 5: OCR/Vision Provider接入 (并行)
- 子代理: [委派中]
- 目标: `backend/app/services/v2_ocr_real_provider.py`
- 目标: `backend/app/services/v2_vision_real_provider.py`
- 需求: 火山OCR + Vision API

### Task 6: 性能统计与追踪 (并行)
- 子代理: [委派中]
- 目标: `backend/app/services/v2_llm.py` 添加metrics
- 目标: `backend/app/services/v2_metrics.py` 新模块
- 需求: Latency/Throughput追踪
