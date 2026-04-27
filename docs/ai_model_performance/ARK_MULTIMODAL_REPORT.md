# Business AI 大模型能力真实测试报告

生成时间：由 `backend/scripts/evaluate_ark_multimodal.py` 生成 JSON 报告为准。

## 测试配置

- Provider：Volcano Ark / 火山方舟
- API：`https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- 模型：`doubao-seed-2-0-pro-260215`
- Key：通过环境变量注入，未写入仓库
- 测试脚本：`backend/scripts/evaluate_ark_multimodal.py`
- JSON 报告：`docs/ai_model_performance/ark_multimodal_report.json`
- 测试素材：脚本自动生成本地图片和音频
  - 图片：`/tmp/business_ai_model_eval/receipt.png`
  - 音频：`/tmp/business_ai_model_eval/tone.wav`

## 本轮真实测试结果

| 能力 | 结果 | 响应时间 | 置信度 | 说明 |
| --- | --- | ---: | ---: | --- |
| 文本 Chat | 成功 | 2901.26 ms | 0.99 | 方舟 chat/completions 连通正常 |
| OCR 采购单识别 | 成功 | 13047.18 ms | 0.99 | 成功识别采购单文字、商品、数量、单位、价格、总额 |
| Vision 商品识别 | 成功 | 13622.08 ms | 0.99 | 成功识别 M8 螺丝、锤子等候选商品 |
| ASR 语音转写 | 失败 | 1125.25 ms | - | 当前 chat/completions 返回：`audio input is not supported by this model` |

## OCR 结果摘要

识别出的商品明细：

1. `M8 SCREW`，数量 `20`，单位 `BOX`，单价 `8.5`
2. `HAMMER`，数量 `2`，单位 `PCS`，单价 `35.0`

识别总金额：`240.0`

原始文字预览：

```text
PURCHASE RECEIPT
M8 SCREW 20 BOX 8.50
HAMMER 2 PCS 35.00
TOTAL 240.00
```

## Vision 结果摘要

候选商品：

1. `M8螺丝`，置信度 `0.99`，规格提示 `20盒`
2. `锤子`，置信度 `0.99`，规格提示 `2件`

## ASR 当前结论

代码层已经接入 Ark/Doubao ASR Provider，使用 OpenAI-compatible `input_audio` content：

```json
{
  "type": "input_audio",
  "input_audio": {
    "data": "base64音频",
    "format": "wav"
  }
}
```

但本轮真实调用 `doubao-seed-2-0-pro-260215` 的 `chat/completions` 返回：

```text
audio input is not supported by this model
```

因此当前结论是：

- OCR：可用
- Vision：可用
- ASR：代码已接入，但当前模型 + 当前 chat/completions 端点未验证通过

如果你之前已经测试过该模型具备 ASR 能力，大概率使用的是以下其中一种不同接入方式：

1. 另一个方舟音频转写专用 API 端点
2. 另一个已开通音频输入能力的 Endpoint ID
3. 控制台/平台封装能力，而不是标准 `chat/completions` 的 `input_audio`
4. 使用视频输入 `video_url` 而不是音频输入 `input_audio`

需要补充确认的信息：

- 你之前 ASR 测试使用的完整 API URL
- `model` 参数是模型名还是 Endpoint ID
- 请求体里音频字段的格式

确认后，只需要调整 `ArkAsrProvider._build_user_content()` 或 ASR API 请求方法即可。

## 性能判断

当前 OCR/Vision 用同一个多模态大模型做结构化识别，优点是：

- 接入成本低
- 不需要单独 OCR 服务
- 可直接输出业务结构化 JSON
- 适合早期 MVP 快速验证

但缺点也明显：

- OCR/Vision 延迟约 13 秒，偏慢
- 成本会高于专用 OCR
- 输出置信度来自模型自评，不是传统 OCR 字符级置信度
- 对复杂票据需要增加二次校验

建议后续产品策略：

1. MVP 阶段：继续用 Doubao 多模态统一实现 OCR/Vision。
2. 试运行阶段：增加结构化校验，比如金额合计、数量单价校验、商品库匹配校验。
3. 商业化阶段：如果票据量变大，可以接专用 OCR 做第一层识别，再由大模型做业务语义整理。
4. ASR 阶段：确认火山方舟音频正确端点后再切生产；否则先接入火山语音识别专用服务。
