"""
Módulo principal de orquestación para Fuentes Base.

Este módulo coordina el flujo completo de extracción y procesamiento de datos:
1. Cargar configuración
2. Inicializar base de datos
3. Ejecutar extractores según configuración
4. Almacenar datos en BD
5. Opcionalmente parsear datos
6. Reportar resultados
"""

import logging
import sys
from datetime import datetime
from typing import Any

from src.core.database import get_database_manager
from src.core.logging import setup_logging
from src.extractors.api_rest import APIRestExtractor
from src.extractors.file_download import FileDownloadExtractor
from src.extractors.web_dynamic import WebDynamicExtractor
from src.extractors.web_static import WebStaticExtractor
from src.repositories.raw_data import get_raw_data_repository
from src.settings import get_settings

logger = logging.getLogger(__name__)


class FuentesBaseService:
    """
    Servicio principal que orquesta el flujo de ingesta de datos.

    Sigue un proceso claro paso a paso para extraer y almacenar datos.
    """

    def __init__(self):
        """Inicializar el servicio con configuración y dependencias."""
        # Cargar settings
        self.settings = get_settings()

        # Setup logging
        setup_logging(
            log_level=self.settings.log_level,
            log_file=self.settings.log_file,
        )

        logger.info("=== Fuentes Base Service Starting ===")
        logger.info(f"Source type: {self.settings.source_type}")

        # Inicializar dependencias
        self.db_manager = get_database_manager(self.settings)
        self.raw_data_repo = get_raw_data_repository(self.db_manager)

        # Trackear resultados
        self.extraction_results: list[dict[str, Any]] = []

    def setup_database(self) -> None:
        """
        Configurar la base de datos y verificar conexión.

        Este método es idempotente - puede llamarse múltiples veces de forma segura.
        """
        logger.info("Setting up database...")
        try:
            # Verificar que podemos conectar
            self.db_manager.get_connection()

            # Verificar que las tablas existen
            if not self.db_manager.table_exists("raw_data"):
                logger.error(
                    "Table 'raw_data' does not exist. "
                    "Please run db/init.sql to create the schema."
                )
                raise RuntimeError("Database schema not initialized")

            logger.info("Database setup completed successfully")

        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise

    def run_extraction(self) -> None:
        """
        Ejecutar extracción de datos según el tipo de fuente configurado.

        Este método detecta el tipo de fuente y ejecuta el extractor apropiado.
        """
        source_type = self.settings.source_type

        if not source_type:
            logger.warning("No source_type configured. Please set SOURCE_TYPE in .env")
            return

        logger.info(f"Running extraction for source type: {source_type}")

        try:
            if source_type == "api_rest":
                extractor = APIRestExtractor(self.settings)
                self.extraction_results = extractor.extract()

            elif source_type == "web_static":
                extractor = WebStaticExtractor(self.settings)
                self.extraction_results = extractor.extract()

            elif source_type == "web_dynamic":
                extractor = WebDynamicExtractor(self.settings)
                self.extraction_results = extractor.extract()

            elif source_type == "file_download":
                extractor = FileDownloadExtractor(self.settings)
                self.extraction_results = extractor.extract()

            else:
                logger.error(f"Unknown source type: {source_type}")
                return

            logger.info(f"Extraction completed with {len(self.extraction_results)} results")

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            raise

    def store_results(self) -> None:
        """
        Almacenar resultados de extracción en la base de datos.

        Este método inserta todos los resultados en la tabla raw_data.
        """
        if not self.extraction_results:
            logger.warning("No results to store")
            return

        logger.info(f"Storing {len(self.extraction_results)} results in database...")

        try:
            # Preparar registros para inserción
            records = []
            for result in self.extraction_results:
                record = {
                    "source_url": result["source_url"],
                    "source_type": self.settings.source_type or "other",
                    "status_code": result["status_code"],
                    "data": result["data"],
                    "error_message": result.get("error_message"),
                    "extracted_at": datetime.fromisoformat(
                        result["extracted_at"].replace("Z", "+00:00")
                    ),
                }
                records.append(record)

            # Insertar en batch
            ids = self.raw_data_repo.insert_many(records)

            logger.info(f"Successfully stored {len(ids)} records in database")

        except Exception as e:
            logger.error(f"Failed to store results: {e}", exc_info=True)
            raise

    def print_summary(self) -> None:
        """
        Imprimir un resumen de los resultados de ingesta.

        Provee una visión clara de qué tuvo éxito y qué falló.
        """
        if not self.extraction_results:
            logger.info("No results to summarize")
            return

        total = len(self.extraction_results)
        successful = sum(
            1 for r in self.extraction_results if r.get("error_message") is None
        )
        failed = total - successful

        logger.info("=" * 70)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Source type: {self.settings.source_type}")
        logger.info(f"Total extractions: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")

        if failed > 0:
            logger.info("\nFailed sources:")
            for result in self.extraction_results:
                if result.get("error_message"):
                    logger.info(f"  - {result['source_url']}")
                    logger.info(f"    Error: {result['error_message']}")

        # Mostrar estadísticas de BD
        try:
            stats = self.raw_data_repo.get_statistics()
            if stats:
                logger.info("\nDatabase statistics:")
                for stat in stats:
                    logger.info(
                        f"  {stat['source_type']}: "
                        f"{stat['total_extractions']} total "
                        f"({stat['successful']} successful, {stat['failed']} failed)"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch database statistics: {e}")

        logger.info("=" * 70)

    def run(self) -> int:
        """
        Ejecutar el flujo completo de ingesta de datos.

        Returns:
            Código de salida (0 para éxito, 1 para fallo)
        """
        try:
            logger.info("Starting Fuentes Base data ingestion service...")

            # Paso 1: Configurar base de datos
            self.setup_database()

            # Paso 2: Ejecutar extracción
            self.run_extraction()

            # Paso 3: Almacenar resultados
            self.store_results()

            # Paso 4: Imprimir resumen
            self.print_summary()

            # Determinar código de salida basado en resultados
            if not self.extraction_results:
                logger.warning("No data was extracted")
                return 1

            # Salir con error si TODAS las requests fallaron
            all_failed = all(
                r.get("error_message") is not None for r in self.extraction_results
            )
            if all_failed:
                logger.error("All extractions failed")
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
    Punto de entrada principal para la aplicación.

    Esta función se llama cuando el módulo se ejecuta directamente.
    """
    service = FuentesBaseService()
    exit_code = service.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
