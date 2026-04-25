# Business H5 商业闭环页面接入报告

生成时间：2026-04-25 19:53:24 CST

## 结论

本轮在已完成 G1-G5 后端商业闭环基础上，继续把采购/供应商、客户复购、财务流水、AI销售单草稿接入 PC/H5 管理台。

新增页面入口：

- 采购单
- 客户复购
- 财务流水
- AI助手中的“AI生成销售单草稿”

同时为 H5 页面补齐后端列表接口，保证页面刷新后能看到真实后端数据，而不是只依赖创建后的本地状态。

## 后端补充

新增/补充 API：

- `GET /api/v2/purchasing/suppliers`
- `GET /api/v2/purchasing/orders`
- `GET /api/v2/customers`

这些接口均要求：

- `Authorization: Bearer <accessToken>`
- `X-Context-Token: <contextToken>`

并严格按当前执行上下文过滤：

- `tenant_id`
- `shop_id`

## H5 新增能力

### 采购单页面

新增导航：`采购单`

能力：

- 新增供应商
- 查看供应商列表
- 基于当前库存商品创建采购入库单
- 查看采购单列表
- 创建采购单后后端自动入库并写财务采购支出流水

### 客户复购页面

新增导航：`客户复购`

能力：

- 新增客户
- 查看客户列表
- 查看客户数量
- 查看匹配订单数
- 查看客户复购分析表

说明：

- 当前复购分析按销售单 `customer_name` 与客户姓名匹配。
- 后续建议升级为销售单 `customer_id` 外键。

### 财务流水页面

新增导航：`财务流水`

能力：

- 查看总收入
- 查看总支出
- 查看净现金流
- 查看财务流水列表

数据来源：

- 销售收入
- 采购支出
- 销售取消退款
- 销售退货退款

### AI销售单草稿入口

AI助手页新增：`AI生成销售单草稿`

能力：

- 输入自然语言销售描述
- 调用 `POST /api/v2/sales/order-drafts/from-text`
- 生成 pending confirmation
- 提醒用户到任务中心审批
- 审批后才会正式创建销售单并扣库存

安全边界：

- AI 不直接落账
- AI 只生成待确认草稿
- 用户批准后才执行真实销售单创建

## 商业路线页更新

已把路线状态更新为：

- F1 销售单/订单：已开放
- F2 采购/供应商：已开放
- F3 客户档案：已开放
- F4 财务流水：已开放
- F5 营销/售后：后续开放

## 验收结果

### H5 build

命令：

```bash
npm run build
```

结果：

- TypeScript build passed
- Vite build passed

### Focused 后端回归

命令：

```bash
PYTHONPATH=backend pytest backend/tests/test_v2_commercial_modules_http_flow.py -q
```

结果：

- `2 passed in 5.64s`

### 默认 preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `36 passed in 64.57s`
- H5 build passed
- readiness：`overall_status=ready`
- readiness：`ready_count=16`
- readiness：`missing_count=0`

### 完整 Docker preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `36 passed in 64.56s`
- H5 build passed
- Docker build passed
- Alembic version：`20260425_02`
- Table count：`48`
- Phase8：`8/8 passed`
- Phase9：`5/5 passed`
- Phase10：`6/6 passed`

### 浏览器冒烟

访问：

- `http://127.0.0.1:8001/`

验证：

- 演示登录成功
- 新导航存在：采购单、客户复购、财务流水
- AI助手页存在：AI生成销售单草稿
- Console JS error：0

## 本轮主要文件

- `apps/h5/src/App.tsx`
- `apps/h5/src/api.ts`
- `apps/h5/src/types.ts`
- `backend/app/api/v2/routes/commercial.py`
- `backend/app/services/v2_commercial.py`
- `backend/tests/test_v2_commercial_modules_http_flow.py`

## 后续建议

1. 销售单详情/取消/退货做成 H5 交互按钮，不只停留在 API。
2. 采购单状态流从“创建即收货”升级为：草稿、待收货、部分收货、已收货、取消。
3. 客户档案升级为销售单 `customer_id` 强关联。
4. 财务模块增加日期筛选、支付方式汇总、应收应付。
5. AI销售单草稿解析升级为结构化 LLM，但继续保持 confirmation-first。
