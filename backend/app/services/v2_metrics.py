"""Metrics and performance tracking for V2 LLM/AI Providers.

Usage:
    from app.services.v2_metrics import LLMCallMetrics, metrics_collector
    
    metrics = LLMCallMetrics(
        provider="volcano",
        model="ep-xxx",
        latency_ms=1234,
        tokens_per_second=42.5,
        success=True
    )
    metrics_collector.record_call(metrics)
    
    stats = metrics_collector.get_stats(provider="volcano", window_minutes=60)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import json
import os


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM/AI Provider call."""
    provider: str
    model: str
    latency_ms: float
    tokens_per_second: float
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error_type: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProviderStats:
    """Aggregated statistics for a provider."""
    provider: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    error_rate: float = 0.0
    slow_calls_count: int = 0  # calls > 5s


class MetricsCollector:
    """Collect and aggregate LLM/AI Provider performance metrics."""
    
    def __init__(self, log_file: Optional[str] = None):
        self._calls: list[LLMCallMetrics] = []
        self._log_file = log_file or self._default_log_path()
        self._slow_threshold_ms = 5000  # 5 seconds
        
    def _default_log_path(self) -> str:
        """Default metrics log file path."""
        return os.path.expanduser("~/.aism/metrics.jsonl")
    
    def record_call(self, metrics: LLMCallMetrics) -> None:
        """Record a new call metrics."""
        self._calls.append(metrics)
        self._log_metrics(metrics)
        
        # Log slow calls
        if metrics.latency_ms > self._slow_threshold_ms:
            print(f"[SLOW] {metrics.provider}/{metrics.model}: {metrics.latency_ms:.0f}ms")
            
    def _log_metrics(self, metrics: LLMCallMetrics) -> None:
        """Append metrics to log file."""
        try:
            os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
            with open(self._log_file, "a") as f:
                data = {
                    "provider": metrics.provider,
                    "model": metrics.model,
                    "latency_ms": metrics.latency_ms,
                    "tokens_per_second": metrics.tokens_per_second,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "success": metrics.success,
                    "error_type": metrics.error_type,
                    "timestamp": metrics.timestamp.isoformat()
                }
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            print(f"[WARN] Failed to log metrics: {e}")
            
    def get_stats(self, provider: Optional[str] = None, window_minutes: int = 60) -> dict[str, ProviderStats]:
        """Get aggregated statistics for providers.
        
        Args:
            provider: Filter by specific provider (None = all)
            window_minutes: Time window for aggregation
            
        Returns:
            Dict mapping provider name to ProviderStats
        """
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        # Filter calls by time window and provider
        filtered = [
            c for c in self._calls
            if c.timestamp > cutoff and (provider is None or c.provider == provider)
        ]
        
        # Group by provider
        by_provider: dict[str, list[LLMCallMetrics]] = defaultdict(list)
        for c in filtered:
            by_provider[c.provider].append(c)
            
        # Calculate stats
        stats: dict[str, ProviderStats] = {}
        for prov, calls in by_provider.items():
            total = len(calls)
            successful = sum(1 for c in calls if c.success)
            failed = total - successful
            
            latencies = [c.latency_ms for c in calls]
            avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
            sorted_lat = sorted(latencies)
            p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0.0
            
            tps_values = [c.tokens_per_second for c in calls]
            avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0.0
            
            slow_calls = sum(1 for c in calls if c.latency_ms > self._slow_threshold_ms)
            
            stats[prov] = ProviderStats(
                provider=prov,
                total_calls=total,
                successful_calls=successful,
                failed_calls=failed,
                total_latency_ms=sum(latencies),
                avg_latency_ms=avg_lat,
                p95_latency_ms=p95_lat,
                avg_tokens_per_second=avg_tps,
                error_rate=failed / total if total else 0.0,
                slow_calls_count=slow_calls
            )
            
        return stats
    
    def log_summary(self, provider: Optional[str] = None, window_minutes: int = 60) -> None:
        """Print a summary of metrics to console."""
        stats = self.get_stats(provider, window_minutes)
        
        print(f"\n📊 Provider Metrics ({window_minutes}m window)")
        print("-" * 60)
        for prov, s in stats.items():
            print(f"[{prov}]")
            print(f"  Total: {s.total_calls} (✓{s.successful_calls} ✗{s.failed_calls})")
            print(f"  Latency: {s.avg_latency_ms:.0f}ms avg, {s.p95_latency_ms:.0f}ms p95")
            print(f"  Throughput: {s.avg_tokens_per_second:.1f} tokens/s")
            print(f"  Error Rate: {s.error_rate*100:.1f}%, Slow: {s.slow_calls_count}")
            print()
            
    def get_slow_calls(self, threshold_ms: int = 5000, limit: int = 10) -> list[LLMCallMetrics]:
        """Get recent slow calls for debugging."""
        slow = [c for c in self._calls if c.latency_ms > threshold_ms]
        return sorted(slow, key=lambda c: c.timestamp, reverse=True)[:limit]


# Global collector instance
metrics_collector = MetricsCollector()
