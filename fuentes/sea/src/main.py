"""
Script principal para extracción de datos del SEA (Sistema de Evaluación de Impacto Ambiental).

Este script orquesta todo el proceso de extracción:
1. Extracción de proyectos desde la API con paginación automática
2. Almacenamiento INCREMENTAL de datos crudos en raw_data (cada batch)
3. Parseo de proyectos (cada batch)
4. Almacenamiento INCREMENTAL de proyectos (cada batch)
5. Generación de estadísticas

Estrategia:
- Append-only (nunca actualiza ni elimina registros)
- Guardado incremental por batches (no se pierde progreso si falla)
"""

import logging
import sys
from datetime import datetime

from src.core.database import get_database_manager
from src.core.http_client import get_http_client
from src.core.logging import setup_logging
from src.extractors.proyectos import get_proyectos_extractor
from src.parsers.proyectos import get_proyectos_parser
from src.repositories.proyectos import get_proyectos_repository
from src.settings import get_settings

logger = logging.getLogger(__name__)

# Tamaño del batch para guardado incremental
BATCH_SIZE = 10  # Guardar cada 10 páginas (reducido para evitar problemas de memoria)


def process_batch(batch_results, parser, repository, batch_num, total_batches):
    """
    Procesar y guardar un batch de resultados.

    Args:
        batch_results: Lista de resultados de extracción
        parser: Parser de proyectos
        repository: Repository de base de datos
        batch_num: Número del batch actual
        total_batches: Total de batches estimados

    Returns:
        Tupla (num_raw_inserted, num_proyectos_inserted, num_duplicated)
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"PROCESANDO BATCH {batch_num}/{total_batches} ({len(batch_results)} páginas)")
    logger.info(f"{'=' * 80}")

    # 1. Guardar datos crudos
    logger.info("  → Guardando datos crudos en raw_data...")
    num_raw_inserted = repository.insert_raw_data_bulk(batch_results)
    logger.info(f"  ✓ Guardados {num_raw_inserted} registros en raw_data")

    # 2. Parsear proyectos del batch
    logger.info("  → Parseando proyectos...")
    batch_proyectos = []
    for i, result in enumerate(batch_results, 1):
        if result["status_code"] == 200 and result["data"] is not None:
            try:
                proyectos = parser.parse_proyectos_from_response(result["data"])
                batch_proyectos.extend(proyectos)
            except Exception as e:
                logger.error(f"  ✗ Error parseando página {i} del batch: {e}")
                continue

    logger.info(f"  ✓ Parseados {len(batch_proyectos)} proyectos")

    # 3. Guardar proyectos (solo nuevos)
    logger.info("  → Guardando proyectos en BD...")
    num_inserted, num_duplicated = repository.insert_proyectos_bulk(batch_proyectos)
    logger.info(f"  ✓ Proyectos nuevos: {num_inserted}, duplicados: {num_duplicated}")

    return num_raw_inserted, num_inserted, num_duplicated


def main():
    """
    Función principal de orquestación con guardado incremental.

    Coordina todo el proceso de extracción y almacenamiento de datos,
    guardando en batches para no perder progreso si falla.
    """
    # 1. Cargar configuración
    settings = get_settings()

    # 2. Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

    logger.info("=" * 80)
    logger.info("SEA SEIA - Sistema de Extracción de Proyectos")
    logger.info("Modo: GUARDADO INCREMENTAL (batch de {} páginas)".format(BATCH_SIZE))
    logger.info("=" * 80)
    logger.info(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 3. Inicializar componentes
        logger.info("Inicializando componentes...")
        http_client = get_http_client(settings)
        db_manager = get_database_manager(settings)
        extractor = get_proyectos_extractor(settings, http_client)
        parser = get_proyectos_parser()
        repository = get_proyectos_repository(db_manager)

        # 4. Verificar conexión a base de datos
        logger.info("Verificando conexión a base de datos...")
        db_manager.get_connection()

        # Verificar que existan las tablas necesarias
        if not db_manager.table_exists("raw_data"):
            logger.error("Tabla 'raw_data' no existe. Ejecutar db/init.sql primero.")
            return 1

        if not db_manager.table_exists("proyectos"):
            logger.error("Tabla 'proyectos' no existe. Ejecutar db/init.sql primero.")
            return 1

        logger.info("Base de datos lista")

        # 5. Extracción y guardado incremental por batches
        logger.info("\n" + "=" * 80)
        logger.info("EXTRACCIÓN CON GUARDADO INCREMENTAL")
        logger.info("=" * 80)

        # Estadísticas acumuladas
        total_raw_inserted = 0
        total_proyectos_inserted = 0
        total_duplicated = 0
        total_pages = 0
        batch_num = 0

        # Loop de extracción y guardado incremental
        logger.info("Iniciando extracción incremental con guardado por batches...")
        logger.info(f"Batch size: {BATCH_SIZE} páginas\n")

        has_more = True
        while has_more:
            batch_num += 1

            # Extraer batch de páginas
            logger.info(f"Extrayendo BATCH {batch_num} ({BATCH_SIZE} páginas)...")
            batch_results, has_more = extractor.extract_batch(BATCH_SIZE)

            if not batch_results:
                logger.info("No hay más datos por extraer")
                break

            total_pages += len(batch_results)

            # Procesar y guardar batch inmediatamente
            try:
                num_raw, num_inserted, num_dup = process_batch(
                    batch_results, parser, repository, batch_num, "?"
                )

                total_raw_inserted += num_raw
                total_proyectos_inserted += num_inserted
                total_duplicated += num_dup

                logger.info(f"✓ Batch {batch_num} completado y guardado")
                logger.info(f"  Progreso total: {total_pages} páginas, {total_proyectos_inserted} proyectos nuevos\n")

            except Exception as e:
                logger.error(f"Error procesando batch {batch_num}: {e}", exc_info=True)
                logger.warning("Continuando con siguiente batch...")
                continue

        # 6. Mostrar estadísticas finales
        logger.info("\n" + "=" * 80)
        logger.info("RESUMEN DE LA EXTRACCIÓN")
        logger.info("=" * 80)
        logger.info(f"Total de páginas procesadas: {total_pages}")
        logger.info(f"Total raw_data guardados: {total_raw_inserted}")
        logger.info(f"Total proyectos nuevos: {total_proyectos_inserted}")
        logger.info(f"Total proyectos duplicados: {total_duplicated}")

        # 7. Estadísticas de la base de datos
        logger.info("\n" + "=" * 80)
        logger.info("ESTADÍSTICAS DE LA BASE DE DATOS")
        logger.info("=" * 80)

        stats = repository.get_estadisticas()

        logger.info(f"Total de proyectos en BD: {stats['total_proyectos']:,}")
        logger.info(f"Total de extracciones (raw_data): {stats['total_raw_extractions']:,}")

        if stats.get("por_tipo"):
            logger.info("\nProyectos por tipo de evaluación:")
            for tipo, count in stats["por_tipo"].items():
                logger.info(f"  - {tipo}: {count:,}")

        if stats.get("top_regiones"):
            logger.info("\nTop 10 regiones con más proyectos:")
            for region, count in list(stats["top_regiones"].items())[:10]:
                logger.info(f"  - {region}: {count:,}")

        # 8. Cerrar conexión a base de datos
        db_manager.close_connection()

        logger.info("\n" + "=" * 80)
        logger.info("EXTRACCIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 80)
        logger.info(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return 0

    except KeyboardInterrupt:
        logger.warning("\n" + "=" * 80)
        logger.warning("EXTRACCIÓN INTERRUMPIDA POR EL USUARIO")
        logger.warning("=" * 80)
        logger.warning("Los datos procesados hasta ahora han sido guardados.")
        return 1

    except Exception as e:
        logger.error(f"Error fatal durante la extracción: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
