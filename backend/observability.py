"""
Observability module for Agri-Agent Swarm.

Provides:
- Prometheus metrics instrumentation (/metrics endpoint)
- Custom domain metrics for irrigation volumes, analyses, anomalies, and valve actuations
- OpenTelemetry distributed tracing integration
- LangSmith LLM cost and trace tracking status
"""
import os
import logging
from typing import Optional

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings

log = logging.getLogger("agri_agent.observability")

# ---------------------------------------------------------------------------
# Custom Prometheus Metrics
# ---------------------------------------------------------------------------

def _get_or_create_counter(name: str, doc: str, labelnames: list[str]) -> Counter:
    """Safely get or create a Prometheus counter without registration conflict."""
    try:
        return Counter(name, doc, labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)  # type: ignore[return-value]


def _get_or_create_gauge(name: str, doc: str, labelnames: list[str] = ()) -> Gauge:
    """Safely get or create a Prometheus gauge without registration conflict."""
    try:
        return Gauge(name, doc, labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)  # type: ignore[return-value]


ANALYSIS_RUNS_TOTAL = _get_or_create_counter(
    "agri_analysis_runs_total",
    "Total multi-agent farm analysis runs executed",
    ["crop_type", "decision"],
)

IRRIGATION_VOLUME_LITERS = _get_or_create_counter(
    "agri_irrigation_volume_liters_total",
    "Total water volume actuated in liters",
    ["crop_type"],
)

ANOMALIES_DETECTED_TOTAL = _get_or_create_counter(
    "agri_anomalies_detected_total",
    "Total anomalies detected by anomaly_check_node or background scheduler",
    ["severity", "anomaly_type"],
)

VALVE_COMMANDS_TOTAL = _get_or_create_counter(
    "agri_valve_commands_total",
    "Total valve actuation commands issued via MCP",
    ["command", "status"],
)

ACTIVE_FARMS_GAUGE = _get_or_create_gauge(
    "agri_active_farms_count",
    "Current number of registered farms in the multi-tenant system",
)

# ---------------------------------------------------------------------------
# OpenTelemetry Tracing
# ---------------------------------------------------------------------------

_tracer = None


def setup_opentelemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry tracer and instrument FastAPI if enabled."""
    global _tracer
    if not settings.otel_enabled:
        log.info("OpenTelemetry is disabled (OTEL_ENABLED=False)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(settings.otel_service_name)
        log.info("OpenTelemetry initialized with service name: %s", settings.otel_service_name)
    except Exception as e:
        log.warning("Could not initialize OpenTelemetry: %s", e)


def get_tracer(name: str = "agri_agent"):
    """Return active OpenTelemetry tracer or no-op fallback."""
    from opentelemetry import trace
    return trace.get_tracer(name)


# ---------------------------------------------------------------------------
# LangSmith Status & Diagnostics
# ---------------------------------------------------------------------------

def get_langsmith_status() -> dict:
    """
    Check if LangSmith LLM cost and trace tracking is actively configured.
    LangSmith traces automatically when LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY is present.
    """
    api_key_present = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1") or settings.langsmith_tracing
    project = os.getenv("LANGCHAIN_PROJECT", settings.langsmith_project)

    return {
        "enabled": tracing_enabled and api_key_present,
        "api_key_configured": api_key_present,
        "tracing_v2": tracing_enabled,
        "project": project,
        "endpoint": os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    }


# ---------------------------------------------------------------------------
# Prometheus FastApi Instrumentator Setup
# ---------------------------------------------------------------------------

def setup_prometheus(app: FastAPI) -> None:
    """Mount Prometheus /metrics endpoint on FastAPI app."""
    if not settings.prometheus_enabled:
        log.info("Prometheus metrics disabled (PROMETHEUS_ENABLED=False)")
        return

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics", tags=["Observability"])
    log.info("Prometheus metrics exposed at /metrics")
