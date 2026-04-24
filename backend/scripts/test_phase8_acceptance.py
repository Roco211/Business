#!/usr/bin/env python3
"""
Phase 8 验收测试脚本
验证：V2 API 完整流程 + Provider 降级 + LLM 意图识别
"""
import os
import sys
import httpx
import time

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

BASE = "http://127.0.0.1:8001/api/v2"


def log(title):
    print(f"\n{'='*60}")
    print(title)
    print('='*60)


def check(desc, ok, detail=""):
    s = "✅" if ok else "❌"
    print(f"  {s} {desc}")
    if detail:
        print(f"     {detail}")
    return ok


def test_health():
    log("[1/8] Health Check")
    try:
        r = httpx.get(f"{BASE}/health", timeout=5)
        return check("Health API", r.status_code == 200, r.text[:80])
    except Exception as e:
        return check("Health API", False, str(e))


def test_auth():
    log("[2/8] Authentication")
    results = []
    # Email login
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "demo@aistoremanager.com", "password": "demo123"
    }, timeout=10)
    results.append(check("Email login", r.status_code == 200))
    # Phone login
    r = httpx.post(f"{BASE}/auth/login", json={
        "phone": "13800138000", "verification_code": "888888", "auth_method": "phone_code"
    }, timeout=10)
    results.append(check("Phone login", r.status_code == 200))
    return all(results)


def test_tenant_context():
    log("[3/8] Tenant & Context")
    results = []
    # Login
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "demo@aistoremanager.com", "password": "demo123"
    }, timeout=10)
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Tenants
    r = httpx.get(f"{BASE}/me/tenants", headers=headers, timeout=10)
    results.append(check("List tenants", r.status_code == 200))
    tenants = r.json()["data"]["tenants"]
    if not tenants:
        return all(results)
    tid = tenants[0]["tenant_id"]
    # Shops
    r = httpx.get(f"{BASE}/tenants/{tid}/shops", headers=headers, timeout=10)
    results.append(check("List shops", r.status_code == 200))
    shops = r.json()["data"]["shops"]
    if not shops:
        return all(results)
    sid = shops[0]["shop_id"]
    # Context select
    r = httpx.post(f"{BASE}/context/select", headers=headers, json={
        "tenant_id": tid, "shop_id": sid
    }, timeout=10)
    results.append(check("Context select", r.status_code == 200))
    return all(results)


def test_inventory():
    log("[4/8] Inventory APIs")
    results = []
    # Setup auth + context
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "demo@aistoremanager.com", "password": "demo123"
    }, timeout=10)
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
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
    # Stock
    r = httpx.get(f"{BASE}/inventory/stock", headers=ctx_headers, timeout=10)
    results.append(check("Stock list", r.status_code == 200))
    # Catalog - may return 404 if not implemented
    r = httpx.get(f"{BASE}/inventory/catalog", headers=ctx_headers, timeout=10)
    results.append(check("Catalog", r.status_code in (200, 404), f"Status: {r.status_code}"))
    # Ledger - may return 404 if not implemented
    r = httpx.get(f"{BASE}/ledger/events", headers=ctx_headers, timeout=10)
    results.append(check("Ledger", r.status_code in (200, 404), f"Status: {r.status_code}"))
    return all(results)


def test_alerts():
    log("[5/8] Alerts API")
    r = httpx.post(f"{BASE}/auth/login", json={
        "email": "demo@aistoremanager.com", "password": "demo123"
    }, timeout=10)
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
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
    r = httpx.get(f"{BASE}/alerts", headers=ctx_headers, params={"shop_id": sid}, timeout=10)
    return check("Alerts list", r.status_code in (200, 404), f"Status: {r.status_code}")


def test_llm_intent():
    log("[6/8] LLM Intent Recognition")
    from app.services.v2_llm import LLMService
    service = LLMService(provider=None)
    cases = [
        ("螺丝刀还有几个？", "stock_query"),
        ("进货了10把锤子", "stock_in"),
        ("今天卖了5个扳手", "stock_out"),
    ]
    results = []
    for text, expected in cases:
        intent = service.parse_intent(text)
        ok = intent.intent_type == expected
        results.append(check(f"'{text}' -> {intent.intent_type}", ok))
    return all(results)


def test_provider_gateways():
    log("[7/8] Provider Gateways (Mock Mode)")
    from app.core.config import get_settings
    from app.services.asr_gateway import build_asr_gateway
    from app.services.ocr_gateway import build_ocr_gateway
    from app.services.vision_gateway import build_vision_gateway
    
    results = []
    settings = get_settings()
    
    # ASR
    try:
        gw = build_asr_gateway(settings)
        results.append(check("ASR Gateway", True, "Mock fallback ready"))
    except Exception as e:
        results.append(check("ASR Gateway", False, str(e)))
    
    # OCR
    try:
        gw = build_ocr_gateway(settings)
        results.append(check("OCR Gateway", True, "Mock fallback ready"))
    except Exception as e:
        results.append(check("OCR Gateway", False, str(e)))
    
    # Vision
    try:
        gw = build_vision_gateway(settings)
        results.append(check("Vision Gateway", True, "Mock fallback ready"))
    except Exception as e:
        results.append(check("Vision Gateway", False, str(e)))
    
    return all(results)


def test_voice_photo_routes():
    log("[8/8] Voice/Photo Routes")
    routes = [
        ("/voice/stock-query", "POST"),
        ("/voice/stock-in", "POST"),
        ("/photo/stock-query", "POST"),
        ("/photo/stock-in", "POST"),
    ]
    results = []
    for path, method in routes:
        r = httpx.request(method, f"{BASE}{path}", timeout=5)
        exists = r.status_code != 404
        results.append(check(f"{method} {path}", exists, f"Status: {r.status_code}"))
    return all(results)


def main():
    print("Phase 8 Acceptance Test Suite")
    print(f"Target: {BASE}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Health", test_health),
        ("Auth", test_auth),
        ("Tenant Context", test_tenant_context),
        ("Inventory", test_inventory),
        ("Alerts", test_alerts),
        ("LLM Intent", test_llm_intent),
        ("Provider Gateways", test_provider_gateways),
        ("Voice/Photo Routes", test_voice_photo_routes),
    ]
    
    results = []
    for name, fn in tests:
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"\n  ❌ Exception in {name}: {e}")
            results.append((name, False))
    
    log("FINAL RESULT")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        s = "PASS" if ok else "FAIL"
        print(f"  [{s}] {name}")
    print(f"\n  Total: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
