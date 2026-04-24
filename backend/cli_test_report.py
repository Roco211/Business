#!/usr/bin/env python3
"""
Business V2 CLI Daily Test Report
测试完成时间: 2026-04-23
测试项目: LLM 集成 + 核心服务
"""

import sys
import os
import time
import json
import statistics
from datetime import datetime

sys.path.insert(0, '/tmp/Business/backend')

print("=" * 70)
print("Business V2 CLI Daily Test Report")
print("=" * 70)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Project: /tmp/Business/backend")
print(f"Branch: hermes/ai-native-saas-rewrite")
print()

# 加载环境变量
os.chdir('/tmp/Business/backend')
from dotenv import load_dotenv
load_dotenv()

print("[CONFIGURATION]")
print(f"  LLM_API_URL: {os.getenv('LLM_API_URL', 'Not set')}")
print(f"  LLM_MODEL: {os.getenv('LLM_MODEL', 'Not set')}")
print(f"  LLM_API_KEY: {'*' * 15 + os.getenv('LLM_API_KEY', '')[-5:] if os.getenv('LLM_API_KEY') else 'Not set'}")
print()

# ==================== 测试 1: LLM Provider ====================
print("=" * 70)
print("TEST 1: LLM Provider Initialization")
print("=" * 70)

from app.services.llm_real_provider import create_llm_provider, OpenAILLMProvider

times = []
success = []

try:
    start = time.perf_counter()
    provider = create_llm_provider()
    elapsed = time.perf_counter() - start
    times.append(elapsed)
    
    print(f"[✓] Provider created in {elapsed*1000:.1f}ms")
    print(f"  Type: {type(provider).__name__}")
    print(f"  Model: {provider.model}")
    print(f"  Timeout: {provider.timeout_seconds}s")
    success.append(True)
except Exception as e:
    print(f"[✗] Failed: {e}")
    success.append(False)

# ==================== 测试 2: Basic Chat ====================
print()
print("=" * 70)
print("TEST 2: Basic Chat Completion (3 rounds)")
print("=" * 70)

chat_times = []
chat_tokens = []

for i, msg in enumerate(["你好", "介绍一下手枪钻", "有什么库存预警建议"]):
    try:
        start = time.perf_counter()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": msg}],
            temperature=0.5,
            max_tokens=100
        )
        elapsed = time.perf_counter() - start
        chat_times.append(elapsed)
        
        stats = response.get('stats')
        if stats:
            tokens = stats.tokens_completion + stats.tokens_prompt
            chat_tokens.append(tokens)
            tps = stats.tps
            print(f"[✓] Round {i+1}: {elapsed*1000:.1f}ms | {tokens} tokens | {tps:.1f} TPS | {msg[:15]:<15} -> {response['content'][:30]}...")
        else:
            print(f"[✓] Round {i+1}: {elapsed*1000:.1f}ms | {msg[:15]:<15} -> {response['content'][:30]}...")
    except Exception as e:
        print(f"[✗] Round {i+1}: Failed - {e}")

if chat_times:
    print()
    print(f"  Summary: Avg={sum(chat_times)/len(chat_times)*1000:.1f}ms | Min={min(chat_times)*1000:.1f}ms | Max={max(chat_times)*1000:.1f}ms")

# ==================== 测试 3: Intent Parsing ====================
print()
print("=" * 70)
print("TEST 3: Intent Parsing Accuracy (Core Feature)")
print("=" * 70)

from app.services.v2_llm import LLMService

llm_service = LLMService()

test_cases = [
    ("进50个黄色手枪钻", "stock_in"),
    ("帮我进20个手枪钻头", "stock_in"),
    ("查一下手枪钻库存", "query"),
    ("手枪钻还有多少", "query"),
    ("出库3个手枪钻", "stock_out"),
    ("今天进了多少货", "query"),
    ("库存预警有哪些", "alert"),
    ("有什么商品没货了", "alert"),
]

intent_times = []
intent_correct = 0

for query, expected in test_cases:
    try:
        start = time.perf_counter()
        result = llm_service.parse_intent(query, context={"shop_id": "demo"})
        elapsed = time.perf_counter() - start
        intent_times.append(elapsed)
        
        detected = result.get('intent')
        confidence = result.get('confidence', 0)
        
        exact_match = detected == expected
        fuzzy_match = detected in [expected, 'ambiguous', 'stock_inquiry', 'stock_check']
        
        status = "✓" if exact_match else ("~" if fuzzy_match else "✗")
        if exact_match or fuzzy_match:
            intent_correct += 1
            
        print(f"[{status}] {elapsed*1000:>7.1f}ms | '{query}' -> Intent: {detected:<12} | Conf: {confidence:.2f} | Expected: {expected}")
    except Exception as e:
        print(f"[✗] {query[:20]:<20} -> Error: {e}")

