#!/usr/bin/env python3
"""Phase 8 LLM Integration Test - Real API Call Verification."""

import os
import sys
import time

sys.path.insert(0, "/root/business-clone/backend")

# Load env from .env file
from dotenv import load_dotenv
load_dotenv("/root/business-clone/backend/.env")

from app.services.llm_real_provider import create_llm_provider
from app.services.v2_llm import get_llm_service, LLMService


def test_real_llm_chat():
    """Test actual LLM API call."""
    print("=" * 60)
    print("Test: Real LLM Chat API Call")
    print("=" * 60)

    try:
        provider = create_llm_provider()
        print(f"Provider: {provider.provider_name}")
        print(f"Model: {provider.model}")
        print(f"URL: {provider.api_url[:50]}...")

        messages = [
            {"role": "system", "content": "你是店铺库存助手。简洁回复。"},
            {"role": "user", "content": "螺丝刀还有多少个？"},
        ]

        print("\nSending request...")
        start = time.time()
        response = provider.chat(messages, stream=False)
        elapsed = time.time() - start

        print(f"Response: {response.content[:100]}...")
        print(f"Time: {elapsed:.2f}s")

        if response.stats:
            print(f"Stats: {response.stats.tokens_prompt} prompt / {response.stats.tokens_completion} completion tokens")
            print(f"TPS: {response.stats.tps:.1f}")

        print(f"[PASS] Real LLM call succeeded")
        return True

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return False


def test_intent_parsing():
    """Test intent parsing with real LLM."""
    print("\n" + "=" * 60)
    print("Test: Intent Parsing with Real LLM")
    print("=" * 60)

    try:
        # Reset singleton to pick up real provider
        import app.services.v2_llm as v2_llm_module
        v2_llm_module._llm_service = None

        service = get_llm_service()
        print(f"Mock mode: {service._use_mock}")

        if service._use_mock:
            print("[SKIP] No real provider available")
            return False

        test_cases = [
            "查一下螺丝刀还有多少个",
            "进50个黄色手枪钻",
            "出了5个电钻",
            "扳手多少钱",
            "今天营业额多少",
        ]

        for query in test_cases:
            print(f"\n  Query: '{query}'")
            start = time.time()
            result = service.parse_intent(query)
            elapsed = time.time() - start

            print(f"    Intent: {result.intent_type}")
            print(f"    Item: {result.item_name}")
            print(f"    Qty: {result.quantity}")
            print(f"    Confidence: {result.confidence}")
            print(f"    Time: {elapsed:.2f}s")

        print(f"\n[PASS] Intent parsing with real LLM succeeded")
        return True

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return False


def test_streaming():
    """Test streaming response."""
    print("\n" + "=" * 60)
    print("Test: Streaming Response")
    print("=" * 60)

    try:
        provider = create_llm_provider()

        messages = [
            {"role": "system", "content": "你是店铺库存助手。"},
            {"role": "user", "content": "库存不足怎么办？"},
        ]

        print("Streaming response:")
        start = time.time()
        chunks = []
        for chunk in provider.chat_stream(messages):
            chunks.append(chunk)
            print(chunk, end="", flush=True)

        elapsed = time.time() - start
        full_response = "".join(chunks)

        print(f"\n\nFull response: {full_response[:100]}...")
        print(f"Time: {elapsed:.2f}s")
        print(f"Chunks: {len(chunks)}")

        print(f"[PASS] Streaming succeeded")
        return True

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Phase 8: LLM Real Provider Integration Tests")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Basic chat
    results.append(("Real LLM Chat", test_real_llm_chat()))

    # Test 2: Intent parsing
    results.append(("Intent Parsing", test_intent_parsing()))

    # Test 3: Streaming
    results.append(("Streaming", test_streaming()))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
