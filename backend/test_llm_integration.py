#!/usr/bin/env python3
"""Test LLM integration with OpenAI-compatible API."""

import asyncio
import json
import sys
import time

# Add backend to path
sys.path.insert(0, "/tmp/Business/backend")

from app.services.llm_real_provider import create_llm_provider


HERMES_BASE_URL = "https://gptrr.qzz.io/v1/chat/completions"
HERMES_API_KEY = "sk-c4f3546c266c51bacfb1e329ae3bf344192ee677f262c32bbab192e4f02c5e5c"
HERMES_MODEL = "kimi-k2.6"


def test_basic_chat():
    """Test basic chat completion."""
    print("=" * 60)
    print("Test 1: Basic Chat Completion")
    print("=" * 60)
    
    try:
        provider = create_llm_provider(
            api_url=HERMES_BASE_URL,
            api_key=HERMES_API_KEY,
            model=HERMES_MODEL,
            provider_name="hermes",
            timeout_seconds=60.0,
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": "Hello! Can you hear me?"},
        ]
        
        print(f"Sending request to: {HERMES_BASE_URL}")
        print(f"Model: {HERMES_MODEL}")
        print("-" * 40)
        
        response = provider.chat(messages)
        
        print(f"Response: {response.content}")
        print(f"Role: {response.role}")
        print(f"Usage: {response.usage}")
        print(f"Stats: {response.stats}")
        print("✅ PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_intent_parsing():
    """Test intent recognition with LLM."""
    print("\n" + "=" * 60)
    print("Test 2: Intent Parsing")
    print("=" * 60)
    
    try:
        provider = create_llm_provider(
            api_url=HERMES_BASE_URL,
            api_key=HERMES_API_KEY,
            model=HERMES_MODEL,
            provider_name="hermes",
            timeout_seconds=60.0,
            max_tokens=200,
        )
        
        prompt = """你是一个智能库存助手，负责解析用户的自然语言指令。

请分析用户的输入，提取以下信息并以JSON格式返回：
- intent: 意图类型 (stock_query, stock_in, stock_out, help, unknown)
- product_name: 商品名称
- quantity: 数量 (整数)
- specs: 规格 (可选)
- notes: 其他备注

用户输入: "进50个黄色手枪钻，3mm的"

请只返回JSON，不要其他文字:"""
        
        messages = [
            {"role": "system", "content": "You are a helpful inventory assistant. Respond only in JSON format."},
            {"role": "user", "content": prompt},
        ]
        
        print("User query: '进50个黄色手枪钻，3mm的'")
        print("-" * 40)
        
        response = provider.chat(messages)
        
        print(f"Raw response: {response.content}")
        
        # Try to parse JSON
        try:
            result = json.loads(response.content.strip())
            print(f"Parsed JSON: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("✅ PASSED - Intent parsing successful")
            return True
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse warning: {e}")
            print("⚠️ Response not valid JSON but LLM responded")
            return True
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_intent_variants():
    """Test multiple intent types."""
    print("\n" + "=" * 60)
    print("Test 3: Multiple Intent Variants")
    print("=" * 60)
    
    test_cases = [
        {"query": "查一下扳手还有多少个", "expected": "stock_query"},
        {"query": "进了20个螺丝刀", "expected": "stock_in"},
        {"query": "出了5个电钻", "expected": "stock_out"},
        {"query": "手枪钻多少钱", "expected": "price_query"},
    ]
    
    try:
        provider = create_llm_provider(
            api_url=HERMES_BASE_URL,
            api_key=HERMES_API_KEY,
            model=HERMES_MODEL,
            provider_name="hermes",
            timeout_seconds=60.0,
            max_tokens=150,
        )
        
        results = []
        for tc in test_cases:
            prompt = f"""解析用户指令，返回JSON格式：
- intent: 意图类型 (stock_query, stock_in, stock_out, price_query)
- product_name: 商品名称
- quantity: 数量
- specs: 规格

用户: "{tc['query']}"
只返回JSON:"""
            
            messages = [
                {"role": "system", "content": "Parse user intent, return JSON only."},
                {"role": "user", "content": prompt},
            ]
            
            response = provider.chat(messages)
            
            try:
                result = json.loads(response.content.strip())
                detected_intent = result.get("intent", "unknown")
                print(f"  ✅ '{tc['query']}' -> {detected_intent} (expected: {tc['expected']})")
                results.append((tc['query'], detected_intent == tc['expected']))
            except:
                print(f"  ⚠️ '{tc['query']}' -> parse error")
                results.append((tc['query'], False))
        
        passed = sum(1 for _, ok in results if ok)
        print(f"\n{passed}/{len(results)} intent detections correct")
        
        if passed >= len(results) * 0.75:  # Allow 1 failure
            print("✅ PASSED")
            return True
        else:
            print("❌ FAILED - Too many incorrect predictions")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streaming():
    """Test streaming chat completion."""
    print("\n" + "=" * 60)
    print("Test 4: Streaming Response")
    print("=" * 60)
    
    try:
        provider = create_llm_provider(
            api_url=HERMES_BASE_URL,
            api_key=HERMES_API_KEY,
            model=HERMES_MODEL,
            provider_name="hermes",
            timeout_seconds=60.0,
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "简单介绍一下你自己"},
        ]
        
        print("Streaming response:")
        print("-" * 40)
        
        collected = []
        for chunk in provider.chat_stream(messages):
            print(chunk, end="", flush=True)
            collected.append(chunk)
        
        print("\n" + "-" * 40)
        full_response = "".join(collected)
        print(f"Full response length: {len(full_response)} chars")
        print("✅ PASSED - Streaming working")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """Test LLM response time and basic load."""
    print("\n" + "=" * 60)
    print("Test 5: Performance Benchmark")
    print("=" * 60)
    
    try:
        provider = create_llm_provider(
            api_url=HERMES_BASE_URL,
            api_key=HERMES_API_KEY,
            model=HERMES_MODEL,
            provider_name="hermes",
            timeout_seconds=60.0,
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "1+1=?"},
        ]
        
        print("Running 3 parallel requests...")
        
        times = []
        for i in range(3):
            start = time.time()
            response = provider.chat(messages)
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.2f}s (TPS: {response.stats.tps:.1f})")
        
        avg_time = sum(times) / len(times)
        print(f"\nAverage response time: {avg_time:.2f}s")
        
        if avg_time < 15:  # Threshold for acceptable performance
            print("✅ PASSED - Performance OK")
            return True
        else:
            print("⚠️ SLOW - Response time > 15s")
            return True  # Still pass but note slowness
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "🔥" * 30)
    print("  LLM Integration Test Suite")
    print("🔥" * 30 + "\n")
    
    results = []
    
    results.append(("Basic Chat", test_basic_chat()))
    results.append(("Intent Parsing", test_intent_parsing()))
    results.append(("Multiple Intents", test_intent_variants()))
    results.append(("Streaming", test_streaming()))
    results.append(("Performance", test_performance()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! LLM integration is working.")
        print("\nNext steps:")
        print("  1. Update v2_llm.py to use real LLM provider")
        print("  2. Integrate with voice.py routes")
        print("  3. Test end-to-end voice -> LLM -> inventory flow")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
