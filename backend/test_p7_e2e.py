#!/usr/bin/env python3
"""Phase 7 Integration Test Suite
Tests end-to-end integration of Voice, Photo, Audit, Alerts with existing systems
"""

import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_v2.db')
os.environ.setdefault('APP_RUNTIME_MODE', 'local-demo')

from fastapi.testclient import TestClient
from app.main import create_app

def run_tests():
    app = create_app()
    client = TestClient(app)
    
    results = []
    
    def test(name, method, path, expected_status, setup_fn=None):
        try:
            if setup_fn:
                setup_fn(client)
            
            if method == "GET":
                resp = client.get(path)
            elif method == "POST":
                resp = client.post(path)
            elif method == "PATCH":
                resp = client.patch(path)
            else:
                resp = client.request(method, path)
            
            passed = resp.status_code == expected_status
            results.append((name, passed, resp.status_code, expected_status))
            return resp
        except Exception as e:
            results.append((name, False, f"ERROR: {e}", expected_status))
            return None
    
    print("=" * 70)
    print(" Phase 7 Integration Test Suite")
    print("=" * 70)
    
    # Test Group 1: Health & System
    print("\n[Group 1: System Health]")
    test("Health Check", "GET", "/api/v2/health", 200)
    
    # Test Group 2: Authentication Flow
    print("\n[Group 2: Authentication]")
    login_resp = test("Login", "POST", "/api/v2/auth/login", 200)
    
    # Test Group 3: Core V2 APIs (need auth)
    print("\n[Group 3: Core V2 APIs]")
    test("List Tenants", "GET", "/api/v2/me/tenants", 401)  # No auth, expect 401
    test("Audit Logs (no auth)", "GET", "/api/v2/audit-logs?shop_id=test", 401)
    test("Alerts (no auth)", "GET", "/api/v2/alerts?shop_id=test", 401)
    
    # Test Group 4: Inventory APIs
    print("\n[Group 4: Inventory APIs]")
    test("List Items", "GET", "/api/v2/inventory/items?shop_id=test", 401)
    test("Query Stock", "GET", "/api/v2/inventory/stock?shop_id=test", 401)
    
    # Test Group 5: Phase 7 Voice/Photo APIs
    print("\n[Group 5: Phase 7 Voice/Photo APIs]")
    # These require auth + shop context
    test("Voice Stock Query", "POST", "/api/v2/voice/stock-query", 422)  # Missing files
    test("Voice Stock In", "POST", "/api/v2/voice/stock-in", 422)  # Missing files
    test("Photo Stock Query", "POST", "/api/v2/photo/stock-query", 422)  # Missing files
    test("Photo Stock In", "POST", "/api/v2/photo/stock-in", 422)  # Missing files
    
    # Test Group 6: Audit/Alerts APIs
    print("\n[Group 6: Audit/Alerts APIs]")
    test("Audit Logs List", "GET", "/api/v2/audit-logs?shop_id=test", 401)
    test("Alerts List", "GET", "/api/v2/alerts?shop_id=test", 401)
    test("Ack Alert (no id)", "PATCH", "/api/v2/alerts/test-id/ack?shop_id=test", 404)
    
    # Summary
    print("\n" + "=" * 70)
    print(" Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, p, _, _ in results if p)
    failed = len(results) - passed
    
    for name, p, got, expected in results:
        status = "PASS" if p else "FAIL"
        print(f" {status:6s} | {name:40s} | Got: {got}, Expected: {expected}")
    
    print("-" * 70)
    print(f" Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("\n All Phase 7 integration tests passed!")
    else:
        print(f"\n {failed} test(s) failed. Review expected.")
    
    print("=" * 70)
    
    # Verify routes registered
    print("\n[Phase 7 Routes Verification]")
    v2_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/v2/' in r.path]
    
    phase7_paths = [
        '/api/v2/voice/stock-query',
        '/api/v2/voice/stock-in',
        '/api/v2/photo/stock-query',
        '/api/v2/photo/stock-in',
        '/api/v2/audit-logs',
        '/api/v2/alerts',
    ]
    
    registered_paths = {r.path for r in v2_routes if hasattr(r, 'path')}
    
    for path in phase7_paths:
        found = 'OK' if path in registered_paths else 'MISSING'
        print(f" {path:40s} {found}")
    
    print("\n" + "=" * 70)
    print(" Integration test complete.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
