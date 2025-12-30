"""
Centralized logging utilities for Project Vyasa services.

Supports both JSON (production) and text (development) log formats.
JSON format is required in Docker/production for easy parsing by log aggregation tools.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _effective_format() -> str:
    return os.getenv("LOG_FORMAT", "text").lower()
LOG_FORMAT_TEXT = "%(asctime)s - %(service)s - %(levelname)s - %(message)s"


class ServiceFilter(logging.Filter):
    """Injects the service name into log records."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self.service_name
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in production.
    
    Promotes keys from extra={"payload": {...}} or extra={"project_id": ...}
    to top-level JSON fields for easy filtering.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": getattr(record, "service", "unknown"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Promote extra fields to top-level
        if hasattr(record, "payload") and isinstance(record.payload, dict):
            # Merge payload into top-level (for easy filtering)
            log_data.update(record.payload)
        else:
            # Check for common extra keys
            for key in ["project_id", "job_id", "document_id", "error", "duration_ms"]:
                if hasattr(record, key):
                    value = getattr(record, key)
                    if value is not None:
                        log_data[key] = value
        
        # Add any other extra fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in [
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "message", "pathname", "process", "processName", "relativeCreated",
                    "thread", "threadName", "exc_info", "exc_text", "stack_info",
                    "service", "payload"
                ]:
                    if not key.startswith("_"):
                        log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False)


def get_logger(service_name: str, name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger that writes to stdout with consistent format.
    
    Format is determined by LOG_FORMAT environment variable:
    - "json" (default in Docker): Structured JSON logs for production
    - "text": Human-readable text logs for development
    
    Args:
        service_name: Logical service identifier (e.g., "orchestrator", "ingestion").
        name: Optional logger name; defaults to service_name.
        level: Logging level; defaults to INFO.
    
    Example (JSON format):
        logger.info("Event happened", extra={"payload": {"project_id": "123", "data": "..."}})
        # Output: {"timestamp": "...", "service": "orchestrator", "level": "INFO", "message": "Event happened", "project_id": "123", "data": "..."}
    
    Example (Text format):
        logger.info("Event happened", extra={"payload": {"project_id": "123"}})
        # Output: 2024-01-15 10:30:00 - orchestrator - INFO - Event happened
    """
    logger_name = name or service_name
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    eff_format = _effective_format()

    if logger.handlers:
        # Reconfigure if format changed
        logger.handlers = []

    handler = logging.StreamHandler(sys.stdout)
    if eff_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(LOG_FORMAT_TEXT))
    
    handler.addFilter(ServiceFilter(service_name))
    logger.addHandler(handler)

    return logger
