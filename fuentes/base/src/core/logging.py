"""
Configuración de logging para la aplicación.

Este módulo provee un setup centralizado de logging con soporte para
múltiples handlers (consola y archivo).
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    log_format: str | None = None,
) -> logging.Logger:
    """
    Configurar logging para la aplicación.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Ruta opcional de archivo para logging
        log_format: Formato opcional de log (usa default si None)

    Returns:
        Logger configurado
    """
    # Default log format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())

    # Clear existing handlers
    logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level.upper())
    console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Create file handler if log_file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level.upper())
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtener un logger con nombre específico.

    Args:
        name: Nombre del logger (usualmente __name__ del módulo)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
