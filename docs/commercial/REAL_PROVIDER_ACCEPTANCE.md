# 真实 Provider 商业化验收清单

本文档记录 Business 项目从 local-demo 走向商业化生产环境时，如何在不泄露密钥的前提下验收真实第三方 provider。

## 当前验收范围

本轮验收包含：

- DeepSeek Main Agent 配置检查
- Ark/Doubao OCR 配置检查
- Ark/Doubao Vision 配置检查
- 客户端 ASR 文本模式检查
- 腾讯 COS / S3-compatible 对象存储预签名检查
- Production mock guardrails
- 后端关键测试
- H5 build
- 密钥扫描

本轮明确暂缓：

- 真实短信发送验收

原因：暂时没有可用短信服务商、签名、模板 ID、测试手机号与凭证。代码仍保留生产门禁，production 不允许 888888 演示验证码；总验收用 `SMS_REAL_PREFLIGHT=0` 把短信标记为 known deferred。

## 环境变量

所有真实密钥必须通过部署 secret 或本地未跟踪 `.env` 注入，不能提交到 GitHub。

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

OBJECT_STORAGE_PROVIDER=cos
COS_BUCKET=your-bucket-1250000000
COS_REGION=ap-guangzhou
COS_ENDPOINT_URL=https://cos.ap-guangzhou.myqcloud.com
COS_SECRET_ID=[REDACTED]
COS_SECRET_KEY=[REDACTED]
COS_PUBLIC_BASE_URL=https://your-bucket-1250000000.cos.ap-guangzhou.myqcloud.com
OBJECT_STORAGE_PRESIGN_TTL_SECONDS=600

# 本轮短信真实发送暂缓
SMS_REAL_PREFLIGHT=0
SMS_PROVIDER=demo
```

说明：

- `SMS_REAL_PREFLIGHT=0` 只表示当前验收不执行真实短信发送，不表示 production 可以使用 demo 短信。
- `production_mock_violations()` 仍会把 `SMS_PROVIDER=demo/mock` 视为生产违规；总验收脚本会在短信暂缓时只过滤该已知项。
- 腾讯 COS 必须使用 virtual-hosted-style；代码已在 provider 为 `cos` 或 endpoint 包含 `myqcloud.com` 时自动处理。
- 预签名 URL 不允许打印到日志。

## 总验收命令

```bash
cd /root/business-clone
python3 -m compileall -q backend/app backend/scripts
PYTHONPATH=backend python3 -m pytest backend/tests -q
cd apps/h5 && npm run build
cd /root/business-clone && SMS_REAL_PREFLIGHT=0 bash backend/scripts/run_real_provider_preflight.sh
```

## 可选真实模型健康检查

如果已经注入真实 Ark Key，并希望做 OCR/Vision 网络请求验收：

```bash
cd /root/business-clone
PYTHONPATH=backend python3 backend/scripts/evaluate_ark_multimodal.py --repeats 1
```

要求：

- 输出报告不能包含 API Key。
- 若模型调用失败，只记录错误类型、provider 名称、耗时和是否 fallback；不能回退 mock 后宣称生产可用。

## 腾讯 COS 已验收结果

已用本地未跟踪 `.env` 完成：

- 文本对象预签名上传、HEAD、SHA256 校验、删除。
- 随机下载 3 张图片上传 COS，PUT 状态 200，HEAD/大小/SHA256 校验成功。

当前限制：

- COS public URL 直连返回 403，说明 bucket/object 当前不是公有读。
- 如前端要直接展示图片，需要开启公有读、接 CDN，或改为后端签名下载 URL。

## 密钥扫描

```bash
cd /root/business-clone
python3 - <<'PY'
from pathlib import Path
import re
patterns = [
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'AKLT[A-Za-z0-9_-]{20,}'),
    re.compile(r'^(?:[A-Z0-9_]*(?:SECRET|PASSWORD|API_KEY|TOKEN(?!S))[A-Z0-9_]*)\s*=\s*([^\s#]+)'),
]
violations = []
for path in Path('.').rglob('*'):
    if path.is_dir() or '.git' in path.parts or 'node_modules' in path.parts:
        continue
    if path.name == '.env' or path.suffix in {'.db', '.sqlite', '.sqlite3'}:
        continue
    try:
        lines = path.read_text(errors='ignore').splitlines()
    except Exception:
        continue
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        for pattern in patterns:
            for match in pattern.finditer(stripped):
                value = match.group(0)
                lowered = value.lower()
                assigned = match.group(1).strip().strip('"').strip("'") if match.lastindex else value
                if (
                    '[redacted]' in lowered
                    or 'example' in lowered
                    or 'placeholder' in lowered
                    or 'configured' in lowered
                    or 'mock_token' in lowered
                    or 'access_token' in lowered
                    or 'opaque' in lowered
                    or '...' in lowered
                    or '*' in assigned
                    or not assigned.strip()
                ):
                    continue
                violations.append((str(path), value[:80]))
if violations:
    for item in violations[:20]:
        print(item)
    raise SystemExit('SECRET_SCAN_FAILED')
print('SECRET_SCAN_OK')
PY
```

## 通过标准

本轮不含短信真实发送时，通过标准为：

- `SMS_REAL_PREFLIGHT=0 bash backend/scripts/run_real_provider_preflight.sh` 通过。
- 后端全量测试通过。
- H5 build 通过。
- 密钥扫描通过。
- GitHub CI 不再引用已删除的 `backend/tests/test_v2_chat_confirmation_first.py`。
- `.env`、本地数据库、`dashboard.jpg` 不提交。

短信服务具备后，再把 `SMS_REAL_PREFLIGHT=1`，配置真实短信 provider，并补一次真实测试手机号验证码验收。
