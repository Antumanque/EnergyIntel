"""
Parser para datos JSON.

Este módulo provee funcionalidad para parsear y transformar datos JSON.
"""

import json
import logging
from typing import Any

from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class JSONParser(BaseParser):
    """
    Parser para datos JSON.

    Este parser convierte strings JSON a diccionarios Python y puede
    aplicar transformaciones opcionales.
    """

    def __init__(self, transform_fn: callable | None = None):
        """
        Inicializar el parser JSON.

        Args:
            transform_fn: Función opcional para transformar el dict parseado
        """
        super().__init__()
        self.transform_fn = transform_fn

    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear datos JSON.

        Args:
            data: String JSON o dict

        Returns:
            Diccionario con resultado del parseo
        """
        try:
            # If already a dict, use it directly
            if isinstance(data, dict):
                parsed_data = data
            # If string, parse as JSON
            elif isinstance(data, str):
                parsed_data = json.loads(data)
            # If bytes, decode and parse
            elif isinstance(data, bytes):
                parsed_data = json.loads(data.decode("utf-8"))
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            # Apply transformation if provided
            if self.transform_fn:
                parsed_data = self.transform_fn(parsed_data)

            return {
                "parsing_successful": True,
                "parsed_data": parsed_data,
                "error_message": None,
                "metadata": {"parser_type": "json"},
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"JSON decode error: {str(e)}",
                "metadata": {"parser_type": "json"},
            }

        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}", exc_info=True)
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"Unexpected error: {str(e)}",
                "metadata": {"parser_type": "json"},
            }
