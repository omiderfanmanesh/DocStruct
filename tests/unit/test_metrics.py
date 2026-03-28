"""Unit tests for metrics collection."""

import pytest

from docstruct.infrastructure.metrics import (
    MetricsCollector,
    StageMetric,
    Timer,
    get_metrics,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    yield
    reset_metrics()


class TestStageMetric:
    def test_record_single(self):
        metric = StageMetric()
        metric.record(100.0)
        assert metric.call_count == 1
        assert metric.avg_duration_ms == 100.0
        assert metric.error_count == 0
        assert metric.error_rate == 0.0

    def test_record_with_error(self):
        metric = StageMetric()
        metric.record(50.0, error=True)
        assert metric.error_count == 1
        assert metric.error_rate == 1.0

    def test_record_multiple(self):
        metric = StageMetric()
        metric.record(100.0)
        metric.record(200.0)
        metric.record(300.0)
        assert metric.call_count == 3
        assert metric.avg_duration_ms == 200.0
        assert metric.min_duration_ms == 100.0
        assert metric.max_duration_ms == 300.0

    def test_to_dict(self):
        metric = StageMetric()
        metric.record(100.0)
        d = metric.to_dict()
        assert "call_count" in d
        assert "avg_duration_ms" in d
        assert "error_rate" in d


class TestMetricsCollector:
    def test_record_stage(self):
        mc = MetricsCollector()
        mc.record_stage("rewrite", 50.0)
        mc.record_stage("rewrite", 100.0)
        summary = mc.get_summary()
        assert summary["stages"]["rewrite"]["call_count"] == 2
        assert summary["stages"]["rewrite"]["avg_duration_ms"] == 75.0

    def test_record_retrieval(self):
        mc = MetricsCollector()
        mc.record_retrieval(graph_count=3, fulltext_count=2, vector_count=0, total_candidates=5)
        summary = mc.get_summary()
        assert summary["retrieval"]["total_queries"] == 1
        assert summary["retrieval"]["graph_hit_rate"] == 1.0
        assert summary["retrieval"]["vector_hit_rate"] == 0.0

    def test_record_confidence(self):
        mc = MetricsCollector()
        mc.record_confidence(0.8)
        mc.record_confidence(0.6)
        summary = mc.get_summary()
        assert summary["avg_confidence_score"] == 0.7

    def test_record_zero_result_query(self):
        mc = MetricsCollector()
        mc.record_retrieval(total_candidates=0)
        summary = mc.get_summary()
        assert summary["retrieval"]["zero_result_rate"] == 1.0

    def test_reset(self):
        mc = MetricsCollector()
        mc.record_query()
        mc.record_llm_call()
        mc.reset()
        summary = mc.get_summary()
        assert summary["total_queries"] == 0
        assert summary["total_llm_calls"] == 0


class TestTimer:
    def test_timer_measures_elapsed(self):
        timer = Timer().start()
        import time
        time.sleep(0.05)
        elapsed = timer.stop()
        assert elapsed >= 40  # at least 40ms (some slack)
        assert elapsed < 500

    def test_elapsed_ms_before_stop(self):
        timer = Timer().start()
        import time
        time.sleep(0.02)
        # Should return current elapsed without stopping
        elapsed = timer.elapsed_ms
        assert elapsed >= 15


class TestGlobalMetrics:
    def test_global_metrics_singleton(self):
        metrics = get_metrics()
        metrics.record_query()
        summary = metrics.get_summary()
        assert summary["total_queries"] == 1
