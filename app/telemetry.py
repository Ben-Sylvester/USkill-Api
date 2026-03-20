"""
OpenTelemetry instrumentation — activated when OTEL_ENABLED=true.

Instruments:
  - FastAPI request spans (via opentelemetry-instrumentation-fastapi)
  - SQLAlchemy queries     (via opentelemetry-instrumentation-sqlalchemy)
  - httpx outgoing calls   (via opentelemetry-instrumentation-httpx)

Exports via OTLP gRPC to OTEL_ENDPOINT (default: localhost:4317).
Set OTEL_ENABLED=false (default) to run without any OTEL overhead.

Usage in main.py:
    from app.telemetry import setup_telemetry
    setup_telemetry(app)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def setup_telemetry(app) -> bool:  # noqa: ANN001
    """
    Attach OpenTelemetry instrumentation to the FastAPI app.
    Returns True if OTEL was activated, False if disabled or deps missing.
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.otel_enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OTEL_ENABLED=true but opentelemetry packages are not installed. "
            "Add opentelemetry-* to requirements.txt and reinstall."
        )
        return False

    # ── Tracer provider ───────────────────────────────────────────────
    resource = Resource(attributes={SERVICE_NAME: settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # ── Instrument FastAPI ────────────────────────────────────────────
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        # Exclude noisy infra paths from traces
        excluded_urls="/health,/metrics,/",
    )

    # ── Instrument outbound httpx (webhooks) ──────────────────────────
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)

    # ── Instrument SQLAlchemy ────────────────────────────────────────
    from app.database import engine
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=provider,
        enable_commenter=True,
    )

    logger.info(
        "OpenTelemetry enabled — exporting to %s as service '%s'",
        settings.otel_endpoint,
        settings.otel_service_name,
    )
    return True
