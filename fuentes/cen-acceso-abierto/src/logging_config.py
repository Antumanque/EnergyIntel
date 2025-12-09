"""
Logging configuration using Loguru.

This module configures loguru and intercepts stdlib logging so all modules
get colored output automatically.

Usage:
    from src.logging_config import logger

    logger.info("This is green")
    logger.warning("This is yellow")
    logger.error("This is red")
"""

import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Handler that intercepts stdlib logging and routes to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    """
    Configure loguru with colored output and intercept stdlib logging.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default loguru handler
    logger.remove()

    # Add custom handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy libraries
    for noisy in ["httpx", "httpcore", "urllib3", "mysql.connector"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Auto-configure on import
setup_logging()

__all__ = ["logger", "setup_logging"]
