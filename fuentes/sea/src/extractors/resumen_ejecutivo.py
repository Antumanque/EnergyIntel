"""
Extractor para links del Resumen Ejecutivo (Capítulo 20).

Este módulo extrae el link al PDF del Resumen Ejecutivo desde la página
del documento EIA/DIA.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.core.http_client import HTTPClient

logger = logging.getLogger(__name__)


class ResumenEjecutivoExtractor:
    """
    Extractor para links de Resumen Ejecutivo.

    Obtiene el HTML de la página del documento EIA/DIA y extrae el link
    al PDF del Capítulo 20 - Resumen Ejecutivo.
    """

    def __init__(self, http_client: HTTPClient):
        """
        Inicializar el extractor.

        Args:
            http_client: Cliente HTTP para hacer requests
        """
        self.http_client = http_client
        self.base_url = "https://seia.sea.gob.cl/documentos"

    def extract_documento_content(self, id_documento: int) -> dict[str, Any]:
        """
        Extraer contenido HTML del documento EIA/DIA.

        Args:
            id_documento: ID del documento a consultar

        Returns:
            Diccionario con metadata de extracción y HTML de la respuesta
        """
        url = f"{self.base_url}/documento.php?idDocumento={id_documento}"

        logger.debug(f"Extrayendo contenido de documento {id_documento}")

        # Hacer request (follow redirects)
        status_code, data, error_message = self.http_client.fetch_url(
            url=url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        )

        # Retornar resultado estandarizado
        return {
            "id_documento": id_documento,
            "url": url,
            "status_code": status_code,
            "html_content": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        }

    def extract_batch(
        self, documentos: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Extraer contenido de múltiples documentos en batch.

        Args:
            documentos: Lista de diccionarios con datos de documentos (debe incluir id_documento)

        Returns:
            Lista de resultados de extracción
        """
        results = []

        for i, doc in enumerate(documentos, 1):
            id_documento = doc.get("id_documento")
            if not id_documento:
                logger.warning(f"Documento {i} no tiene id_documento, saltando")
                continue

            try:
                result = self.extract_documento_content(id_documento)
                results.append(result)

                if i % 10 == 0:
                    logger.info(f"Extraídos {i}/{len(documentos)} documentos")

            except Exception as e:
                logger.error(
                    f"Error extrayendo documento {id_documento}: {e}"
                )
                results.append({
                    "id_documento": id_documento,
                    "url": f"{self.base_url}/documento.php?idDocumento={id_documento}",
                    "status_code": 0,
                    "html_content": None,
                    "error_message": str(e),
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                })

        logger.info(
            f"Extracción de documentos completada: {len(results)} documentos procesados"
        )
        return results


def get_resumen_ejecutivo_extractor(
    http_client: HTTPClient,
) -> ResumenEjecutivoExtractor:
    """
    Factory function para crear una instancia de ResumenEjecutivoExtractor.

    Args:
        http_client: Cliente HTTP

    Returns:
        Instancia configurada de ResumenEjecutivoExtractor
    """
    return ResumenEjecutivoExtractor(http_client)
