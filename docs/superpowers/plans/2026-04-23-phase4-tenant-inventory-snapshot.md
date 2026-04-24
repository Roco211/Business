# Phase 4+ 实施计划：多租户基础与库存快照

## 概述

**状态更新: 经检查发现 Phase 2/4 模型已存在**

通过代码审查确认：
- ✅ **V2Tenant/租户** - 已实现于 `v2_identity.py`
- ✅ **V2Shop/ShopMembership** - 已实现于 `v2_identity.py`  
- ✅ **V2InventoryStockSnapshot** - 已实现于 `v2_inventory.py`
- ✅ **V2InventoryLedgerEvent** - 已实现于 `v2_inventory.py`
- ✅ **v2_tenant_service** - 已实现于 `v2_identity.py`
- ✅ **v2_inventory_service** - 已实现于 `v2_inventory.py`

**结论**: Phase 2/4 基础设施已完成，直接跳转到阶段 7 场景实现

## 已完成的工作（之前已开发）

### Task 1: ✅ 租户模型 (已存在)
**Files:** `backend/app/models/v2_identity.py`
- V2Account: 账户系统
- V2Tenant: 租户/商家组织
- V2Shop: 门店（带 tenant_id 外键）
- V2TenantMembership: 租户成员关系
- V2ShopAccess: 门店访问权限

### Task 2: ✅ 库存快照模型 (已存在)
**Files:** `backend/app/models/v2_inventory.py`
- V2InventoryItem: 库存商品
- V2InventoryStockSnapshot: 库存快照/投影
- V2InventoryLedgerEvent: 库存事件账本

### Task 3-6: ✅ 服务和API (已存在)
- `backend/app/services/v2_identity.py` (8KB) - 多租户认证
- `backend/app/services/v2_inventory.py` (17KB) - 库存管理
- `backend/app/services/v2_inventory_projections.py` (4.5KB)
- `backend/app/api/v2/routes/identity.py` - API路由
- `backend/app/api/v2/routes/inventory.py` - API路由

## 下一步：阶段 7 场景实现

### 待实现场景（优先级 P0）
1. ⏳ **voice stock query** - 语音库存查询
2. ⏳ **voice stock in** - 语音入库
3. ⏳ **photo stock query** - 照片库存查询  
4. ⏳ **photo stock in** - 照片入库
5. ⏳ **manual correction** - 手动纠错
6. ⏳ **audit browsing** - 审计浏览
7. ✅ **receipt OCR stock in** - 票据OCR入库（已完成）
8. ⏳ **low-stock alerts** - 低库存警报

### 阶段 8 待清理
- ⏳ 移除 default shop bootstrap
- ⏳ 移除 default owner bootstrap
- ⏳ 移除 shop=tenant 假设
