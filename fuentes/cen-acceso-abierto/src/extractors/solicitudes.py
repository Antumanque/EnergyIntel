"""
Extractor de solicitudes y documentos del CEN.

Este módulo implementa la lógica de extracción de datos desde la API del CEN:
1. Extrae solicitudes (tipo=6) por año
2. Extrae documentos (tipo=11) por solicitud_id
3. Filtra documentos de interés (SUCTD, SAC, Formulario_proyecto_fehaciente)
4. Guarda en base de datos con estrategia append-only
"""

import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from src.http_client import APIClient, get_api_client
from src.repositories.cen import CENDatabaseManager, get_cen_db_manager
from src.schemas.solicitud import validate_documento, validate_solicitud
from src.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Configuración de concurrencia
DEFAULT_CONCURRENCY = 10

# Estadísticas de validación
_validation_stats = {"solicitudes_valid": 0, "solicitudes_invalid": 0,
                     "documentos_valid": 0, "documentos_invalid": 0, "errors": []}


def reset_validation_stats():
    """Resetear estadísticas de validación."""
    global _validation_stats
    _validation_stats = {"solicitudes_valid": 0, "solicitudes_invalid": 0,
                         "documentos_valid": 0, "documentos_invalid": 0, "errors": []}


def get_validation_stats() -> dict:
    """Obtener estadísticas de validación."""
    return _validation_stats.copy()


def log_validation_summary():
    """Loguear resumen de validación."""
    stats = get_validation_stats()
    total_sol = stats["solicitudes_valid"] + stats["solicitudes_invalid"]
    total_doc = stats["documentos_valid"] + stats["documentos_invalid"]

    if total_sol > 0:
        pct = (stats["solicitudes_valid"] / total_sol) * 100
        if stats["solicitudes_invalid"] == 0:
            logger.info(f"✓ Validación Pydantic solicitudes: {stats['solicitudes_valid']}/{total_sol} válidas (100%)")
        else:
            logger.warning(f"⚠ Validación Pydantic solicitudes: {stats['solicitudes_valid']}/{total_sol} válidas ({pct:.1f}%)")

    if total_doc > 0:
        pct = (stats["documentos_valid"] / total_doc) * 100
        if stats["documentos_invalid"] == 0:
            logger.info(f"✓ Validación Pydantic documentos: {stats['documentos_valid']}/{total_doc} válidos (100%)")
        else:
            logger.warning(f"⚠ Validación Pydantic documentos: {stats['documentos_valid']}/{total_doc} válidos ({pct:.1f}%)")

    if stats["errors"]:
        for err in stats["errors"][:5]:
            logger.warning(f"  - {err}")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"


def flatten_documentos(documentos_by_solicitud: Dict[int, List[dict]]) -> List[dict]:
    """
    Convierte dict de {solicitud_id: [documentos]} a lista plana de documentos.

    Args:
        documentos_by_solicitud: Diccionario con documentos por solicitud

    Returns:
        Lista plana de documentos
    """
    all_documentos = []
    for solicitud_id, documentos in documentos_by_solicitud.items():
        all_documentos.extend(documentos)
    return all_documentos


