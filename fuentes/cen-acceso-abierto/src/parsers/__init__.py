"""
Parsers module for transforming JSON data to database models.

This module contains parsers for different CEN data types.
"""

from src.parsers.interesados import transform_interesados
from src.parsers.solicitudes import (
    parse_solicitud,
    parse_documento,
)

__all__ = [
    "transform_interesados",
    "parse_solicitud",
    "parse_documento",
]
