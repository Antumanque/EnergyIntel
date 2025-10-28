"""
Extractor para documentos del expediente (EIA/DIA).

Este módulo extrae la lista de documentos asociados a un expediente,
específicamente buscando el documento principal EIA o DIA.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.core.http_client import HTTPClient
from src.settings import Settings

logger = logging.getLogger(__name__)


class ExpedienteDocumentosExtractor:
    """
    Extractor para documentos del expediente.

    Obtiene la lista de documentos de un expediente desde el endpoint
    xhr_busqueda_expediente.php y extrae información del documento EIA/DIA.
    """

    def __init__(self, http_client: HTTPClient):
        """
        Inicializar el extractor.

        Args:
            http_client: Cliente HTTP para hacer requests
        """
        self.http_client = http_client
        self.base_url = "https://seia.sea.gob.cl/expediente"

    def extract_documentos(self, expediente_id: int) -> dict[str, Any]:
        """
        Extraer documentos de un expediente.

        Args:
            expediente_id: ID del expediente a consultar

        Returns:
            Diccionario con metadata de extracción y HTML de la respuesta
        """
        url = f"{self.base_url}/xhr_busqueda_expediente.php?id_expediente={expediente_id}"

        logger.debug(f"Extrayendo documentos de expediente {expediente_id}")

        # Hacer request
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
            "expediente_id": expediente_id,
            "url": url,
            "status_code": status_code,
            "html_content": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        }

    def extract_batch(
        self, expedientes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Extraer documentos de múltiples expedientes en batch.

        Args:
            expedientes: Lista de diccionarios con datos de expedientes (debe incluir expediente_id)

        Returns:
            Lista de resultados de extracción
        """
        results = []

        for i, exp in enumerate(expedientes, 1):
            expediente_id = exp.get("expediente_id")
            if not expediente_id:
                logger.warning(f"Expediente {i} no tiene expediente_id, saltando")
                continue

            try:
                result = self.extract_documentos(expediente_id)
                results.append(result)

                if i % 10 == 0:
                    logger.info(f"Extraídos documentos de {i}/{len(expedientes)} expedientes")

            except Exception as e:
                logger.error(
                    f"Error extrayendo documentos de expediente {expediente_id}: {e}"
                )
                results.append({
                    "expediente_id": expediente_id,
                    "url": f"{self.base_url}/xhr_busqueda_expediente.php?id_expediente={expediente_id}",
                    "status_code": 0,
                    "html_content": None,
                    "error_message": str(e),
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                })

        logger.info(
            f"Extracción de documentos completada: {len(results)} expedientes procesados"
        )
        return results


def get_expediente_documentos_extractor(
    http_client: HTTPClient,
) -> ExpedienteDocumentosExtractor:
    """
    Factory function para crear una instancia de ExpedienteDocumentosExtractor.

    Args:
        http_client: Cliente HTTP

    Returns:
        Instancia configurada de ExpedienteDocumentosExtractor
    """
    return ExpedienteDocumentosExtractor(http_client)