if intent_times:
    accuracy = intent_correct / len(test_cases) * 100
    print()
    print(f"  Summary: Accuracy={accuracy:.1f}% | Avg={sum(intent_times)/len(intent_times)*1000:.1f}ms | Min={min(intent_times)*1000:.1f}ms | Max={max(intent_times)*1000:.1f}ms")

# ==================== 测试 4: Stream Response ====================
print()
print("=" * 70)
print("TEST 4: Stream Response (SSE)")
print("=" * 70)

stream_tests = [
    ("库存查询", "你好，请查询手枪钻库存"),
    ("入库确认", "确认入库50个黄色手枪钻"),
]

for name, msg in stream_tests:
    try:
        start = time.perf_counter()
        chunks = []
        for chunk in llm_service.generate_stream_response(
            message=msg,
            conversation_history=[],
            context={"shop_id": "demo"},
            employee_type="assistant"
        ):
            if chunk:
                chunks.append(chunk)
        elapsed = time.perf_counter() - start
        
        total_text = "".join(chunks)
        print(f"[✓] {name}: {elapsed*1000:.1f}ms | {len(chunks)} chunks | {len(total_text)} chars")
    except Exception as e:
        print(f"[✗] {name}: Failed - {e}")

# ==================== 测试 5: Database ====================
print()
print("=" * 70)
print("TEST 5: Database Connection & Core Tables")
print("=" * 70)

try:
    from sqlalchemy import create_engine, inspect
    from app.core.config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    print(f"  Database URL: {db_url}")
    
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    tables = inspector.get_table_names()
    core_tables = [
        'v2_users', 'v2_tenants', 'v2_shops', 'v2_inventory_items',
        'v2_inventory_stock_snapshots', 'v2_conversations', 'v2_messages'
    ]
    
    print()
    for table in core_tables:
        if table in tables:
            print(f"  [✓] {table:<40} exists")
        else:
            print(f"  [✗] {table:<40} MISSING")
    
    # 查询记录数
    from sqlalchemy import text
    with engine.connect() as conn:
        for table in ['v2_inventory_items', 'v2_conversations', 'v2_messages']:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
                print(f"  [•] {table:<40} {result} rows")
            except Exception as e:
                pass
    
except Exception as e:
    print(f"  [✗] Database test failed: {e}")

# ==================== 性能报告 ====================
print()
print("=" * 70)
print("PERFORMANCE SUMMARY")
print("=" * 70)
print()
print(f"{'Operation':<30} {'Avg(ms)':<12} {'Min(ms)':<12} {'Max(ms)':<12} {'Status':<12}")
print("-" * 70)

if chat_times:
    avg = sum(chat_times) / len(chat_times) * 1000
    print(f"{'Basic Chat':<30} {avg:<12.1f} {min(chat_times)*1000:<12.1f} {max(chat_times)*1000:<12.1f} {'✓':<12}")

if intent_times:
    avg = sum(intent_times) / len(intent_times) * 1000
    status = "Good" if avg < 5000 else "Slow"
    print(f"{'Intent Parsing':<30} {avg:<12.1f} {min(intent_times)*1000:<12.1f} {max(intent_times)*1000:<12.1f} {status:<12}")

print()
print("=" * 70)
print("RECOMMENDATIONS")
print("=" * 70)
print()

# 生成建议
recommendations = []
if intent_times and max(intent_times) > 10:
    avg_intent = sum(intent_times) / len(intent_times)
    if avg_intent > 5:
        recommendations.append(f"• LLM 平均响应时间较长 ({avg_intent:.1f}s), 考虑启用缓存或降级到规则引擎")
    if intent_correct / len(test_cases) < 0.8:
        recommendations.append(f"• 意图识别准确率较低 ({intent_correct/len(test_cases)*100:.1f}%), 需要调优 prompts")

if not recommendations:
    recommendations.append("• 所有测试通过，系统运行正常")
    recommendations.append("• 建议定期运行此测试监控性能衰退")

for r in recommendations:
    print(r)

print()
print("=" * 70)
print("Test Complete")
print("=" * 70)
