"""
Structured JSON logging — LegalLens API
Implements: architecture.md §1 component 12 (structured logging, immutable audit trail).
code-standards.md: secrets never logged; LOG_LEVEL from config only.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure structlog for structured JSON output.
    Call once at application startup from main.py.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        shared_processors.append(structlog.processors.JSONRenderer())
        renderer = structlog.processors.JSONRenderer()
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs go through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a bound structlog logger. Use instead of logging.getLogger()."""
    return structlog.get_logger(name)
