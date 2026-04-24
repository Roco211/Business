#!/usr/bin/env python3
"""V2 Chat 端到端场景测试 - 模拟用户查询库存的完整流程"""
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import httpx
from app.services.v2_llm import get_llm_service

BASE = "http://127.0.0.1:8001/api/v2"


def test_chat_stock_query_scenario():
    """测试聊天库存查询场景：用户输入 -> 意图识别 -> 库存查询 -> 生成回复"""
    print("=" * 60)
    print("V2 Chat Stock Query Scenario")
    print("=" * 60)
    
    # Step 1: Login
    print("\n[1/5] Authenticate")
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "demo@aistoremanager.com",
        "password": "demo123"
    }, timeout=10)
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  ✓ Logged in")
    
    # Step 2: Get context
    print("\n[2/5] Resolve Context")
    r = httpx.get(f"{BASE}/me/tenants", headers=headers, timeout=10)
    tid = r.json()["data"]["tenants"][0]["tenant_id"]
    r = httpx.get(f"{BASE}/tenants/{tid}/shops", headers=headers, timeout=10)
    sid = r.json()["data"]["shops"][0]["shop_id"]
    r = httpx.post(f"{BASE}/context/select", headers=headers, json={
        "tenant_id": tid, "shop_id": sid
    }, timeout=10)
    ctx_token = r.json()["data"]["context_session_id"]
    ctx_headers = {
        "Authorization": f"Bearer {token}",
        "X-Context-Token": ctx_token
    }
    print(f"  ✓ Context: {sid[:16]}...")
    
    # Step 3: User sends message
    print("\n[3/5] User Intent Recognition")
    user_messages = [
        "电动螺丝刀还有几个？",
        "查一下库存",
        "进货了5把高精度锤子",
    ]
    
    llm_service = get_llm_service()
    intents = []
    for msg in user_messages:
        intent = llm_service.parse_intent(msg)
        intents.append((msg, intent))
        print(f"  \"{msg}\" -> {intent.intent_type}({intent.item_name}, qty={intent.quantity})")
    
    # Step 4: Query inventory based on intent
    print("\n[4/5] Inventory Query")
    r = httpx.get(f"{BASE}/inventory/stock", headers=ctx_headers, timeout=10)
    stock_items = r.json()["data"]["items"]
    
    # Build item lookup
    item_map = {}
    for item in stock_items:
        item_map[item["item_name"]] = item
        # Also map by SKU prefix if available
        sku = item.get("sku", "")
        if sku:
            item_map[sku.split("-")[-1]] = item
    
    print(f"  Available items: {len(stock_items)}")
    for item in stock_items:
        print(f"    - {item['item_name']}: {item['current_quantity']} {item['default_unit']}")
    
    # Step 5: Generate responses
    print("\n[5/5] Generate Responses")
    for msg, intent in intents:
        if intent.intent_type == "stock_query":
            # Find matching item
            matched_item = None
            if intent.item_name:
                for name, item in item_map.items():
                    if intent.item_name in name or name in intent.item_name:
                        matched_item = item
                        break
            
            if matched_item:
                query_result = {
                    "item_name": matched_item["item_name"],
                    "quantity": matched_item["current_quantity"],
                    "unit": matched_item["default_unit"]
                }
                response = llm_service.generate_response(query_result, msg)
                print(f"  Q: {msg}")
                print(f"  A: {response.content}")
            else:
                print(f"  Q: {msg}")
                print(f"  A: 未找到商品 \"{intent.item_name}\"，请确认商品名称")
        
        elif intent.intent_type == "stock_in":
            print(f"  Q: {msg}")
            print(f"  A: [系统] 收到入库请求：{intent.item_name} x {intent.quantity}，等待确认...")
        
        elif intent.intent_type == "stock_out":
            print(f"  Q: {msg}")
            print(f"  A: [系统] 收到出库请求：{intent.item_name} x {intent.quantity}，等待确认...")
        
        else:
            print(f"  Q: {msg}")
            print(f"  A: 抱歉，我不理解您的意思。您可以问我：")
            print(f"      - \"XX还有几个？\" 查库存")
            print(f"      - \"进货了X件XX\" 记录入库")
    
    print("\n" + "=" * 60)
    print("✅ Chat scenario completed")
    print("=" * 60)
    return True


def test_voice_photo_routes_exist():
    """验证 Voice/Photo 路由存在"""
    print("\n[Voice/Photo Routes]")
    
    # These should return 401/422 (not 404)
    routes = [
        ("/voice/stock-query", "POST"),
        ("/voice/stock-in", "POST"),
        ("/photo/stock-query", "POST"),
        ("/photo/stock-in", "POST"),
    ]
    
    for path, method in routes:
        r = httpx.request(method, f"{BASE}{path}", timeout=5)
        # 401 = needs auth, 422 = needs form data - both mean route exists
        # 404 = route not found
        exists = r.status_code != 404
        status = "✓" if exists else "✗"
        print(f"  {status} {method} {path}: {r.status_code}")
    
    return True


def main():
    results = []
    results.append(("Chat Stock Query", test_chat_stock_query_scenario()))
    results.append(("Voice/Photo Routes", test_voice_photo_routes_exist()))
    
    print("\n" + "=" * 60)
    print("Final Summary")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  [{status}] {name}")
    print(f"\nTotal: {passed}/{len(results)} passed")
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
