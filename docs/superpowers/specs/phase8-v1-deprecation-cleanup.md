# Spec: Phase 8 v1 Deprecation Cleanup

## Overview

V1 退场 - 清理 legacy 代码，标记 v1 为 deprecated，保留 runtime 但不再维护。

## Goals

1. 识别所有 v1 代码路径
2. 移除 default shop bootstrap
3. 移除 default owner bootstrap
4. 移除 shop=tenant 假设
5. 标记 v1 为 deprecated
6. 保留 minimal v1 runtime（启动但不新建实例）

## Inventory

### V1 Models

| File | Status | Action |
|------|--------|--------|
| `shop.py` | ✅ Used | Keep, mark deprecated |
| `owner_account.py` | ✅ Used | Keep, mark deprecated |
| `shop_membership.py` | ✅ Used | Keep, mark deprecated |
| `inventory_item.py` | ✅ Used | Keep, mark deprecated |
| `inventory_event.py` | ✅ Used | Keep, mark deprecated |

### V1 Services

| File | Status | Action |
|------|--------|--------|
| `shop.py` | ⚠️ Partial | Mark deprecated, keep read-only |
| `auth.py` | ✅ Active | Keep, used by v2 |
| `owner.py` | ⚠️ Partial | Remove bootstrap, keep lookup |

### V2 Models (Target)

| File | Status |
|------|--------|
| `v2_identity.py` | ✅ V2Transition, V2Account, V2Tenant, V2Shop |
| `v2_shop.py` | ✅ Shop V2 implementation |
| `v2_inventory.py` | ✅ V2InventoryItem, V2InventoryStockSnapshot, V2InventoryLedgerEvent |

## Cleanup Tasks

### Task 1: Remove Default Shop Bootstrap

**Location:** `backend/app/services/shop.py`

```python
# REMOVE this from initialization:
def ensure_default_shop():
    """创建默认商店（如果存在）"
    Remo this from app startup
```

- [ ] 移除 `ensure_default_shop()` 调用
- [ ] 保留函数用于向后兼容
- [ ] 添加 deprecation 警告

### Task 2: Remove Owner Auto-Creation

**Location:** `backend/app/services/owner.py`

```python
# REMOVE auto-creation logic
- [ ] 移除首次登录自动创建 Owner
- [ ] 保留 Owner 查询功能
- [ ] 添加 deprecation 警告

### Task 3: Replace Shop=Tenant Assumption

**Search patterns:**
- `shop_id = tenant_id` - 移除
- `shop.id == tenant.id` - 替换为 tenant.shop_id

**Files to check:**
- [ ] Reception
- [ ] Reception
- [ ] Reception

### Task 4: Mark V1 Deprecated

**Files:**
- [ ] Add `@deprecated` decorator to v1 service methods
- [ ] Add deprecation log warning
- [ ] Update docstrings

### Task 5: Auto-Migration Path

**File:** `backend/app/services/v2_migration.py`

```python
def migrate_shop_to_v2(
    db_session: Session,
    shop_id: str,
) -> V2Shop:
    """
    自动迁移 v1 shop 到 v2
    1. Create V2Tenant
    2. Create V2shop with v1_shop_id
    3. Link owner_account
    4. Return V2Shop
    """
```

### Task 6: Tests & Validation

- [ ] 确保 v2 集成测试通过
- [ ] 确保 v1 runtime 不崩溃
- [ ] 验证 legacy 数据访问

## Implementation Plan

### Phase 8.1: Audit & Mark (2h)
- [ ] 审计所有 v1 代码路径
- [ ] 添加 deprecation 标记
- [ ] 创建迁移工具

### Phase 8.2: Remove Bootstrap (2h)
- [ ] 移除 shop bootstrap
- [ ] 移除 owner auto-creation
- [ ] 测试启动流程

### Phase 8.3: Clean Assumptions (2h)
- [ ] 替换 shop=tenant 假设
- [ ] 更新 API 路由
- [ ] 运行集成测试

### Phase 8.4: Documentation (1h)
- [ ] 更新 API 文档
- [ ] 创建迁移指南
- [ ] 更新 README

**Total: ~7h**

## Acceptance Criteria

- [ ] V1 bootstrap 不再自动创建
- [ ] Legacy shop 可通过 v2 API 访问
- [ ] 新用户走 v2 流程
- [ ] Old accounts 保留功能
- [ ] CI 测试通过
- [ ] 无 regression

## Risk Mitigation

1. **备份** - 生产数据完全备份
2. **Feature flag** - V2 rollout 可控
3. **Rollback** - 保留 v1 代码 1 个月
4. **Monitoring** - 监控错误率

## Post-Cleanup

- V1 代码保留至 v2.1
- V1 API deprecated but functional
- V2 becomes default path