class SolicitudesExtractor:
    """
    Extractor de datos del CEN Acceso Abierto.

    Coordina la extracción de solicitudes y documentos desde la API del CEN.
    Guarda todas las respuestas raw en raw_api_data para audit trail.
    """

    def __init__(self, settings: Settings, api_client: APIClient, db_manager: CENDatabaseManager):
        """
        Inicializa el extractor.

        Args:
            settings: Configuración de la aplicación
            api_client: Cliente HTTP para realizar requests
            db_manager: Gestor de base de datos CEN
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
        Extrae todas las solicitudes.

        NOTA: La API del CEN ignora el parámetro 'anio' y siempre retorna
        TODAS las solicitudes. El parámetro se mantiene por compatibilidad.

        Usa tipo=6 de la API del CEN.
        Guarda la respuesta raw en raw_api_data antes de procesarla.

        Args:
            anio: Año (ignorado por la API, se mantiene por compatibilidad)

        Returns:
            Tuple (success, solicitudes)
            - success: True si la extracción fue exitosa
            - solicitudes: Lista de diccionarios con datos de solicitudes
        """
        url = self.build_url(tipo=6, anio=anio, tipo_solicitud_id=0, solicitud_id=None)
        logger.info("📡 Extrayendo todas las solicitudes de la API...")

        status_code, data, error = self.api_client.fetch_url(url)

        # Guardar respuesta raw en base de datos (audit trail)
        if self.db_manager:
            self.db_manager.insert_raw_api_response(url, status_code, data, error)

        if status_code == 200 and data:
            if isinstance(data, list):
                logger.info(f"✅ {len(data)} solicitudes extraídas")
                return True, data
            else:
                logger.warning(f"⚠️ Respuesta inesperada (no es lista): {type(data)}")
                return False, []
        else:
            logger.error(f"❌ Error al extraer solicitudes: {error}")
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
        Extrae documentos para una lista de solicitud_ids (secuencial).

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

    async def _fetch_documentos_async(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        solicitud_id: int
    ) -> Tuple[int, bool, List[Dict[str, Any]]]:
        """
        Fetch documentos de una solicitud de forma asíncrona.

        Returns:
            Tupla (solicitud_id, success, documentos)
        """
        async with semaphore:
            url = self.build_url(tipo=11, anio=None, tipo_solicitud_id=None, solicitud_id=solicitud_id)

            try:
                fetch_start = time.perf_counter()
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "CEN-Acceso-Abierto-DataDumper/1.0",
                        "Accept": "application/json, text/plain, */*",
                    },
                    follow_redirects=True,
                )
                fetch_elapsed = time.perf_counter() - fetch_start

                if response.is_success:
                    try:
                        data = response.json()
                    except Exception:
                        data = []

                    if isinstance(data, list):
                        # Validar documentos
                        for doc in data[:3]:  # Validar primeros 3 como muestra
                            is_valid, _, error = validate_documento(doc)
                            if is_valid:
                                _validation_stats["documentos_valid"] += 1
                            else:
                                _validation_stats["documentos_invalid"] += 1
                                if len(_validation_stats["errors"]) < 10:
                                    _validation_stats["errors"].append(f"Doc {doc.get('id')}: {error}")

                        # Guardar raw response si hay db_manager
                        if self.db_manager:
                            self.db_manager.insert_raw_api_response(url, response.status_code, data, None)
                        return solicitud_id, True, data
                    else:
                        return solicitud_id, False, []
                else:
                    logger.warning(f"Solicitud {solicitud_id}: HTTP {response.status_code}")
                    return solicitud_id, False, []

            except httpx.TimeoutException:
                logger.warning(f"Solicitud {solicitud_id}: timeout")
                return solicitud_id, False, []
            except Exception as e:
                logger.warning(f"Solicitud {solicitud_id}: error {e}")
                return solicitud_id, False, []

    async def extract_documentos_parallel_async(
        self,
        solicitud_ids: List[int],
        concurrency: int = DEFAULT_CONCURRENCY
    ) -> Dict[str, Any]:
        """
        Extrae documentos en paralelo para una lista de solicitud_ids.

        Args:
            solicitud_ids: Lista de IDs de solicitudes
            concurrency: Número de requests paralelos

        Returns:
            Diccionario con resultados
        """
        results = {
            "total_solicitudes": len(solicitud_ids),
            "successful_solicitudes": 0,
            "total_documentos": 0,
            "documentos_importantes": 0,
            "documentos_by_solicitud": {},
        }

        if not solicitud_ids:
            return results

        logger.info(
            f"📡 Extrayendo documentos de {len(solicitud_ids)} solicitudes "
            f"(concurrencia: {concurrency})..."
        )

        semaphore = asyncio.Semaphore(concurrency)
        batch_size = concurrency

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            # Procesar en batches para mostrar progreso
            for batch_start in range(0, len(solicitud_ids), batch_size):
                batch_ids = solicitud_ids[batch_start:batch_start + batch_size]
                batch_num = (batch_start // batch_size) + 1
                total_batches = math.ceil(len(solicitud_ids) / batch_size)

                batch_start_time = time.perf_counter()

                # Lanzar requests del batch en paralelo
                tasks = [
                    self._fetch_documentos_async(client, semaphore, sid)
                    for sid in batch_ids
                ]
                batch_results = await asyncio.gather(*tasks)

                batch_elapsed = time.perf_counter() - batch_start_time

                # Procesar resultados del batch
                batch_docs = 0
                batch_important = 0
                batch_success = 0

                for solicitud_id, success, documentos in batch_results:
                    if success:
                        batch_success += 1
                        results["successful_solicitudes"] += 1
                        results["total_documentos"] += len(documentos)
                        batch_docs += len(documentos)

                        # Filtrar documentos importantes
                        documentos_importantes = self.filter_documentos_importantes(documentos)
                        results["documentos_importantes"] += len(documentos_importantes)
                        batch_important += len(documentos_importantes)
                        results["documentos_by_solicitud"][solicitud_id] = documentos_importantes
                    else:
                        results["documentos_by_solicitud"][solicitud_id] = []

                # Log de progreso cada batch
                processed = min(batch_start + batch_size, len(solicitud_ids))
                logger.info(
                    f"BATCH {batch_num}/{total_batches}: "
                    f"{batch_success}/{len(batch_ids)} OK, "
                    f"{batch_important} docs importantes "
                    f"(took {format_duration(batch_elapsed)}, "
                    f"total: {processed}/{len(solicitud_ids)})"
                )

        logger.info(
            f"📊 Extracción paralela completada: "
            f"{results['successful_solicitudes']}/{results['total_solicitudes']} solicitudes, "
            f"{results['documentos_importantes']} documentos importantes"
        )

        # Loguear resumen de validación
        log_validation_summary()

        return results

    def extract_documentos_parallel(
        self,
        solicitud_ids: List[int],
        concurrency: int = DEFAULT_CONCURRENCY
    ) -> Dict[str, Any]:
        """
        Wrapper síncrono para extract_documentos_parallel_async.
        """
        reset_validation_stats()  # Reset antes de nueva extracción
        return asyncio.run(self.extract_documentos_parallel_async(solicitud_ids, concurrency))

    def run(self) -> int:
        """
        Ejecuta el flujo completo de extracción de solicitudes y documentos.

        Returns:
            Código de salida (0 = éxito, 1 = error)
        """
        logger.info("=" * 70)
        logger.info("🚀 INICIANDO EXTRACCIÓN CEN ACCESO ABIERTO")
        logger.info("=" * 70)

        try:
            # Cargar configuración
            logger.info("\n📋 Configuración:")
            logger.info(f"  Base URL: {self.settings.cen_api_base_url}")
            logger.info(f"  Años a procesar: {self.settings.cen_years_list}")
            logger.info(f"  Tipos de documento: {self.settings.cen_document_types_list}")

            # Verificar conexión a base de datos
            logger.info("\n🔌 Verificando conexión a base de datos...")
            if not self.db_manager.test_connection():
                logger.error("❌ No se pudo conectar a la base de datos. Abortando.")
                return 1

            # PASO 1: Extraer solicitudes
            logger.info("\n" + "=" * 70)
            logger.info("PASO 1: EXTRACCIÓN DE SOLICITUDES")
            logger.info("=" * 70)

            solicitudes_results = self.extract_all_years()

            if solicitudes_results["total_solicitudes"] == 0:
                logger.warning("⚠️ No se extrajeron solicitudes. Abortando.")
                return 1

            # Aplanar solicitudes de todos los años
            all_solicitudes = []
            for anio, solicitudes in solicitudes_results["solicitudes_by_year"].items():
                all_solicitudes.extend(solicitudes)

            # Deduplicar por ID (la API retorna las mismas solicitudes para todos los años)
            logger.info(f"📊 Total solicitudes recolectadas (con duplicados): {len(all_solicitudes)}")
            unique_solicitudes_dict = {s["id"]: s for s in all_solicitudes}
            all_solicitudes = list(unique_solicitudes_dict.values())
            logger.info(f"📊 Solicitudes únicas después de deduplicar: {len(all_solicitudes)}")

            logger.info(f"\n📥 Guardando {len(all_solicitudes)} solicitudes en la base de datos...")
            inserted_solicitudes = self.db_manager.insert_solicitudes_bulk(all_solicitudes)
            logger.info(f"✅ {inserted_solicitudes} solicitudes nuevas insertadas")

            # PASO 2: Extraer documentos
            logger.info("\n" + "=" * 70)
            logger.info("PASO 2: EXTRACCIÓN DE DOCUMENTOS")
            logger.info("=" * 70)

            # Obtener IDs de todas las solicitudes extraídas
            solicitud_ids = [s["id"] for s in all_solicitudes]
            logger.info(f"📋 Procesando documentos de {len(solicitud_ids)} solicitudes...")

            documentos_results = self.extract_documentos_for_solicitudes(solicitud_ids)

            if documentos_results["documentos_importantes"] == 0:
                logger.warning("⚠️ No se encontraron documentos importantes.")
            else:
                # Aplanar documentos
                all_documentos = flatten_documentos(documentos_results["documentos_by_solicitud"])

                logger.info(f"\n📥 Guardando {len(all_documentos)} documentos en la base de datos...")
                inserted_documentos = self.db_manager.insert_documentos_bulk(all_documentos)
                logger.info(f"✅ {inserted_documentos} documentos nuevos insertados")

            # PASO 3: Mostrar estadísticas finales
            logger.info("\n" + "=" * 70)
            logger.info("📊 ESTADÍSTICAS FINALES")
            logger.info("=" * 70)

            stats = self.db_manager.get_stats()
            logger.info(f"  Total solicitudes en BD: {stats.get('total_solicitudes', 0)}")
            logger.info(f"  Total documentos en BD: {stats.get('total_documentos', 0)}")
            logger.info(f"    - Formulario SUCTD: {stats.get('docs_suctd', 0)}")
            logger.info(f"    - Formulario SAC: {stats.get('docs_sac', 0)}")
            logger.info(f"    - Formulario_proyecto_fehaciente: {stats.get('docs_fehaciente', 0)}")
            logger.info(f"  Total raw API responses: {stats.get('total_raw_responses', 0)}")

            logger.info("\n" + "=" * 70)
            logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
            logger.info("=" * 70)

            return 0

        except KeyboardInterrupt:
            logger.warning("\n⚠️ Proceso interrumpido por el usuario")
            return 1
        except Exception as e:
            logger.error(f"\n❌ Error inesperado: {e}", exc_info=True)
            return 1


def get_solicitudes_extractor(
    settings: Settings = None,
    api_client: APIClient = None,
    db_manager: CENDatabaseManager = None,
) -> SolicitudesExtractor:
    """
    Factory function para crear instancia del extractor.

    Args:
        settings: Configuración (si None, se carga automáticamente)
        api_client: Cliente HTTP (si None, se crea automáticamente)
        db_manager: Gestor de BD CEN (si None, se crea automáticamente)

    Returns:
        Instancia de SolicitudesExtractor
    """
    if settings is None:
        settings = get_settings()
    if api_client is None:
        api_client = get_api_client(settings)
    if db_manager is None:
        db_manager = get_cen_db_manager()

    return SolicitudesExtractor(settings, api_client, db_manager)
