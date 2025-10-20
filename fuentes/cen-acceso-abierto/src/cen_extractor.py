"""
Extractor de solicitudes y documentos del CEN.

Este módulo implementa la lógica de extracción de datos desde la API del CEN:
1. Extrae solicitudes (tipo=6) por año
2. Extrae documentos (tipo=11) por solicitud_id
3. Filtra documentos de interés (SUCTD, SAC, Formulario_proyecto_fehaciente)
4. Guarda en base de datos con estrategia append-only
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from src.client import APIClient
from src.settings import Settings

logger = logging.getLogger(__name__)


class CENExtractor:
    """
    Extractor de datos del CEN Acceso Abierto.

    Coordina la extracción de solicitudes y documentos desde la API del CEN.
    Guarda todas las respuestas raw en raw_api_data para audit trail.
    """

    def __init__(self, settings: Settings, api_client: APIClient, db_manager=None):
        """
        Inicializa el extractor.

        Args:
            settings: Configuración de la aplicación
            api_client: Cliente HTTP para realizar requests
            db_manager: Gestor de base de datos (opcional, para guardar raw responses)
        """
        self.settings = settings
        self.api_client = api_client
        self.base_url = settings.cen_api_base_url
        self.db_manager = db_manager

    def build_url(self, tipo: int, anio: Optional[int] = None,
                  tipo_solicitud_id: Optional[int] = 0,
                  solicitud_id: Optional[int] = None) -> str:
        """
        Construye URL con parámetros para la API del CEN.

        Args:
            tipo: Tipo de endpoint (0-11)
            anio: Año de las solicitudes (None para 'null')
            tipo_solicitud_id: ID del tipo de solicitud (None para 'null')
            solicitud_id: ID de la solicitud específica (None para 'null')

        Returns:
            URL completa con parámetros
        """
        params = {
            "tipo": tipo,
            "anio": anio if anio is not None else "null",
            "tipo_solicitud_id": tipo_solicitud_id if tipo_solicitud_id is not None else "null",
            "solicitud_id": solicitud_id if solicitud_id is not None else "null",
        }
        query_string = urlencode(params)
        return f"{self.base_url}?{query_string}"

    def fetch_solicitudes_by_year(self, anio: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Extrae todas las solicitudes de un año específico.

        Usa tipo=6 de la API del CEN.
        Guarda la respuesta raw en raw_api_data antes de procesarla.

        Args:
            anio: Año a extraer (ej: 2025)

        Returns:
            Tuple (success, solicitudes)
            - success: True si la extracción fue exitosa
            - solicitudes: Lista de diccionarios con datos de solicitudes
        """
        url = self.build_url(tipo=6, anio=anio, tipo_solicitud_id=0, solicitud_id=None)
        logger.info(f"📡 Extrayendo solicitudes del año {anio}...")

        status_code, data, error = self.api_client.fetch_url(url)

        # Guardar respuesta raw en base de datos (audit trail)
        if self.db_manager:
            self.db_manager.insert_raw_api_response(url, status_code, data, error)

        if status_code == 200 and data:
            if isinstance(data, list):
                logger.info(f"✅ {len(data)} solicitudes extraídas para el año {anio}")
                return True, data
            else:
                logger.warning(f"⚠️ Respuesta inesperada (no es lista): {type(data)}")
                return False, []
        else:
            logger.error(f"❌ Error al extraer solicitudes del año {anio}: {error}")
            return False, []

    def fetch_documentos_by_solicitud(self, solicitud_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Extrae todos los documentos de una solicitud específica.

        Usa tipo=11 de la API del CEN.
        Guarda la respuesta raw en raw_api_data antes de procesarla.

        Args:
            solicitud_id: ID de la solicitud

        Returns:
            Tuple (success, documentos)
            - success: True si la extracción fue exitosa
            - documentos: Lista de diccionarios con datos de documentos
        """
        url = self.build_url(tipo=11, anio=None, tipo_solicitud_id=None, solicitud_id=solicitud_id)

        status_code, data, error = self.api_client.fetch_url(url)

        # Guardar respuesta raw en base de datos (audit trail)
        if self.db_manager:
            self.db_manager.insert_raw_api_response(url, status_code, data, error)

        if status_code == 200 and data:
            if isinstance(data, list):
                return True, data
            else:
                logger.warning(f"⚠️ Respuesta inesperada para solicitud {solicitud_id} (no es lista): {type(data)}")
                return False, []
        else:
            logger.error(f"❌ Error al extraer documentos de solicitud {solicitud_id}: {error}")
            return False, []

    def filter_documentos_importantes(self, documentos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra documentos por tipo_documento de interés.

        Solo retorna documentos que sean:
        - Formulario SUCTD
        - Formulario SAC
        - Formulario_proyecto_fehaciente

        Args:
            documentos: Lista completa de documentos

        Returns:
            Lista filtrada de documentos importantes
        """
        tipos_interes = set(self.settings.cen_document_types_list)

        documentos_filtrados = [
            d for d in documentos
            if d.get("tipo_documento") in tipos_interes
        ]

        logger.debug(
            f"📄 Filtrados {len(documentos_filtrados)}/{len(documentos)} documentos "
            f"(tipos: {', '.join(tipos_interes)})"
        )

        return documentos_filtrados

    def extract_all_years(self) -> Dict[str, Any]:
        """
        Extrae solicitudes de todos los años configurados.

        Returns:
            Diccionario con resultados:
            {
                "total_years": int,
                "successful_years": int,
                "total_solicitudes": int,
                "solicitudes_by_year": {anio: [solicitudes]}
            }
        """
        years = self.settings.cen_years_list
        results = {
            "total_years": len(years),
            "successful_years": 0,
            "total_solicitudes": 0,
            "solicitudes_by_year": {},
        }

        for anio in years:
            success, solicitudes = self.fetch_solicitudes_by_year(anio)

            if success:
                results["successful_years"] += 1
                results["total_solicitudes"] += len(solicitudes)
                results["solicitudes_by_year"][anio] = solicitudes
            else:
                results["solicitudes_by_year"][anio] = []

        logger.info(
            f"📊 Resumen extracción: {results['successful_years']}/{results['total_years']} años, "
            f"{results['total_solicitudes']} solicitudes totales"
        )

        return results

    def extract_documentos_for_solicitudes(
        self, solicitud_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Extrae documentos para una lista de solicitud_ids.

        Args:
            solicitud_ids: Lista de IDs de solicitudes

        Returns:
            Diccionario con resultados:
            {
                "total_solicitudes": int,
                "successful_solicitudes": int,
                "total_documentos": int,
                "documentos_importantes": int,
                "documentos_by_solicitud": {solicitud_id: [documentos]}
            }
        """
        results = {
            "total_solicitudes": len(solicitud_ids),
            "successful_solicitudes": 0,
            "total_documentos": 0,
            "documentos_importantes": 0,
            "documentos_by_solicitud": {},
        }

        logger.info(f"📡 Extrayendo documentos de {len(solicitud_ids)} solicitudes...")

        for i, solicitud_id in enumerate(solicitud_ids, 1):
            # Log de progreso cada 10 solicitudes
            if i % 10 == 0:
                logger.info(f"  Progreso: {i}/{len(solicitud_ids)} solicitudes procesadas")

            success, documentos = self.fetch_documentos_by_solicitud(solicitud_id)

            if success:
                results["successful_solicitudes"] += 1
                results["total_documentos"] += len(documentos)

                # Filtrar solo documentos importantes
                documentos_importantes = self.filter_documentos_importantes(documentos)
                results["documentos_importantes"] += len(documentos_importantes)
                results["documentos_by_solicitud"][solicitud_id] = documentos_importantes
            else:
                results["documentos_by_solicitud"][solicitud_id] = []

        logger.info(
            f"📊 Resumen extracción documentos: "
            f"{results['successful_solicitudes']}/{results['total_solicitudes']} solicitudes, "
            f"{results['documentos_importantes']} documentos importantes de {results['total_documentos']} totales"
        )

        return results


def get_cen_extractor(settings: Settings, api_client: APIClient, db_manager=None) -> CENExtractor:
    """
    Factory function para crear instancia del extractor.

    Args:
        settings: Configuración de la aplicación
        api_client: Cliente HTTP
        db_manager: Gestor de BD (opcional, para guardar raw responses)

    Returns:
        Instancia de CENExtractor
    """
    return CENExtractor(settings, api_client, db_manager)
