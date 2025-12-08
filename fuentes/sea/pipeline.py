#!/usr/bin/env python3
"""
SEA SEIA - Pipeline Unificado con Tracking Incremental

Entry point único que ejecuta el pipeline completo:
    python pipeline.py

COMPORTAMIENTO:
1. Registra inicio de ejecución en pipeline_runs
2. Extrae TODOS los proyectos de la API (paginación automática)
3. Hace UPSERT: inserta nuevos, actualiza los que cambiaron
4. Registra estadísticas del delta (nuevos vs actualizados)
5. Muestra reporte del delta desde la última corrida

CARACTERÍSTICAS:
- Idempotente: Se puede ejecutar múltiples veces
- Incremental: Detecta cambios y solo actualiza lo necesario
- Tracking: Guarda historial de corridas en pipeline_runs
- Delta visible: Muestra qué cambió desde la última vez

USO:
    # Ejecutar pipeline completo
    python pipeline.py

    # Ver delta sin ejecutar (dry-run)
    python pipeline.py --dry-run

    # Solo mostrar delta desde última corrida
    python pipeline.py --delta

    # Limitar páginas (para testing)
    python pipeline.py --max-pages 5
"""

import argparse
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

BATCH_SIZE = 10  # Páginas por batch


def print_header(text: str) -> None:
    """Imprimir header visual."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_section(text: str) -> None:
    """Imprimir sección."""
    print("\n" + "-" * 80)
    print(f">>> {text}")
    print("-" * 80)


def show_delta_report(repository) -> None:
    """Mostrar reporte del delta desde la última corrida."""
    print_header("DELTA DESDE ÚLTIMA CORRIDA")

    delta = repository.get_delta_since_last_run()

    if delta["ultima_corrida"] is None:
        print("Primera ejecución - no hay corrida anterior registrada")
        print(f"Total proyectos en BD: {delta['nuevos']}")
        return

    print(f"Última corrida exitosa: {delta['ultima_corrida']}")
    print(f"Proyectos nuevos:       {delta['nuevos']}")
    print(f"Proyectos actualizados: {delta['actualizados']}")

    # Mostrar algunos ejemplos de nuevos
    if delta["proyectos_nuevos"]:
        print("\nProyectos NUEVOS (últimos 10):")
        for p in delta["proyectos_nuevos"][:10]:
            print(f"  - [{p['expediente_id']}] {p['expediente_nombre'][:60]}...")
            print(f"    {p['workflow_descripcion']} | {p['region_nombre']} | {p['estado_proyecto']}")

    # Mostrar algunos ejemplos de actualizados
    if delta["proyectos_actualizados"]:
        print("\nProyectos ACTUALIZADOS (últimos 10):")
        for p in delta["proyectos_actualizados"][:10]:
            print(f"  - [{p['expediente_id']}] {p['expediente_nombre'][:60]}...")
            print(f"    {p['workflow_descripcion']} | {p['region_nombre']} | {p['estado_proyecto']}")


def run_extraction(
    extractor,
    parser,
    repository,
    max_pages: int | None = None,
    pipeline_run_id: int | None = None
) -> dict:
    """
    Ejecutar extracción completa con upsert.

    Args:
        extractor: Extractor de proyectos
        parser: Parser de proyectos
        repository: Repositorio de proyectos
        max_pages: Límite de páginas (opcional)
        pipeline_run_id: ID del pipeline_run actual (para tracking)

    Returns:
        Dict con estadísticas acumuladas
    """
    print_section("EXTRACCIÓN DE PROYECTOS")

    total_stats = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0, "total": 0}
    total_pages = 0
    batch_num = 0

    logger.info(f"Iniciando extracción (batch size: {BATCH_SIZE} páginas)")
    if max_pages:
        logger.info(f"Límite de páginas: {max_pages}")

    has_more = True
    while has_more:
        batch_num += 1

        # Verificar límite de páginas
        if max_pages and total_pages >= max_pages:
            logger.info(f"Alcanzado límite de {max_pages} páginas")
            break

        # Calcular cuántas páginas extraer en este batch
        pages_to_extract = BATCH_SIZE
        if max_pages:
            pages_remaining = max_pages - total_pages
            pages_to_extract = min(BATCH_SIZE, pages_remaining)

        # Extraer batch
        logger.info(f"Extrayendo BATCH {batch_num} ({pages_to_extract} páginas)...")
        batch_results, has_more = extractor.extract_batch(pages_to_extract)

        if not batch_results:
            logger.info("No hay más datos por extraer")
            break

        total_pages += len(batch_results)

        # Guardar raw_data
        logger.info("  -> Guardando raw_data...")
        repository.insert_raw_data_bulk(batch_results)

        # Parsear proyectos
        logger.info("  -> Parseando proyectos...")
        batch_proyectos = []
        for result in batch_results:
            if result["status_code"] == 200 and result["data"] is not None:
                try:
                    proyectos = parser.parse_proyectos_from_response(result["data"])
                    batch_proyectos.extend(proyectos)
                except Exception as e:
                    logger.error(f"Error parseando: {e}")

        # Upsert proyectos
        if batch_proyectos:
            logger.info(f"  -> Upsert de {len(batch_proyectos)} proyectos...")
            batch_stats = repository.upsert_proyectos_bulk(batch_proyectos, pipeline_run_id)

            # Acumular estadísticas
            total_stats["nuevos"] += batch_stats["nuevos"]
            total_stats["actualizados"] += batch_stats["actualizados"]
            total_stats["sin_cambios"] += batch_stats["sin_cambios"]
            total_stats["total"] += batch_stats["total"]

            logger.info(
                f"  -> Batch {batch_num}: "
                f"+{batch_stats['nuevos']} nuevos, "
                f"~{batch_stats['actualizados']} actualizados, "
                f"={batch_stats['sin_cambios']} sin cambios"
            )

    print(f"\nTotal páginas procesadas: {total_pages}")
    return total_stats


def print_final_report(stats: dict, elapsed_seconds: float, run_id: int) -> None:
    """Imprimir reporte final."""
    print_header("REPORTE FINAL")

    print(f"Pipeline Run ID: {run_id}")
    print(f"Tiempo total:    {elapsed_seconds:.1f} segundos ({elapsed_seconds/60:.1f} minutos)")
    print()
    print("ESTADÍSTICAS:")
    print(f"  Proyectos nuevos:       {stats['nuevos']:,}")
    print(f"  Proyectos actualizados: {stats['actualizados']:,}")
    print(f"  Proyectos sin cambios:  {stats['sin_cambios']:,}")
    print(f"  Total procesados:       {stats['total']:,}")
    print()

    # Calcular porcentajes
    if stats["total"] > 0:
        pct_nuevos = (stats["nuevos"] / stats["total"]) * 100
        pct_actualizados = (stats["actualizados"] / stats["total"]) * 100
        pct_sin_cambios = (stats["sin_cambios"] / stats["total"]) * 100
        print(f"  % Nuevos:       {pct_nuevos:.1f}%")
        print(f"  % Actualizados: {pct_actualizados:.1f}%")
        print(f"  % Sin cambios:  {pct_sin_cambios:.1f}%")

    print("=" * 80)


def main() -> int:
    """Entry point principal."""
    arg_parser = argparse.ArgumentParser(
        description="SEA SEIA - Pipeline Unificado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python pipeline.py              # Ejecutar pipeline completo
  python pipeline.py --dry-run    # Ver qué se haría sin ejecutar
  python pipeline.py --delta      # Solo mostrar delta desde última corrida
  python pipeline.py --max-pages 5  # Limitar a 5 páginas (testing)
        """
    )

    arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se haría sin ejecutar"
    )

    arg_parser.add_argument(
        "--delta",
        action="store_true",
        help="Solo mostrar delta desde última corrida (no ejecutar)"
    )

    arg_parser.add_argument(
        "--max-pages",
        type=int,
        help="Límite de páginas a procesar (para testing)"
    )

    args = arg_parser.parse_args()

    # Configuración
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_file=settings.log_file)

    print_header("SEA SEIA - Pipeline Unificado")
    logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Inicializar componentes
        db_manager = get_database_manager(settings)
        repository = get_proyectos_repository(db_manager)

        # Verificar conexión
        db_manager.get_connection()

        # Modo --delta: solo mostrar delta
        if args.delta:
            show_delta_report(repository)
            return 0

        # Modo --dry-run
        if args.dry_run:
            print("MODO DRY-RUN: Solo mostrando información")
            show_delta_report(repository)
            print("\nPara ejecutar realmente: python pipeline.py")
            return 0

        # Verificar tablas
        if not db_manager.table_exists("proyectos"):
            logger.error("Tabla 'proyectos' no existe. Ejecutar db/init.sql primero.")
            return 1

        # Verificar si existe pipeline_runs (migración 011)
        if not db_manager.table_exists("pipeline_runs"):
            logger.warning("Tabla 'pipeline_runs' no existe.")
            logger.warning("Ejecutar: mysql -u user -p db < db/migrations/011_add_updated_at_and_pipeline_runs.sql")
            return 1

        # Iniciar pipeline run
        run_id = repository.start_pipeline_run()
        start_time = datetime.now()

        # Inicializar extractor y parser
        http_client = get_http_client(settings)
        extractor = get_proyectos_extractor(settings, http_client)
        parser = get_proyectos_parser()

        # Ejecutar extracción
        stats = run_extraction(
            extractor, parser, repository,
            max_pages=args.max_pages,
            pipeline_run_id=run_id
        )

        # Finalizar pipeline run
        elapsed = (datetime.now() - start_time).total_seconds()
        repository.finish_pipeline_run(run_id, "completed", stats)

        # Reporte final
        print_final_report(stats, elapsed, run_id)

        # Mostrar delta
        show_delta_report(repository)

        db_manager.close_connection()
        return 0

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrumpido por el usuario")
        if "run_id" in locals():
            repository.finish_pipeline_run(
                run_id, "failed", stats if "stats" in locals() else {},
                error_message="Interrupted by user"
            )
        return 130

    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        if "run_id" in locals() and "repository" in locals():
            repository.finish_pipeline_run(
                run_id, "failed", stats if "stats" in locals() else {},
                error_message=str(e)
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
