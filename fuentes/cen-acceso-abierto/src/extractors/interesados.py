"""
Extractor de datos de interesados (stakeholders) del CEN.

Este módulo maneja la extracción completa desde el endpoint /interesados.
"""

import logging
import sys
from typing import Any, Dict, List

from src.http_client import APIClient, get_api_client
from src.parsers.interesados import transform_interesados
from src.repositories.base import DatabaseManager, get_database_manager
from src.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class InteresadosExtractor:
    """
    Extractor para el endpoint /interesados del CEN.

    Maneja la extracción, transformación y carga de datos de stakeholders.
    """

    def __init__(
        self,
        settings: Settings,
        api_client: APIClient,
        db_manager: DatabaseManager,
    ):
        """
        Inicializa el extractor.

        Args:
            settings: Configuración de la aplicación
            api_client: Cliente HTTP para realizar requests
            db_manager: Gestor de base de datos
        """
        self.settings = settings
        self.api_client = api_client
        self.db_manager = db_manager
        self.results: Dict[str, dict] = {}

    def setup_database(self) -> None:
        """
        Configura la conexión a la base de datos y crea las tablas necesarias.

        Este método es idempotente - puede ser llamado múltiples veces de forma segura.
        """
        logger.info("Setting up database for interesados...")
        try:
            # Asegurar que podemos conectar
            self.db_manager.get_connection()

            # Crear tablas si no existen
            self.db_manager.create_tables()

            logger.info("Database setup completed successfully")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise

    def fetch_and_store_url(self, url: str) -> dict:
        """
        Obtiene datos de una URL y los almacena en la base de datos.

        Args:
            url: URL del endpoint /interesados

        Returns:
            Diccionario con resultado de la operación
        """
        logger.info(f"Processing URL: {url}")

        # Obtener los datos
        status_code, data, error = self.api_client.fetch_url(url)

        # Preparar metadata del resultado
        result = {
            "url": url,
            "status_code": status_code,
            "success": error is None,
            "error": error,
        }

        # Guardar en base de datos
        try:
            row_id = self.db_manager.insert_raw_data(
                source_url=url, status_code=status_code, data=data, error_message=error
            )
            result["row_id"] = row_id
            logger.info(f"Successfully processed {url} (row_id: {row_id})")

            # Transformar y normalizar datos si fue exitoso
            if result["success"] and data:
                self._transform_and_save(data, row_id, result)

        except Exception as e:
            result["success"] = False
            result["error"] = f"Database insert failed: {str(e)}"
            logger.error(f"Failed to store data from {url}: {e}")

        return result

    def _transform_and_save(
        self, data: Any, raw_data_id: int, result: dict
    ) -> None:
        """
        Transforma datos raw a tablas normalizadas.

        ESTRATEGIA DE NORMALIZACIÓN:
        - Transforma datos raw a formato normalizado
        - SOLO inserta registros NUEVOS (append-only)
        - Mantiene historial completo (no elimina registros antiguos)

        Args:
            data: Datos raw del API
            raw_data_id: ID del registro raw_api_data
            result: Diccionario de resultado para actualizar
        """
        try:
            logger.info("Transforming interesados data...")

            # PASO 1: Transformar JSON raw a lista de registros normalizados
            records = transform_interesados(data)

            if records:
                # PASO 2: Insertar SOLO registros nuevos
                affected = self.db_manager.insert_interesados_bulk(
                    records, raw_data_id=raw_data_id
                )
                result["transformed"] = True
                result["transformed_records"] = affected

                if affected > 0:
                    logger.info(
                        f"Inserted {affected} NEW interesados records "
                        f"(skipped {len(records) - affected} existing)"
                    )
                else:
                    logger.info("All records already exist, none inserted")
            else:
                logger.warning("No records to transform")
                result["transformed"] = False

        except Exception as e:
            logger.error(f"Transformation failed: {e}", exc_info=True)
            result["transformation_error"] = str(e)
            # No fallar todo el proceso si falla la transformación
            # Los datos raw ya están guardados de forma segura

    def process_all_urls(self) -> None:
        """
        Procesa todas las URLs configuradas de forma secuencial.

        Este método obtiene y almacena datos de cada URL en la configuración.
        Los errores de URLs individuales no detienen el proceso general.
        """
        urls = self.settings.api_urls

        if not urls:
            logger.warning(
                "No API URLs configured. Please set API_URL_1, API_URL_2, etc."
            )
            return

        logger.info(f"Processing {len(urls)} URL(s)...")

        for url in urls:
            result = self.fetch_and_store_url(url)
            self.results[url] = result

        logger.info("All URLs processed")

    def print_summary(self) -> None:
        """
        Imprime un resumen de los resultados de la ingesta.
        """
        if not self.results:
            logger.info("No results to summarize")
            return

        total = len(self.results)
        successful = sum(1 for r in self.results.values() if r["success"])
        failed = total - successful
        transformed = sum(
            1 for r in self.results.values() if r.get("transformed", False)
        )

        logger.info("=" * 60)
        logger.info("INTERESADOS EXTRACTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total URLs processed: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Transformed: {transformed}")

        if failed > 0:
            logger.info("\nFailed URLs:")
            for url, result in self.results.items():
                if not result["success"]:
                    logger.info(f"  - {url}")
                    logger.info(f"    Error: {result['error']}")

        if transformed > 0:
            logger.info("\nTransformed Data:")
            for url, result in self.results.items():
                if result.get("transformed"):
                    logger.info(
                        f"  - {url}: {result.get('transformed_records', 0)} records"
                    )

        logger.info("=" * 60)

    def run(self) -> int:
        """
        Ejecuta el flujo completo de extracción de interesados.

        Returns:
            Código de salida (0 = éxito, 1 = error)
        """
        try:
            logger.info("Starting interesados extraction...")

            # Paso 1: Configurar base de datos
            self.setup_database()

            # Paso 2: Procesar todas las URLs
            self.process_all_urls()

            # Paso 3: Imprimir resumen
            self.print_summary()

            # Determinar código de salida basado en resultados
            if not self.results:
                logger.warning("No data was processed")
                return 1

            # Salir con error si TODAS las peticiones fallaron
            all_failed = all(not r["success"] for r in self.results.values())
            if all_failed:
                logger.error("All requests failed")
                return 1

            logger.info("Interesados extraction completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Fatal error during extraction: {e}", exc_info=True)
            return 1

        finally:
            # Siempre limpiar recursos
            try:
                self.db_manager.close_connection()
                logger.info("Resources cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def get_interesados_extractor(
    settings: Settings = None,
    api_client: APIClient = None,
    db_manager: DatabaseManager = None,
) -> InteresadosExtractor:
    """
    Factory function para crear instancia del extractor.

    Args:
        settings: Configuración (si None, se carga automáticamente)
        api_client: Cliente HTTP (si None, se crea automáticamente)
        db_manager: Gestor de BD (si None, se crea automáticamente)

    Returns:
        Instancia de InteresadosExtractor
    """
    if settings is None:
        settings = get_settings()
    if api_client is None:
        api_client = get_api_client(settings)
    if db_manager is None:
        db_manager = get_database_manager(settings)

    return InteresadosExtractor(settings, api_client, db_manager)
