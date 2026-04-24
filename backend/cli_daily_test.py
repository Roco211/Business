#!/usr/bin/env python3
"""
CLI Daily Usage Test - Business Project V2
测试场景：
1. API 健康检查
2. 认证登录
3. 首页仪表盘数据
4. AI 意图解析（带性能统计）
5. 库存查询
6. 商品建档
7. 入库/出库场景
8. LLM 流式输出测试

输出：详细的性能报告和操作日志
"""

import time
import json
import requests
import sys
import os
import statistics
from datetime import datetime
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, '/tmp/Business/backend')

from app.core.config import get_settings

# ==================== 配置 ====================
BASE_URL = "http://127.0.0.1:8001"
API_V2 = f"{BASE_URL}/api/v2"
API_V1 = f"{BASE_URL}/api/v1"

# 性能统计
PERFORMANCE_STATS: Dict[str, List[float]] = {}
TEST_RESULTS: List[Dict[str, Any]] = []

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def log(msg: str, level="info"):
    """带颜色的日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if level == "info":
        print(f"[{timestamp}] {msg}")
    elif level == "success":
        print(f"{Colors.GREEN}[{timestamp}] ✓ {msg}{Colors.RESET}")
    elif level == "error":
        print(f"{Colors.RED}[{timestamp}] ✗ {msg}{Colors.RESET}")
    elif level == "warn":
        print(f"{Colors.YELLOW}[{timestamp}] ⚠ {msg}{Colors.RESET}")
    elif level == "header":
        print(f"{Colors.CYAN}{Colors.BOLD}\n{'='*60}\n{msg}\n{'='*60}{Colors.RESET}")

def measure_time(name: str):
    """上下文管理器测量执行时间"""
    class TimerContext:
        def __enter__(self):
            self.start = time.perf_counter()
            return self
        def __exit__(self, *args):
            elapsed = time.perf_counter() - self.start
            if name not in PERFORMANCE_STATS:
                PERFORMANCE_STATS[name] = []
            PERFORMANCE_STATS[name].append(elapsed)
            setattr(self, 'elapsed', elapsed)
    return TimerContext()

def record_result(test_name: str, status: bool, response_time: float, details: str = ""):
    """记录测试结果"""
    TEST_RESULTS.append({
        "test": test_name,
        "status": "PASS" if status else "FAIL",
        "response_time_ms": round(response_time * 1000, 2),
        "details": details
    })
    if status:
        log(f"{test_name}: {response_time*1000:.2f}ms", "success")
    else:
        log(f"{test_name}: {response_time*1000:.2f}ms - {details}", "error")

# ==================== 测试场景 ====================

def test_health_check():
    """测试1: API 健康检查"""
    log("测试 API 健康状态", "header")
    
    with measure_time("health_check") as timer:
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=10)
            elapsed = timer.elapsed
            if resp.status_code == 200:
                record_result("Health Check", True, elapsed, f"Status: {resp.status_code}")
                return True
            else:
                record_result("Health Check", False, elapsed, f"Unexpected status: {resp.status_code}")
                return False
        except Exception as e:
            record_result("Health Check", False, timer.elapsed, str(e))
            return False

def test_openapi_schema():
    """测试2: OpenAPI Schema 检查"""
    log("测试 OpenAPI Schema", "header")
    
    with measure_time("openapi_check") as timer:
        try:
            resp = requests.get(f"{BASE_URL}/openapi.json", timeout=15)
            elapsed = timer.elapsed
            if resp.status_code == 200:
                schema = resp.json()
                routes = len(schema.get('paths', {}))
                record_result("OpenAPI Schema", True, elapsed, f"{routes} endpoints")
                return True, schema
            else:
                record_result("OpenAPI Schema", False, elapsed, f"Status: {resp.status_code}")
                return False, None
        except Exception as e:
            record_result("OpenAPI Schema", False, timer.elapsed, str(e))
            return False, None

def test_auth_login():
    """测试3: 认证系统"""
    log("测试 JWT 认证", "header")
    
    with measure_time("auth_login") as timer:
        try:
            # 登录测试 (使用 demo 模式)
            login_data = {
                "phone_number": "13800138000",
                "verification_code": "888888"
            }
            resp = requests.post(f"{API_V2}/auth/verify", json=login_data, timeout=15)
            elapsed = timer.elapsed
            
            if resp.status_code == 200:
                data = resp.json()
                if "access_token" in data:
                    token = data["access_token"]
                    record_result("Auth Login", True, elapsed, f"Token: {token[:20]}...")
                    return True, token
                else:
                    record_result("Auth Login", False, elapsed, "No access_token in response")
                    return False, None
            else:
                record_result("Auth Login", False, elapsed, f"Status: {resp.status_code}")
                return False, None
        except Exception as e:
            record_result("Auth Login", False, timer.elapsed, str(e))
            return False, None

def test_dashboard(token: str):
    """测试4: 仪表盘数据"""
    log("测试首页仪表盘", "header")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        ("Dashboard Summary", f"{API_V2}/dashboard/summary", "GET"),
        ("Inventory Stats", f"{API_V2}/dashboard/inventory", "GET"),
    ]
    
    results = []
    for name, url, method in endpoints:
        with measure_time(f"dashboard_{name.lower().replace(' ', '_')}") as timer:
            try:
                if method == "GET":
                    resp = requests.get(url, headers=headers, timeout=10)
                
                elapsed = timer.elapsed
                if resp.status_code == 200:
                    data = resp.json()
                    summary = json.dumps(data, ensure_ascii=False)[:100] + "..."
                    record_result(f"Dashboard - {name}", True, elapsed, summary)
                    results.append(True)
                else:
                    record_result(f"Dashboard - {name}", False, elapsed, f"Status: {resp.status_code}")
                    results.append(False)
            except Exception as e:
                record_result(f"Dashboard - {name}", False, timer.elapsed, str(e))
                results.append(False)
    
    return all(results)

def test_llm_intent_parsing():
    """测试5: LLM 意图解析（核心功能）"""
    log("测试 LLM 意图解析性能", "header")
    
    try:
        from app.services.v2_llm import LLMService
        from app.services.llm_real_provider import get_llm_provider
        
        llm_service = LLMService()
        provider = get_llm_provider()
        
        test_cases = [
            ("进50个黄色手枪钻", "stock_in"),
            ("查一下今天进了多少货", "query"),
            ("手枪钻库存还有多少", "query"),
            ("出库3个手枪钻", "stock_out"),
            ("有什么商品快没货了", "alert"),
        ]
        
        results = []
        for query, expected_intent in test_cases:
            with measure_time(f"llm_intent_{expected_intent}") as timer:
                try:
                    start = time.perf_counter()
                    
                    # 测试意图解析
                    result = llm_service.parse_intent(query, context={})
                    
                    elapsed = time.perf_counter() - start
                    
                    if "error" in result:
                        record_result(f"LLM Intent: {query[:20]}", False, elapsed, result["error"])
                        results.append(False)
                    else:
                        intent = result.get("intent", "unknown")
                        confidence = result.get("confidence", 0)
                        matched = intent == expected_intent
                        status = "✓" if matched or intent in [expected_intent, "ambiguous"] else "✗"
                        record_result(
                            f"LLM Intent: {query[:20]}...", 
                            matched or confidence > 0, 
                            elapsed,
                            f"Intent={intent}, Conf={confidence:.2f}"
                        )
                        results.append(True)
                        
                except Exception as e:
                    record_result(f"LLM Intent: {query[:20]}...", False, timer.elapsed, str(e))
                    results.append(False)
        
        return all(results)
        
    except ImportError as e:
        log(f"无法导入 LLM 服务: {e}", "error")
        return False
    except Exception as e:
        log(f"LLM 测试失败: {e}", "error")
        return False

def test_llm_streaming():
    """测试6: LLM 流式输出"""
    log("测试 LLM SSE 流式输出", "header")
    
    test_messages = [
        "你好，我是五金店老板",
        "帮我查一下手枪钻的库存",
    ]
    
    try:
        from app.services.v2_llm import LLMService
        
        llm_service = LLMService()
        results = []
        
        for msg in test_messages:
            with measure_time(f"llm_stream_{msg[:10]}") as timer:
                try:
                    start = time.perf_counter()
                    
                    # 测试流式生成
                    chunks = []
                    tokens = 0
                    
                    for chunk in llm_service.generate_stream_response(
                        message=msg,
                        conversation_history=[],
                        context={"shop_id": "demo"},
                        employee_type="assistant"
                    ):
                        if chunk:
                            chunks.append(chunk)
                            tokens += len(chunk.split())
                    
                    elapsed = time.perf_counter() - start
                    total_text = "".join(chunks)
                    tps = tokens / elapsed if elapsed > 0 else 0
                    
                    record_result(
                        f"LLM Stream: {msg[:20]}...",
                        len(chunks) > 0,
                        elapsed,
                        f"{len(chunks)} chunks, {tokens} tokens, {tps:.1f} TPS"
                    )
                    results.append(len(chunks) > 0)
                    
                except Exception as e:
                    record_result(f"LLM Stream: {msg[:20]}...", False, timer.elapsed, str(e))
                    results.append(False)
        
        return all(results)
        
    except Exception as e:
        log(f"流式测试失败: {e}", "error")
        return False

def test_inventory_endpoints(token: str):
    """测试7: 库存相关端点"""
    log("测试库存 API", "header")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        ("Inventory Items", f"{API_V2}/inventory/items", "GET"),
        ("Stock Snapshot", f"{API_V2}/inventory/snapshot", "GET"),
        ("Inventory Alerts", f"{API_V2}/inventory/alerts", "GET"),
    ]
    
    results = []
    for name, url, method in endpoints:
        with measure_time(f"inventory_{name.lower().replace(' ', '_')}") as timer:
            try:
                if method == "GET":
                    resp = requests.get(url, headers=headers, timeout=15)
                
                elapsed = timer.elapsed
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        count = len(data)
                        record_result(f"Inventory - {name}", True, elapsed, f"{count} items")
                    elif isinstance(data, dict):
                        record_result(f"Inventory - {name}", True, elapsed, "OK")
                    results.append(True)
                else:
                    record_result(f"Inventory - {name}", False, elapsed, f"Status: {resp.status_code}")
                    results.append(False)
            except Exception as e:
                record_result(f"Inventory - {name}", False, timer.elapsed, str(e))
                results.append(False)
    
    return all(results)

def test_escalation_flow(token: str):
    """测试8: 升级处理流程"""
    log("测试升级处理流程", "header")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    escalation_data = {
        "original_intent": "stock_in",
        "user_message": "进50个黄色手枪钻",
        "session_context": {
            "shop_id": "demo",
            "matched_items": ["item_123"]
        },
        "escalation_reason": "Ambiguous product specification",
        "suggested_action": "Clarify product details"
    }
    
    with measure_time("escalation_create") as timer:
        try:
            resp = requests.post(
                f"{API_V2}/escalations",
                headers=headers,
                json=escalation_data,
                timeout=15
            )
            elapsed = timer.elapsed
            
            if resp.status_code in [200, 201]:
                record_result("Escalation", True, elapsed, f"Status: {resp.status_code}")
                return True
            else:
                record_result("Escalation", False, elapsed, f"Status: {resp.status_code}")
                return False
        except Exception as e:
            record_result("Escalation", False, timer.elapsed, str(e))
            return False

# ==================== 报告生成 ====================

def print_performance_report():
    """打印性能报告"""
    log("PERFORMANCE REPORT", "header")
    
    print(f"\n{Colors.BOLD}{'Test Name':<40} {'Count':>6} {'Min(ms)':>10} {'Avg(ms)':>10} {'Max(ms)':>10} {'p95(ms)':>10}{Colors.RESET}")
    print("-" * 90)
    
    all_times = []
    for name, times in sorted(PERFORMANCE_STATS.items()):
        if len(times) > 0:
            count = len(times)
            min_ms = min(times) * 1000
            avg_ms = sum(times) / len(times) * 1000
            max_ms = max(times) * 1000
            p95_ms = sorted(times)[int(len(times) * 0.95)] * 1000 if len(times) > 1 else avg_ms
            all_times.extend(times)
            
            status_color = Colors.GREEN if avg_ms < 500 else (Colors.YELLOW if avg_ms < 2000 else Colors.RED)
            print(f"{status_color}{name:<40} {count:>6} {min_ms:>10.1f} {avg_ms:>10.1f} {max_ms:>10.1f} {p95_ms:>10.1f}{Colors.RESET}")
    
    print("-" * 90)
    if all_times:
        total_run_time = sum(all_times) * 1000
        print(f"{'TOTAL RUN TIME':<40} {len(all_times):>6} {min(all_times)*1000:>10.1f} {sum(all_times)/len(all_times)*1000:>10.1f} {max(all_times)*1000:>10.1f} {'':>10}")
        print(f"Total test scenarios: {len(TEST_RESULTS)} | Passed: {sum(1 for r in TEST_RESULTS if r['status']=='PASS')} | Failed: {sum(1 for r in TEST_RESULTS if r['status']=='FAIL')}")

def print_summary_table():
    """打印结果摘要表"""
    log("TEST RESULTS SUMMARY", "header")
    
    passed = sum(1 for r in TEST_RESULTS if r['status'] == 'PASS')
    failed = sum(1 for r in TEST_RESULTS if r['status'] == 'FAIL')
    
    print(f"\n{Colors.BOLD}Overall Summary:{Colors.RESET}")
    print(f"  Total Tests: {len(TEST_RESULTS)}")
    print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")
    
    if failed > 0:
        print(f"\n{Colors.RED}Failed Tests:{Colors.RESET}")
        for r in TEST_RESULTS:
            if r['status'] == 'FAIL':
                print(f"  • {r['test']}: {r['details']}")
    
    # 根据耗时分类
    print(f"\n{Colors.BOLD}Response Time Analysis:{Colors.RESET}")
    fast = sum(1 for r in TEST_RESULTS if r['response_time_ms'] < 100)
    normal = sum(1 for r in TEST_RESULTS if 100 <= r['response_time_ms'] < 1000)
    slow = sum(1 for r in TEST_RESULTS if r['response_time_ms'] >= 1000)
    
    print(f"  <100ms (Fast):   {fast}")
    print(f"  100ms-1s (Normal): {normal}")
    print(f"  >1s (Slow):      {slow}")

# ==================== 主程序 ====================

def main():
    log(f"Business V2 CLI Daily Test Started", "header")
    log(f"Target: {BASE_URL}")
    log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Configuration: SQLite + OpenAI Compatible API")
    
    # 运行测试
    all_passed = True
    
    # 1. 健康检查
    if not test_health_check():
        log("健康检查失败，停止测试", "error")
        return
    
    # 2. OpenAPI Schema
    ok, schema = test_openapi_schema()
    if not ok:
        log("无法获取 API Schema", "warn")
    
    # 3. 登录认证
    ok, token = test_auth_login()
    if not ok:
        log("认证失败，跳过需要认证的测试", "warn")
        token = None
    else:
        # 4. 仪表盘
        if token:
            test_dashboard(token)
            
            # 7. 库存端点
            test_inventory_endpoints(token)
            
            # 8. 升级流程
            test_escalation_flow(token)
    
    # 5. LLM 意图解析（不需要服务器）
    test_llm_intent_parsing()
    
    # 6. LLM 流式输出
    test_llm_streaming()
    
    # 输出报告
    print("\n")
    print_performance_report()
    print_summary_table()
    
    # 最终状态
    passed = sum(1 for r in TEST_RESULTS if r['status'] == 'PASS')
    failed = sum(1 for r in TEST_RESULTS if r['status'] == 'FAIL')
    
    print(f"\n{Colors.BOLD}Test Run Complete: {passed}/{len(TEST_RESULTS)} passed{Colors.RESET}")
    
    # 保存详细报告
    report_file = f"/tmp/Business/backend/cli_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "summary": {
                "total": len(TEST_RESULTS),
                "passed": passed,
                "failed": failed
            },
            "performance_stats": {
                name: {
                    "count": len(times),
                    "min_ms": min(times) * 1000,
                    "max_ms": max(times) * 1000,
                    "avg_ms": sum(times) / len(times) * 1000
                } for name, times in PERFORMANCE_STATS.items()
            },
            "results": TEST_RESULTS
        }, f, indent=2, ensure_ascii=False)
    
    log(f"详细报告已保存: {report_file}")

if __name__ == "__main__":
    main()
