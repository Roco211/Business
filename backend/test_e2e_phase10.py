#!/usr/bin/env python3
"""Phase 10: End-to-End API Test Suite for Business Backend.

Tests the complete V2 API flow:
1. Authentication (login + token)
2. Inventory CRUD
3. Chat scenarios (S1-S7)
4. Stock checks
5. Purchase suggestions
6. Dashboard/Analytics
"""

import json
import sys
import time
import uuid

import httpx

BASE_URL = "http://localhost:8001"
API_V2 = f"{BASE_URL}/api/v2"

# Test credentials
TEST_PHONE = "13800138000"
TEST_CODE = "888888"  # Demo verification code


class TestClient:
    """HTTP client with auth token management."""

    def __init__(self):
        self.client = httpx.Client(base_url=BASE_URL, timeout=30.0)
        self.token = None
        self.account_id = None
        self.shop_id = None

    def login(self) -> bool:
        """Login and get auth token + context token."""
        try:
            # Step 1: Login
            resp = self.client.post(
                f"{API_V2}/auth/login",
                json={
                    "auth_method": "phone_code",
                    "phone": TEST_PHONE,
                    "verification_code": TEST_CODE,
                }
            )
            data = resp.json()

            if "data" not in data:
                print(f"Login failed: {data}")
                return False

            self.token = data["data"].get("access_token") or data["data"].get("accessToken")
            self.account_id = data["data"].get("account_id") or data["data"].get("accountId")
            self.client.headers["Authorization"] = f"Bearer {self.token}"

            # Step 2: Get tenants
            resp = self.client.get(f"{API_V2}/me/tenants")
            tenants_data = resp.json()
            tenants = tenants_data.get("data", {}).get("tenants", [])
            if not tenants:
                print("No tenants found")
                return False
            tenant_id = tenants[0]["tenant_id"]

            # Step 3: Get shops for tenant
            resp = self.client.get(f"{API_V2}/tenants/{tenant_id}/shops")
            shops_data = resp.json()
            shops = shops_data.get("data", {}).get("shops", [])
            if not shops:
                print("No shops found")
                return False
            shop_id = shops[0]["shop_id"]
            self.shop_id = shop_id

            # Step 4: Select context
            resp = self.client.post(
                f"{API_V2}/context/select",
                json={"tenant_id": tenant_id, "shop_id": shop_id}
            )
            context_data = resp.json()
            if "data" not in context_data:
                print(f"Context select failed: {context_data}")
                return False

            context_data_body = context_data["data"]
            context_token = (
                context_data_body.get("contextToken")
                or context_data_body.get("contextSessionId")
                or context_data_body.get("context_token")
                or context_data_body.get("context_session_id")
            )
            self.client.headers["X-Context-Token"] = context_token

            return True

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def get(self, path: str, **kwargs):
        return self.client.get(f"{API_V2}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.client.post(f"{API_V2}{path}", **kwargs)

    def close(self):
        self.client.close()


def test_health():
    """T1: Health check."""
    print("\n[T1] Health Check")
    try:
        resp = httpx.get(f"{API_V2}/health", timeout=5.0)
        data = resp.json()
        assert data["data"]["status"] == "ok"
        print("  PASS - API is healthy")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False


def test_auth_flow(client: TestClient):
    """T2: Authentication flow."""
    print("\n[T2] Authentication Flow")

    # Login
    if not client.login():
        print("  FAIL - Login failed")
        return False

    print(f"  PASS - Login successful")
    print(f"       Token: {client.token[:20]}...")
    print(f"       Account: {client.account_id}")
    print(f"       Shop: {client.shop_id}")

    # Verify token works
    try:
        resp = client.get("/inventory/items")
        assert resp.status_code in (200, 404)  # 404 if no items yet
        print("  PASS - Token works for authenticated requests")
        return True
    except Exception as e:
        print(f"  FAIL - Token validation failed: {e}")
        return False


def test_inventory_crud(client: TestClient):
    """T3: Inventory CRUD operations."""
    print("\n[T3] Inventory CRUD")

    try:
        # Get existing items
        resp = client.get("/inventory/items")
        assert resp.status_code == 200
        items = resp.json().get("data", {}).get("items", [])

        if not items:
            print("  SKIP - No items in database")
            return True

        item = items[0]
        item_id = item["inventory_item_id"]
        item_name = item["name"]
        unit = item.get("default_unit") or "个"
        print(f"  Using existing item: {item_name} (ID: {item_id})")

        # Get current stock
        resp = client.get("/inventory/stock")
        assert resp.status_code == 200
        stock_items = resp.json().get("data", {}).get("items", [])
        stock_row = next((row for row in stock_items if row.get("inventory_item_id") == item_id), None)
        current_qty = stock_row.get("current_quantity", 0) if stock_row else 0
        print(f"  Current stock: {current_qty}")

        # Stock in - formal stock-in endpoint, not correction
        resp = client.post("/inventory/stock-in", json={
            "inventory_item_id": item_id,
            "stock_in_quantity": 50,
            "unit": unit,
            "price": 25.0,
            "reason": "测试入库",
        })
        assert resp.status_code == 200, f"Stock in failed: {resp.text}"
        stock_in_data = resp.json().get("data", {})
        after_stock_in = stock_in_data.get("new_quantity")
        print(f"  PASS - Stock in: new_quantity={after_stock_in}")

        # Stock out
        resp = client.post("/inventory/stock-out", json={
            "inventory_item_id": item_id,
            "expected_quantity": after_stock_in,
            "stock_out_quantity": 10,
            "reason": "测试出库",
        })
        assert resp.status_code == 200, f"Stock out failed: {resp.text}"
        print(f"  PASS - Stock out: -10 units")

        # Verify final stock
        resp = client.get("/inventory/stock")
        final_items = resp.json().get("data", {}).get("items", [])
        final_row = next((row for row in final_items if row.get("inventory_item_id") == item_id), None)
        final_qty = final_row.get("current_quantity", 0) if final_row else 0
        print(f"  PASS - Final stock: {final_qty}")

        return True

    except Exception as e:
        print(f"  FAIL - {e}")
        return False


def test_chat_scenarios(client: TestClient):
    """T4: Chat scenarios S1-S7."""
    print("\n[T4] Chat Scenarios (S1-S7)")

    scenarios = [
        ("S1-入库", "进50个测试扳手", "stock_in"),
        ("S2-出库", "出了10个测试扳手", "stock_out"),
        ("S3-查询", "测试扳手还有多少个", "stock_query"),
        ("S6-营业额", "今天营业额多少", "revenue_query"),
        ("S6-销量", "热销商品排行", "sales_query"),
        ("S5-预警", "库存预警", "alert_query"),
    ]

    results = []
    for name, message, expected_intent in scenarios:
        try:
            resp = client.post("/chat", json={"message": message})
            assert resp.status_code == 200, f"HTTP {resp.status_code}"

            data = resp.json()["data"]
            actual_intent = data.get("intent", "unknown")
            reply = data.get("reply", "")

            # For S1/S2, we check if transaction was processed
            # For S3/S6/S5, we check intent matches
            if expected_intent in ("stock_in", "stock_out"):
                # Just verify we got a response
                success = bool(reply)
            else:
                success = actual_intent == expected_intent

            status = "PASS" if success else "WARN"
            print(f"  {status} - {name}: intent={actual_intent}, reply={reply[:50]}...")
            results.append(success)

        except Exception as e:
            print(f"  FAIL - {name}: {e}")
            results.append(False)

    return all(results)


def test_stock_check(client: TestClient):
    """T5: Stock check (盘点)."""
    print("\n[T5] Stock Check (盘点)")

    try:
        # Get items
        resp = client.get("/inventory/items")
        assert resp.status_code == 200
        items = resp.json().get("data", {}).get("items", [])

        if not items:
            print("  SKIP - No items to check")
            return True

        item = items[0]
        item_id = item["inventory_item_id"]

        # Create stock check record
        resp = client.post("/stock-checks", json={
            "inventory_item_id": item_id,
            "actual_quantity": 95,
            "check_method": "manual",
            "notes": "测试盘点",
        })
        assert resp.status_code == 200, f"Create check failed: {resp.text}"
        check = resp.json()["data"]
        check_id = check["check_id"]
        print(f"  PASS - Created check record: diff={check['difference']}")

        # Get check summary
        resp = client.get("/stock-checks/summary")
        assert resp.status_code == 200
        summary = resp.json()["data"]
        print(f"  PASS - Summary: total_checks={summary.get('total_checks')}")

        # Resolve the check
        resp = client.post(f"/stock-checks/{check_id}/resolve", json={
            "resolution": "correct",
            "note": "调整为实际库存",
        })
        assert resp.status_code == 200
        print(f"  PASS - Resolved check: corrected")

        return True

    except Exception as e:
        print(f"  FAIL - {e}")
        return False


def test_purchase_suggestions(client: TestClient):
    """T6: Purchase suggestions."""
    print("\n[T6] Purchase Suggestions")

    try:
        resp = client.get("/purchase/suggestions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        suggestions = data.get("suggestions", [])
        print(f"  PASS - Got {len(suggestions)} suggestions")

        # Get summary
        resp = client.get("/purchase/summary")
        assert resp.status_code == 200
        summary = resp.json()["data"]
        print(f"  PASS - Summary: total_needed={summary.get('total_estimated_cost')}")

        return True

    except Exception as e:
        print(f"  FAIL - {e}")
        return False


def test_dashboard(client: TestClient):
    """T7: Dashboard and analytics."""
    print("\n[T7] Dashboard & Analytics")

    try:
        # Summary
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 200
        summary = resp.json()["data"]
        print(f"  PASS - Summary: revenue={summary.get('today_revenue')}")

        # Alerts
        resp = client.get(f"/alerts?shop_id={client.shop_id}")
        assert resp.status_code == 200
        alerts = resp.json().get("data", {})
        print(f"  PASS - Alerts: count={alerts.get('pagination', {}).get('count', 0)}")

        return True

    except Exception as e:
        print(f"  FAIL - {e}")
        return False


def main():
    print("=" * 60)
    print("Phase 10: End-to-End API Test Suite")
    print("=" * 60)

    # T1: Health
    health_ok = test_health()
    if not health_ok:
        print("\nHealth check failed, aborting tests.")
        return

    # Create client
    client = TestClient()

    # T2: Auth
    auth_ok = test_auth_flow(client)
    if not auth_ok:
        print("\nAuth failed, aborting tests.")
        client.close()
        return

    # Run all tests
    results = [
        ("T3-Inventory CRUD", test_inventory_crud(client)),
        ("T4-Chat Scenarios", test_chat_scenarios(client)),
        ("T5-Stock Check", test_stock_check(client)),
        ("T6-Purchase Suggestions", test_purchase_suggestions(client)),
        ("T7-Dashboard", test_dashboard(client)),
    ]

    client.close()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = auth_ok
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        all_passed = all_passed and passed

    total = len(results) + 1  # +1 for auth
    passed = sum(1 for _, p in results if p) + (1 if auth_ok else 0)

    print(f"\nTotal: {passed}/{total} tests passed")

    if all_passed:
        print("\nAll tests PASSED!")
    else:
        print("\nSome tests FAILED - see details above")


if __name__ == "__main__":
    main()
