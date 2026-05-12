from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import get_settings

logger = logging.getLogger(__name__)
_OBSERVABILITY_INITIALIZED = False
_LANGFUSE_CLIENT: Langfuse | None = None


def _parse_otlp_headers(headers: str | None) -> dict[str, str]:
    if not headers:
        return {}
    parsed: dict[str, str] = {}
    for item in headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            parsed[key] = value
    return parsed


def _init_otel(app: FastAPI | None = None) -> None:
    settings = get_settings()
    if not settings.otel_traces_enabled:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.namespace": "open-swe",
            }
        )
    )
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            headers=_parse_otlp_headers(settings.otel_exporter_otlp_headers),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def _init_langfuse() -> None:
    global _LANGFUSE_CLIENT
    settings = get_settings()
    if not settings.langfuse_enabled:
        return
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    kwargs: dict[str, Any] = {
        "public_key": settings.langfuse_public_key,
        "secret_key": settings.langfuse_secret_key,
    }
    if settings.langfuse_host:
        kwargs["host"] = settings.langfuse_host
    _LANGFUSE_CLIENT = Langfuse(**kwargs)


def init_observability(app: FastAPI | None = None) -> None:
    global _OBSERVABILITY_INITIALIZED
    if _OBSERVABILITY_INITIALIZED:
        return
    _init_otel(app)
    _init_langfuse()
    _OBSERVABILITY_INITIALIZED = True


@contextmanager
def start_trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    tracer = trace.get_tracer("open_swe.webapp")
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            span.set_attribute(key, value)
        yield


def record_langfuse_event(
    *, name: str, input_payload: dict[str, Any], metadata: dict[str, Any] | None = None
) -> None:
    if _LANGFUSE_CLIENT is None:
        return
    try:
        _LANGFUSE_CLIENT.trace(
            name=name,
            input=input_payload,
            metadata=metadata or {},
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to record Langfuse event", exc_info=True)
