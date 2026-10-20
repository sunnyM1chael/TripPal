import logging
import sys

import structlog


def configure_logging(level: str, *, stream=None) -> None:
    output = sys.stdout if stream is None else stream
    logging.basicConfig(format="%(message)s", stream=output, level=level, force=True)
    # Map API credentials are query parameters. Never emit httpx URLs in application logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared_processors, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=True,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger().bind(component=component)

