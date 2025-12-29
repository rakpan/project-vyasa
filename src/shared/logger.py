"""
Centralized logging utilities for Project Vyasa services.

Provides a consistent log format and stdout handler so Docker captures output.
Format: ``Timestamp - Service - Level - Message``.
"""

import logging
import sys
from typing import Optional

LOG_FORMAT = "%(asctime)s - %(service)s - %(levelname)s - %(message)s"


class ServiceFilter(logging.Filter):
    """Injects the service name into log records."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self.service_name
        return True


def get_logger(service_name: str, name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger that writes to stdout with a consistent format.

    Args:
        service_name: Logical service identifier (e.g., "orchestrator", "ingestion").
        name: Optional logger name; defaults to service_name.
        level: Logging level; defaults to INFO.
    """
    logger_name = name or service_name
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.addFilter(ServiceFilter(service_name))
        logger.addHandler(handler)

    return logger
