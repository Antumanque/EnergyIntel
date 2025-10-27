"""
Clase base abstracta para extractores de datos.

Este módulo define la interfaz que todos los extractores deben implementar.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.settings import Settings

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Clase base abstracta para extractores de datos.

    Todos los extractores concretos (API REST, web scraping, file download, etc.)
    deben heredar de esta clase e implementar el método extract().
    """

    def __init__(self, settings: Settings):
        """
        Inicializar el extractor con settings.

        Args:
            settings: Settings de aplicación
        """
        self.settings = settings
        self.results: list[dict[str, Any]] = []

    @abstractmethod
    def extract(self) -> list[dict[str, Any]]:
        """
        Extraer datos desde la fuente.

        Este método debe ser implementado por cada extractor concreto.

        Returns:
            Lista de diccionarios con los datos extraídos. Cada dict debe tener
            al menos las siguientes keys:
            - source_url: URL o identificador de la fuente
            - status_code: Código de status (HTTP code o custom code)
            - data: Los datos extraídos (puede ser dict, str, bytes, etc.)
            - error_message: Mensaje de error si hubo fallo, None sino
            - extracted_at: Timestamp de cuando se extrajo (ISO format)

        Example:
            [
                {
                    "source_url": "https://api.example.com/data",
                    "status_code": 200,
                    "data": {"key": "value"},
                    "error_message": None,
                    "extracted_at": "2025-10-24T12:00:00Z"
                }
            ]
        """
        pass

    def validate_result(self, result: dict[str, Any]) -> bool:
        """
        Validar que un resultado tenga los campos requeridos.

        Args:
            result: Diccionario de resultado a validar

        Returns:
            True si es válido, False sino
        """
        required_fields = ["source_url", "status_code", "data", "error_message", "extracted_at"]
        return all(field in result for field in required_fields)

    def log_summary(self) -> None:
        """
        Loggear un resumen de los resultados de extracción.
        """
        if not self.results:
            logger.info("No results to summarize")
            return

        total = len(self.results)
        successful = sum(1 for r in self.results if r.get("error_message") is None)
        failed = total - successful

        logger.info("=" * 60)
        logger.info(f"EXTRACTION SUMMARY - {self.__class__.__name__}")
        logger.info("=" * 60)
        logger.info(f"Total extractions: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")

        if failed > 0:
            logger.info("\nFailed sources:")
            for result in self.results:
                if result.get("error_message"):
                    logger.info(f"  - {result['source_url']}")
                    logger.info(f"    Error: {result['error_message']}")

        logger.info("=" * 60)
