"""
Main orchestration module for the API data ingestion service.

This module coordinates the entire workflow:
1. Load configuration
2. Initialize database
3. Fetch data from configured APIs
4. Save raw data to database
5. Transform/normalize data into tables
6. Report results
"""

import logging
import sys
from typing import Any, Dict, List

from src.client import get_api_client
from src.database import get_database_manager
from src.settings import get_settings
from src.transformers import transform_interesados

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class DataIngestionService:
    """
    Clase principal del servicio que orquesta el flujo de ingesta de datos.
    """

    def __init__(self):
        """Inicializa el servicio con configuración y dependencias."""
        # Cargar configuración
        self.settings = get_settings()
        logger.info("Settings loaded successfully")

        # Inicializar dependencias
        self.api_client = get_api_client(self.settings)
        self.db_manager = get_database_manager(self.settings)
        logger.info("Service dependencies initialized")

        # Rastrear resultados
        self.results: Dict[str, dict] = {}

    def setup_database(self) -> None:
        """
        Configura la conexión a la base de datos y crea las tablas necesarias.

        Este método es idempotente - puede ser llamado múltiples veces de forma segura.
        """
        logger.info("Setting up database...")
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
                self._transform_if_needed(url, data, row_id, result)

        except Exception as e:
            result["success"] = False
            result["error"] = f"Database insert failed: {str(e)}"
            logger.error(f"Failed to store data from {url}: {e}")

        return result

    def _transform_if_needed(
        self, url: str, data: Any, raw_data_id: int, result: dict
    ) -> None:
        """
        Transforma datos raw a tablas normalizadas basado en el endpoint de la URL.

        ESTRATEGIA DE NORMALIZACIÓN:
        - Detecta el tipo de endpoint por la URL
        - Transforma datos raw a formato normalizado
        - SOLO inserta registros NUEVOS (append-only)
        - Mantiene historial completo (no elimina registros antiguos)
        """
        try:
            # DETECCIÓN AUTOMÁTICA del tipo de endpoint
            if "interesados" in url.lower():
                logger.info(f"Transforming interesados data from {url}...")

                # PASO 1: Transformar JSON raw a lista de registros normalizados
                records = transform_interesados(data)

                if records:
                    # PASO 2: Insertar SOLO registros nuevos (ver database.py para lógica)
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
                    logger.warning(f"No records to transform from {url}")
                    result["transformed"] = False

        except Exception as e:
            logger.error(f"Transformation failed for {url}: {e}", exc_info=True)
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

        Proporciona una vista clara de lo que tuvo éxito y lo que falló.
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
        logger.info("INGESTION SUMMARY")
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
        Ejecuta el flujo completo de ingesta de datos.
        """
        try:
            logger.info("Starting API data ingestion service...")

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

            logger.info("Data ingestion completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Fatal error during ingestion: {e}", exc_info=True)
            return 1

        finally:
            # Siempre limpiar recursos
            try:
                self.db_manager.close_connection()
                logger.info("Resources cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def main() -> None:
    """
    Punto de entrada principal de la aplicación.

    Esta función se llama cuando el módulo se ejecuta directamente.
    """
    service = DataIngestionService()
    exit_code = service.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
