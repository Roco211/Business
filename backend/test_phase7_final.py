#!/usr/bin/env python3
"""Phase 7 Final Validation"""

import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_v2.db')

from fastapi.testclient import TestClient
from app.main import create_app

def main():
    app = create_app()
    client = TestClient(app)
    
    print("=" * 70)
    print(" Phase 7 Final Validation")
    print("=" * 70)
    
    # Get all V2 routes
    v2_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/v2/' in r.path]
    
    print(f"\n V2 API Routes: {len(v2_routes)}")
    
    # Check Phase 7 routes specifically - check both exact match and pattern match
    phase7_routes = [
        ('/api/v2/voice/stock-query', 'POST'),
        ('/api/v2/voice/stock-in', 'POST'),
        ('/api/v2/photo/stock-query', 'POST'),
        ('/api/v2/photo/stock-in', 'POST'),
        ('/api/v2/audit-logs', 'GET'),
        ('/api/v2/alerts', 'GET'),
        ('/api/v2/alerts/{alert_id}/ack', 'PATCH'),  # Path param
    ]
    
    print("\n Phase 7 Route Validation:")
    all_exist = True
    for path, method in phase7_routes:
        found = False
        for r in v2_routes:
            if not hasattr(r, 'methods') or not hasattr(r, 'path'):
                continue
            if path in r.path and method in r.methods:
                found = True
                break
        status = "OK" if found else "MISSING"
        print(f" {status:10s} {method} {path}")
        if not found:
            all_exist = False
    
    # Test health
    resp = client.get('/api/v2/health')
    health_ok = resp.status_code == 200
    print(f"\n System Health: {resp.status_code} {'OK' if health_ok else 'FAIL'}")
    
    # Summary
    print("\n" + "=" * 70)
    if all_exist and health_ok:
        print(" Result: ALL PHASE 7 ROUTES REGISTERED")
    else:
        print(" Result: Some routes missing")
    print("=" * 70)
    
    return all_exist

if __name__ == "__main__":
    main()
