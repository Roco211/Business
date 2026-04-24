#!/usr/bin/env python3
"""
Phase 9 场景测试脚本
验证：Chat/SSE/Catalog/Ledger/Alerts 端到端流程
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


def get_auth_context():
    """Login and get full context (token + tenant + shop + context_token)."""
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
    
    return {
        "token": token,
        "tenant_id": tid,
        "shop_id": sid,
        "context_token": ctx_token,
    }


def test_chat_standard():
    log("[Scenario 1] Chat Standard - Stock Query")
    ctx = get_auth_context()
    headers = {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Context-Token": ctx["context_token"],
    }
    
    r = httpx.post(f"{BASE}/chat", headers=headers, json={
        "message": "锤子还有多少个？"
    }, timeout=10)
    
    if r.status_code != 200:
        return check("Chat response", False, f"Status: {r.status_code}")
    
    data = r.json()["data"]
    ok = (
        data.get("intent") == "stock_query"
        and "锤子" in data.get("reply", "")
        and data.get("confidence", 0) > 0
    )
    return check("Chat stock query", ok, f"Reply: {data.get('reply', '')[:60]}")


def test_chat_sse():
    log("[Scenario 2] Chat SSE Streaming")
    ctx = get_auth_context()
    headers = {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Context-Token": ctx["context_token"],
        "Content-Type": "application/json",
    }
    
    r = httpx.post(f"{BASE}/chat/stream", headers=headers, json={
        "message": "查库存"
    }, timeout=15)
    
    if r.status_code != 200:
        return check("SSE stream", False, f"Status: {r.status_code}")
    
    # Parse SSE events
    events = []
    for line in r.text.strip().split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            event_type = line[7:]
        elif line.startswith("data: "):
            import json
            try:
                payload = json.loads(line[6:])
                events.append((event_type, payload))
            except json.JSONDecodeError:
                pass
    
    # Verify event sequence
    event_types = [e[0] for e in events]
    has_intent = "intent" in event_types
    has_inventory = "inventory" in event_types
    has_tokens = "token" in event_types
    has_done = "done" in event_types
    
    # Verify employee role in intent event
    intent_event = next((e for e in events if e[0] == "intent"), None)
    has_employee = intent_event and "employee" in intent_event[1] if intent_event else False
    
    ok = has_intent and has_tokens and has_done
    detail = f"Events: {event_types} | Employee: {has_employee}"
    return check("SSE event sequence", ok, detail)


def test_catalog():
    log("[Scenario 3] Catalog Query")
    ctx = get_auth_context()
    headers = {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Context-Token": ctx["context_token"],
    }
    
    r = httpx.get(f"{BASE}/inventory/catalog", headers=headers, timeout=10)
    if r.status_code != 200:
        return check("Catalog list", False, f"Status: {r.status_code}")
    
    data = r.json()["data"]
    items = data.get("items", [])
    ok = len(items) > 0
    return check("Catalog items", ok, f"Count: {len(items)}")


def test_ledger():
    log("[Scenario 4] Ledger Events Query")
    ctx = get_auth_context()
    headers = {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Context-Token": ctx["context_token"],
    }
    
    r = httpx.get(f"{BASE}/ledger/events", headers=headers, timeout=10)
    if r.status_code != 200:
        return check("Ledger events", False, f"Status: {r.status_code}")
    
    data = r.json()["data"]
    events = data.get("events", [])
    return check("Ledger query", True, f"Count: {len(events)}")


def test_alerts():
    log("[Scenario 5] Alerts Query")
    ctx = get_auth_context()
    headers = {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Context-Token": ctx["context_token"],
    }
    
    r = httpx.get(f"{BASE}/alerts", headers=headers, params={"shop_id": ctx["shop_id"]}, timeout=10)
    if r.status_code != 200:
        return check("Alerts list", False, f"Status: {r.status_code}")
    
    data = r.json()["data"]
    alerts = data.get("alerts", [])
    return check("Alerts query", True, f"Count: {len(alerts)}")


def main():
    print("Phase 9 Scenario Test Suite")
    print(f"Target: {BASE}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Chat Standard", test_chat_standard),
        ("Chat SSE", test_chat_sse),
        ("Catalog", test_catalog),
        ("Ledger", test_ledger),
        ("Alerts", test_alerts),
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
