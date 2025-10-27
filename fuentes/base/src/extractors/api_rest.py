"""
Extractor para APIs REST.

Este módulo provee funcionalidad para extraer datos desde APIs REST.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.core.http_client import get_http_client
from src.extractors.base import BaseExtractor
from src.settings import Settings

logger = logging.getLogger(__name__)


class APIRestExtractor(BaseExtractor):
    """
    Extractor para APIs REST.

    Este extractor fetchea datos desde múltiples URLs de API REST y
    retorna los resultados en formato estandarizado.
    """

    def __init__(self, settings: Settings, urls: list[str] | None = None):
        """
        Inicializar el extractor REST API.

        Args:
            settings: Settings de aplicación
            urls: Lista opcional de URLs a extraer (usa settings.api_urls si None)
        """
        super().__init__(settings)
        self.urls = urls or settings.api_urls
        self.http_client = get_http_client(settings)

    def extract(self) -> list[dict[str, Any]]:
        """
        Extraer datos desde las URLs de API REST configuradas.

        Returns:
            Lista de diccionarios con los datos extraídos
        """
        if not self.urls:
            logger.warning("No API URLs configured for extraction")
            return []

        logger.info(f"Starting API REST extraction for {len(self.urls)} URL(s)")

        self.results = []

        for url in self.urls:
            result = self._extract_single_url(url)
            self.results.append(result)

        self.log_summary()
        return self.results

    def _extract_single_url(self, url: str) -> dict[str, Any]:
        """
        Extraer datos desde una sola URL.

        Args:
            url: URL a extraer

        Returns:
            Diccionario con el resultado de la extracción
        """
        logger.info(f"Extracting from: {url}")

        # Fetch the data
        status_code, data, error_message = self.http_client.fetch_url(url)

        # Build result
        result = {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        if error_message:
            logger.error(f"Failed to extract from {url}: {error_message}")
        else:
            logger.info(f"Successfully extracted from {url}")

        return result
