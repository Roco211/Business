# 腾讯 COS 对象存储接入说明

本文档用于 Business 项目生产环境接入腾讯云对象存储 COS。COS 按 S3-compatible 协议接入，不需要在代码中保存任何真实密钥。

## 1. 支持的 provider 名称

推荐使用通用名称：

```bash
OBJECT_STORAGE_PROVIDER=s3-compatible
```

也支持腾讯 COS 别名：

```bash
OBJECT_STORAGE_PROVIDER=cos
# 或 tencent-cos / tencent_cos / qcloud-cos / qcloud_cos
```

这些别名都会归一化为 S3-compatible provider。

## 2. 推荐生产配置

请通过部署平台 secret、服务器环境变量或本地未跟踪 `.env` 注入。不要提交真实值。

```bash
APP_ENV=production
APP_RUNTIME_MODE=production

OBJECT_STORAGE_PROVIDER=cos
COS_BUCKET=business-prod-media-1250000000
COS_REGION=ap-guangzhou
COS_ENDPOINT_URL=https://cos.ap-guangzhou.myqcloud.com
COS_SECRET_ID=[REDACTED]
COS_SECRET_KEY=[REDACTED]
COS_PUBLIC_BASE_URL=https://business-prod-media-1250000000.cos.ap-guangzhou.myqcloud.com
OBJECT_STORAGE_PRESIGN_TTL_SECONDS=600
```

也可以使用通用变量名：

```bash
OBJECT_STORAGE_PROVIDER=s3-compatible
OBJECT_STORAGE_BUCKET=business-prod-media-1250000000
OBJECT_STORAGE_REGION=ap-guangzhou
OBJECT_STORAGE_ENDPOINT_URL=https://cos.ap-guangzhou.myqcloud.com
OBJECT_STORAGE_ACCESS_KEY_ID=[REDACTED]
OBJECT_STORAGE_SECRET_ACCESS_KEY=[REDACTED]
OBJECT_STORAGE_PUBLIC_BASE_URL=https://business-prod-media-1250000000.cos.ap-guangzhou.myqcloud.com
OBJECT_STORAGE_PRESIGN_TTL_SECONDS=600
```

## 3. 腾讯 COS endpoint 格式

常见格式：

```text
https://cos.<region>.myqcloud.com
```

例如：

```text
https://cos.ap-guangzhou.myqcloud.com
https://cos.ap-shanghai.myqcloud.com
https://cos.ap-beijing.myqcloud.com
```

Bucket 通常带 APPID，例如：

```text
business-prod-media-1250000000
```

公开访问域名可使用 COS 默认域名或 CDN 域名：

```text
https://business-prod-media-1250000000.cos.ap-guangzhou.myqcloud.com
https://media.example.com
```

## 4. 非破坏性验收建议

在已注入真实 COS secret 后执行：

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m pytest backend/tests/test_object_storage_provider.py backend/tests/test_v2_media_ai_platform.py -q
bash backend/scripts/run_real_provider_preflight.sh
```

如果要做真实上传验收，应使用临时测试 object key，上传后读取校验 SHA256，最后删除测试对象。验收日志不得打印 SecretId、SecretKey、签名 URL 完整内容或数据库连接串。

## 5. 生产门禁

生产环境中：

- `OBJECT_STORAGE_PROVIDER=mock` 会被 readiness / mock guardrails 标记为违规。
- COS/S3-compatible 必须配置 bucket、region、endpoint、access key、secret key。
- local-demo/test 仍可使用 mock object storage，但不能作为商业化验收依据。
