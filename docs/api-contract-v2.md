# V2 API 契约文档

> 版本: v2.0
> 更新时间: 2026-04-24
> 后端地址: http://localhost:8001

---

## 认证方式

所有 V2 API（除 `/health` 和 `/auth/login` 外）需要双重认证：

### 1. Bearer Token（身份认证）
```
Authorization: Bearer <access_token>
```

通过 `/auth/login` 获取，支持两种方式：

**邮箱登录**
```json
POST /api/v2/auth/login
{
  "auth_method": "email_password",
  "email": "demo@aistoremanager.com",
  "password": "demo123"
}
```

**手机验证码登录**
```json
POST /api/v2/auth/login
{
  "auth_method": "phone_code",
  "phone_number": "13800138000",
  "verification_code": "888888"
}
```

### 2. Context Token（店铺上下文）
```
X-Context-Token: <context_session_id>
```

通过 `/context/select` 获取：
```json
POST /api/v2/context/select
Headers: Authorization: Bearer <token>
Body: {"tenant_id": "xxx", "shop_id": "xxx"}
```

---

## 核心 API 列表

### 1. 认证与上下文

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/v2/auth/login` | 无需 | 登录获取 token |
| POST | `/api/v2/auth/logout` | Bearer | 退出登录 |
| POST | `/api/v2/auth/refresh` | Bearer | 刷新 token |
| GET | `/api/v2/me` | Bearer | 当前用户信息 |
| GET | `/api/v2/me/tenants` | Bearer | 租户列表 |
| GET | `/api/v2/tenants/{tid}/shops` | Bearer | 店铺列表 |
| POST | `/api/v2/context/select` | Bearer | 选择店铺上下文 |
| GET | `/api/v2/context/current` | Bearer + Context | 当前上下文 |

### 2. 库存管理

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/v2/inventory/stock` | Bearer + Context | 库存快照列表 |
| GET | `/api/v2/inventory/items` | Bearer + Context | 商品列表 |
| GET | `/api/v2/inventory/catalog` | Bearer + Context | 商品目录 |
| GET | `/api/v2/inventory/events` | Bearer + Context | 库存事件 |
| GET | `/api/v2/ledger/events` | Bearer + Context | 库存流水 |
| POST | `/api/v2/inventory/corrections` | Bearer + Context | 库存修正 |
| POST | `/api/v2/inventory/stock-out` | Bearer + Context | 出库 |

### 3. AI 聊天

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/v2/chat` | Bearer + Context | 标准聊天 |
| POST | `/api/v2/chat/stream` | Bearer + Context | **SSE 流式聊天** |

### 4. 预警

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/v2/alerts` | Bearer + Context | 预警列表 |
| POST | `/api/v2/alerts/{id}/ack` | Bearer + Context | 确认预警 |

### 5. 多媒体（Mock 模式）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/v2/voice/stock-query` | Bearer + Context | 语音查库存 |
| POST | `/api/v2/voice/stock-in` | Bearer + Context | 语音入库 |
| POST | `/api/v2/photo/stock-query` | Bearer + Context | 图片查库存 |
| POST | `/api/v2/photo/stock-in` | Bearer + Context | 图片入库 |
| POST | `/api/v2/documents/receipt-extractions` | Bearer + Context | 票据识别 |

---

## SSE 流式聊天规范

### 请求
```bash
POST /api/v2/chat/stream
Headers:
  Authorization: Bearer <token>
  X-Context-Token: <context_token>
  Content-Type: application/json

Body:
{
  "message": "锤子还有多少个？"
}
```

### 响应格式
```
Content-Type: text/event-stream
```

### 事件序列

```
event: intent
data: {
  "intent_type": "stock_query",
  "item_name": "锤子",
  "quantity": null,
  "confidence": 0.8,
  "employee": {
    "name": "库存守护员",
    "color": "#10B981",
    "badge": "库存"
  }
}

event: inventory
data: {
  "item_id": "xxx",
  "item_name": "高精度锤子",
  "sku": "TOOL-HAMMER-001",
  "quantity": 15.0,
  "unit": "把",
  "threshold": 5.0,
  "employee": { "name": "库存守护员", ... }
}

event: token
data: {"token": "高精"}

event: token
data: {"token": "度锤"}

event: token
data: {"token": "子目"}

...

event: done
data: {
  "message_id": "xxx",
  "employee": { "name": "库存守护员", ... }
}
```

### AI 员工角色映射

| Intent | 员工名称 | 颜色 | Badge |
|--------|---------|------|-------|
| stock_query | 库存守护员 | #10B981 | 库存 |
| stock_in | 库存守护员 | #10B981 | 入库 |
| stock_out | 库存守护员 | #10B981 | 出库 |
| price_query | 价格参谋 | #F59E0B | 价格 |
| sales_query | 销售分析员 | #3B82F6 | 销售 |
| revenue_query | 营业数据员 | #8B5CF6 | 营收 |
| alert_query | 库存守护员 | #EF4444 | 预警 |
| unknown | AI参谋 | #6B7280 | 助手 |

---

## 通用响应格式

### 成功响应
```json
{
  "data": { ... }
}
```

### 错误响应
```json
{
  "error": {
    "code": "error_code",
    "message": "错误描述"
  }
}
```

---

## 前端 SDK 示例

### 初始化
```typescript
const API_BASE = 'http://localhost:8001/api/v2';

class AISMClient {
  private token: string = '';
  private contextToken: string = '';

  async login(email: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auth_method: 'email_password', email, password }),
    });
    const data = await res.json();
    this.token = data.data.access_token;
    return data;
  }

  async selectContext(tenantId: string, shopId: string) {
    const res = await fetch(`${API_BASE}/context/select`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tenant_id: tenantId, shop_id: shopId }),
    });
    const data = await res.json();
    this.contextToken = data.data.context_session_id;
    return data;
  }

  async chat(message: string) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'X-Context-Token': this.contextToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });
    return res.json();
  }

  async *chatStream(message: string) {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'X-Context-Token': this.contextToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          const eventType = line.slice(7);
          // Next line should be data:
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          yield { event: eventType, data };
        }
      }
    }
  }
}
```

---

## 测试环境

- **后端地址**: http://localhost:8001
- **演示账号**: demo@aistoremanager.com / demo123
- **演示验证码**: 888888（手机号 13800138000）
- **数据库**: SQLite (aism-dev.db)

---

*Generated: 2026-04-24*
