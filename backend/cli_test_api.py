#!/usr/bin/env python3
"""
Business V2 CLI API Test
后端服务完整测试
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001"
API_V2 = f"{BASE_URL}/api/v2"

print("=" * 70)
print("Business V2 CLI API Test")
print("=" * 70)
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"目标: {BASE_URL}")
print()

results = []

def record(name, status, duration, details=""):
    marker = "✅" if status else "❌"
    results.append({"name": name, "status": status, "ms": duration * 1000, "details": details})
    print(f"{marker} {name:<38} {duration * 1000:>8.1f}ms | {details}")

# 测试 1: Health
print("▶ Health Check")
start = time.time()
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    record("Health API", r.status_code == 200, time.time() - start, r.text)
except Exception as e:
    record("Health API", False, time.time() - start, str(e))

# 测试 2: OpenAPI Schema
print("\n▶ API Discovery")
start = time.time()
try:
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    if r.status_code == 200:
        schema = r.json()
        endpoints = len(schema.get('paths', {}))
        endpoints_v2 = len([p for p in schema.get('paths', {}) if '/api/v2/' in p])
        record("OpenAPI Schema", True, time.time() - start, f"{endpoints} total / {endpoints_v2} v2")
    else:
        record("OpenAPI Schema", False, time.time() - start, f"HTTP {r.status_code}")
except Exception as e:
    record("OpenAPI Schema", False, time.time() - start, str(e))

# 测试 3: Auth (使用正确的 V2 格式)
print("\n▶ Authentication (V2)")
start = time.time()
token = None
try:
    # V2 使用 email/password 格式
    r = requests.post(f"{API_V2}/auth/login", json={
        "email": "demo@example.com",
        "password": "demo123456"
    }, timeout=10)
    elapsed = time.time() - start
    
    if r.status_code == 200:
        data = r.json()
        token = data.get('data', {}).get('access_token')
        record("V2 Login", True, elapsed, f"Token: {token[:25]}..." if token else "No token")
    else:
        # 如果认证失败但 422 格式正确，说明接口存在但凭证错误
        if r.status_code == 422:
            record("V2 Login", False, elapsed, f"Validation Error - check credentials")
        elif r.status_code == 401:
            record("V2 Login", False, elapsed, "Unauthorized - invalid credentials")
        else:
            record("V2 Login", False, elapsed, f"HTTP {r.status_code}")
except Exception as e:
    record("V2 Login", False, time.time() - start, str(e))

# 测试 4: 数据库/API 状态
print("\n▶ V2 Health Status")
start = time.time()
try:
    r = requests.get(f"{API_V2}/health", timeout=5)
    elapsed = time.time() - start
    if r.status_code == 200:
        health = r.json()
        status = health.get('data', {}).get('status', 'unknown')
        record("V2 Health", True, elapsed, f"Status: {status}")
    else:
        record("V2 Health", False, elapsed, f"HTTP {r.status_code}")
except Exception as e:
    record("V2 Health", False, time.time() - start, str(e))

# 测试 5: Inventory 公开端点（如果没有 auth）
print("\n▶ Inventory API")

# 尝试无 Auth 访问
start = time.time()
try:
    r = requests.get(f"{API_V2}/inventory/items?page_size=1", timeout=10)
    elapsed = time.time() - start
    
    if r.status_code == 200:
        data = r.json()
        items_count = len(data.get('data', {}).get('items', []))
        record("Inventory Items", True, elapsed, f"{items_count} items")
    elif r.status_code == 401:
        record("Inventory Items", False, elapsed, "Auth required")
    else:
        record("Inventory Items", False, elapsed, f"HTTP {r.status_code}")
except Exception as e:
    record("Inventory Items", False, time.time() - start, str(e))

# 如果拿到了 token，测试认证端点
if token:
    print("\n▶ Authenticated Endpoints")
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        ("Identity Me", "GET", f"{API_V2}/me"),
        ("Conversation List", "GET", f"{API_V2}/conversations?page_size=1"),
        ("Tenant List", "GET", f"{API_V2}/tenants?page_size=1"),
        ("Shop List", "GET", f"{API_V2}/shops?page_size=1"),
    ]
    
    for name, method, url in endpoints:
        start = time.time()
        try:
            r = requests.get(url, headers=headers, timeout=10)
            elapsed = time.time() - start
            
            status = r.status_code == 200
            details = f"HTTP {r.status_code}"
            if status:
                data = r.json()
                data_key = list(data.get('data', {}).keys())[0] if data.get('data') else 'ok'
                details = f"{data_key}"
            
            record(f"API - {name}", status, elapsed, details)
        except Exception as e:
            record(f"API - {name}", False, time.time() - start, str(e)[:40])

# Summary
print()
print("=" * 70)
print("Summary Report")
print("=" * 70)

total = len(results)
passed = sum(1 for r in results if r["status"])
failed = total - passed

print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
print()

if results:
    times = [r["ms"] for r in results if r["status"]]
    if times:
        print("Performance Statistics:")
        print(f"  Average Response: {sum(times)/len(times):>.1f} ms")
        print(f"  Fastest:            {min(times):>.1f} ms")
        print(f"  Slowest:            {max(times):>.1f} ms")
        print(f"  95th Percentile:    {sorted(times)[int(len(times)*0.95)]:>.1f} ms")

if failed > 0:
    print()
    print("Failed Endpoints:")
    for r in results:
        if not r["status"]:
            print(f"  • {r['name']}: {r['details']}")

print()
print("=" * 70)
print("Status:", end=" ")
if passed == total:
    print("🟢 All systems operational")
elif passed >= total * 0.7:
    print("🟡 Core functionality intact")
else:
    print("🔴 System degraded")
print("=" * 70)
