# Phase K1 RBAC 权限角色补强计划

日期：2026-04-26
分支：`hermes/ai-native-saas-rewrite`

## 背景

J6 已经提供商用试运行验收入口。进入 Phase K 后，第一优先级是正式商用前权限补强：不能让所有登录账号都具备老板级操作能力。

当前系统已有 `V2TenantMembership.role_key`、`V2ShopAccess.access_level`、`V2ContextSession.permission_snapshot`，但 context 选择时权限快照仍是固定 `inventory:read` + `conversation:write`，关键业务路由也还没有系统化权限保护。

## 目标

实现第一版 RBAC：

1. 定义四类角色：
   - `owner`：老板，全权限。
   - `manager`：店长，大部分经营操作权限，但仍通过显式权限控制。
   - `clerk`：店员，可做销售、客户、库存读取和 AI草稿，但不能看财务、导出、采购、审批。
   - `finance`：财务，可看财务、销售/采购只读、导出，不能改库存、创建订单、审批 AI任务。

2. context select 时生成真实 permission snapshot。
3. 后端关键 API 按权限拦截：
   - 库存写：`inventory:write`
   - 销售写：`sales:write`
   - 采购写：`purchasing:write`
   - 客户写：`customers:write`
   - 财务读：`finance:read`
   - CSV导出：`exports:read`
   - AI草稿/聊天：`ai:write`
   - confirmation 审批/拒绝：`confirmations:approve`
4. H5 根据 `roleKey` / `permissions` 展示权限说明，并隐藏/禁用无权限操作。

## 非目标

- 本阶段不做用户邀请、成员管理 UI。
- 本阶段不做权限矩阵数据库表，先用代码内稳定矩阵。
- 本阶段不迁移历史 context session，重新选择门店即可获得新快照。
- 本阶段不做字段级权限。

## TDD 验收

先新增失败测试：

1. `clerk` context select 返回 `sales:write`、`ai:write`，但不包含 `finance:read`、`exports:read`、`confirmations:approve`。
2. `finance` context select 返回 `finance:read`、`exports:read`，但不包含 `inventory:write`、`sales:write`、`confirmations:approve`。
3. `clerk` 访问 `/api/v2/finance/summary` 返回 403 `permission_denied`。
4. `finance` 调用 `POST /api/v2/inventory/items` 返回 403 `permission_denied`。
5. `owner` 可正常访问财务摘要并创建商品。

## 实施步骤

1. 增加 RBAC 服务模块或在 identity service 中定义权限矩阵。
2. 修改 `select_v2_context(...)`，将 `role_key` 映射为权限列表写入 `permission_snapshot`。
3. 在 `v2_context` dependency 增加 `V2ForbiddenError`、`has_permission(...)`、`require_v2_permission(...)`。
4. 在关键路由增加权限检查。
5. H5 保存 context 的 `roleKey` / `permissions`，增加权限说明与操作级禁用。
6. 执行后端回归、H5 build、Docker热更新、浏览器验收。

## 安全边界

- 多租户/门店隔离仍然优先，权限只在当前 context 上生效。
- 无权限返回 403，不泄露其他租户/门店数据。
- AI 仍然 confirmation-first，RBAC 不允许 AI 绕过审批。
- 任何 token / context token 不输出。
