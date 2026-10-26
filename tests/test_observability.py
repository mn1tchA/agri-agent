"""
Unit tests for the observability module (Prometheus metrics, OpenTelemetry, LangSmith).
"""

from api import app
from observability import (
    ANALYSIS_RUNS_TOTAL,
    ANOMALIES_DETECTED_TOTAL,
    IRRIGATION_VOLUME_LITERS,
    VALVE_COMMANDS_TOTAL,
    get_langsmith_status,
    get_tracer,
    setup_opentelemetry,
)


class TestObservabilitySuite:
    """Test custom metrics, OpenTelemetry, and LangSmith."""

    def test_custom_prometheus_metrics(self):
        ANALYSIS_RUNS_TOTAL.labels(crop_type="Wheat", decision="irrigate").inc()
        IRRIGATION_VOLUME_LITERS.labels(crop_type="Wheat").inc(5000.0)
        ANOMALIES_DETECTED_TOTAL.labels(severity="CRITICAL", anomaly_type="EXTREME_HEAT").inc()
        VALVE_COMMANDS_TOTAL.labels(command="OPEN_VALVE", status="EXECUTED").inc()

    def test_opentelemetry_tracer(self):
        setup_opentelemetry(app)
        tracer = get_tracer("test_tracer")
        assert tracer is not None

    def test_langsmith_diagnostics(self):
        status = get_langsmith_status()
        assert "enabled" in status
        assert "project" in status
        assert "endpoint" in status
