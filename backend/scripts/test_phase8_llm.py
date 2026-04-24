#!/usr/bin/env python3
"""验证 Phase 8 LLM Provider 配置和基础功能"""
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from app.core.config import get_settings
from app.services.v2_metrics import LLMCallMetrics, metrics_collector
from app.services.llm_real_provider import OpenAILLMProvider, LLMMessage


def test_provider_configs():
    """测试 Provider 配置加载"""
    print("🧪 Testing Provider Configurations...\n")
    
    settings = get_settings()
    
    # Check LLM Provider
    print("[LLM Provider]")
    print(f"  Provider Name: {settings.llm_provider}")
    print(f"  API URL: {settings.llm_provider_api_url}")
    print(f"  Model: {settings.llm_provider_model}")
    print(f"  ✓ LLM configured\n" if settings.llm_provider_api_key else "  ✗ Missing API key\n")
    
    # Check ASR Provider
    print("[ASR Provider]")
    print(f"  Provider: {settings.asr_provider}")
    print("  ✓ ASR configured\n" if settings.asr_provider_api_key else "  ✗ Missing API key\n")
    
    # Check OCR Provider
    print("[OCR Provider]")
    print(f"  Provider: {settings.ocr_provider}")
    print("  ✓ OCR configured\n" if settings.ocr_provider_api_key else "  ✗ Missing API key\n")
    
    # Check Vision Provider
    print("[Vision Provider]")
    print(f"  Provider: {settings.vision_provider}")
    print("  ✓ Vision configured\n" if settings.vision_provider_api_key else "  ✗ Missing API key\n")
    
    return True


def test_llm_provider_direct():
    """直接测试 LLM Provider (可选)"""
    print("🤖 Testing LLM Provider Direct Call...\n")
    
    settings = get_settings()
    
    if not settings.llm_provider_api_key or settings.llm_provider_api_key == "***":
        print("  ⚠️  LLM API key not configured, skipping direct test")
        return False
    
    try:
        provider = OpenAILLMProvider(
            api_url=settings.llm_provider_api_url,
            api_key=settings.llm_provider_api_key,
            model=settings.llm_provider_model,
            timeout_seconds=30.0,
            max_tokens=100,
            temperature=0.7,
            provider_name=settings.llm_provider,
        )
        
        messages = [
            LLMMessage(role="system", content="你是一个专业的五金店AI助手。"),
            LLMMessage(role="user", content="店里还有多少库存？"),
        ]
        
        print("  Sending test message...")
        response = provider.completion(messages)
        
        if response and response.content:
            print(f"  ✓ Response received: {len(response.content)} chars")
            print(f"  Content preview: {response.content[:100]}...")
            
            # Record metrics
            if response.stats:
                metrics = LLMCallMetrics(
                    provider=settings.llm_provider,
                    model=settings.llm_provider_model,
                    latency_ms=response.stats.total_time_ms,
                    tokens_per_second=response.stats.tps,
                    input_tokens=response.stats.tokens_prompt,
                    output_tokens=response.stats.tokens_completion,
                    success=True
                )
                metrics_collector.record_call(metrics)
                print(f"  ✓ Metrics recorded: {response.stats.total_time_ms:.0f}ms")
            return True
        else:
            print("  ✗ No valid response")
            return False
            
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False


def test_metrics_system():
    """测试 Metrics 采集系统"""
    print("\n📊 Testing Metrics System...\n")
    
    # Add some test metrics
    for i in range(3):
        metrics = LLMCallMetrics(
            provider="test-provider",
            model="test-model",
            latency_ms=1200 + i * 100,
            tokens_per_second=25.0 + i,
            input_tokens=50 + i * 10,
            output_tokens=100 + i * 10,
            success=True
        )
        metrics_collector.record_call(metrics)
    
    # Get stats
    stats = metrics_collector.get_stats(provider="test-provider", window_minutes=60)
    
    if stats.get("test-provider"):
        s = stats["test-provider"]
        print(f"  Provider: {s.provider}")
        print(f"  Total calls: {s.total_calls}")
        print(f"  Avg latency: {s.avg_latency_ms:.1f}ms")
        print(f"  TPS: {s.avg_tokens_per_second:.1f}")
        print("  ✓ Metrics system working")
        return True
    else:
        print("  ✗ No stats found")
        return False


def main():
    """主测试入口"""
    print("=" * 50)
    print("Phase 8 LLM Integration Smoke Test")
    print("=" * 50 + "\n")
    
    results = []
    
    # Test 1: Configuration
    results.append(("Provider Configs", test_provider_configs()))
    
    # Test 2: LLM Provider
    results.append(("LLM Provider", test_llm_provider_direct()))
    
    # Test 3: Metrics
    results.append(("Metrics System", test_metrics_system()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed
    
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\n  Passed: {passed}/{len(results)}")
    print(f"  Failed: {failed}/{len(results)}")
    
    # Print metrics summary
    print("\n" + "-" * 50)
    metrics_collector.log_summary(window_minutes=60)
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
