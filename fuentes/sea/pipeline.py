#!/usr/bin/env python3
"""
SEA SEIA - Pipeline Unificado con Tracking Incremental

Entry point que ejecuta el pipeline completo:
    python pipeline.py

COMPORTAMIENTO:
1. Registra inicio de ejecucion en pipeline_runs
2. Extrae TODOS los proyectos de la API (paginacion automatica)
3. Hace UPSERT: inserta nuevos, actualiza los que cambiaron
4. Registra estadisticas del delta (nuevos vs actualizados)
5. Muestra reporte del delta desde la ultima corrida

CARACTERISTICAS:
- Idempotente: Se puede ejecutar multiples veces
- Incremental: Detecta cambios y solo actualiza lo necesario
- Tracking: Guarda historial de corridas en pipeline_runs
- Delta visible: Muestra que cambio desde la ultima vez

USO:
    # Ejecutar pipeline completo
    python pipeline.py

    # Preview: ver que se insertaria/actualizaria sin ejecutar
    python pipeline.py --preview

    # Solo mostrar delta desde ultima corrida
    python pipeline.py --delta

    # Limitar paginas (para testing)
    python pipeline.py --max-pages 5

    # Extraer RUTs de todos los PDFs pendientes (full run)
    python pipeline.py --extract-ruts

    # Extraer RUTs con límite (para testing)
    python pipeline.py --extract-ruts --rut-limit 50
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.database import get_database_manager
from src.core.http_client import format_duration, get_http_client
from src.extractors.proyectos import get_async_proyectos_extractor, get_proyectos_extractor
from src.extractors.rut_extractor import extraer_y_guardar_ruts, get_rut_extractor
from src.parsers.proyectos import get_proyectos_parser
from src.repositories.proyectos import get_proyectos_repository
from src.settings import get_settings

# Loguru auto-configures on import
from src.logging_config import logger

BATCH_SIZE = 10  # Páginas por batch
RUT_BATCH_SIZE = 50  # PDFs por batch para extracción de RUTs


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


def run_rut_extraction(
    db_manager,
    expediente_ids: list[int] | None = None,
    limit: int | None = None
) -> dict:
    """
    Extraer RUTs de PDFs pendientes.

    Args:
        db_manager: Database manager
        expediente_ids: Lista de expediente_ids específicos (opcional)
        limit: Límite de PDFs a procesar (opcional)

    Returns:
        Dict con estadísticas
    """
    print_section("EXTRACCIÓN DE RUTs")

    conn = db_manager.get_connection()
    cursor = conn.cursor(dictionary=True)

    # Query base para PDFs pendientes
    if expediente_ids:
        # Solo PDFs de proyectos específicos
        placeholders = ','.join(['%s'] * len(expediente_ids))
        query = f"""
            SELECT rel.id, rel.pdf_url, p.expediente_nombre
            FROM resumen_ejecutivo_links rel
            JOIN expediente_documentos ed ON rel.id_documento = ed.id_documento
            JOIN proyectos p ON ed.expediente_id = p.expediente_id
            WHERE rel.pdf_url IS NOT NULL
            AND rel.ruts_extracted_at IS NULL
            AND p.expediente_id IN ({placeholders})
        """
        params = expediente_ids
    else:
        # Todos los PDFs pendientes
        query = """
            SELECT rel.id, rel.pdf_url, p.expediente_nombre
            FROM resumen_ejecutivo_links rel
            JOIN expediente_documentos ed ON rel.id_documento = ed.id_documento
            JOIN proyectos p ON ed.expediente_id = p.expediente_id
            WHERE rel.pdf_url IS NOT NULL
            AND rel.ruts_extracted_at IS NULL
        """
        params = []

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        logger.info("No hay PDFs pendientes para extracción de RUTs")
        return {"total": 0, "con_ruts": 0, "sin_ruts": 0}

    logger.info(f"Procesando {len(rows)} PDFs para extracción de RUTs...")

    extractor = get_rut_extractor()
    stats = {"total": 0, "con_ruts": 0, "sin_ruts": 0}
    t_inicio = time.perf_counter()

    for i, row in enumerate(rows, 1):
        nombre = row['expediente_nombre'][:50] if row['expediente_nombre'] else 'N/A'

        if i % 10 == 0 or i == len(rows):
            logger.info(f"  [{i}/{len(rows)}] Procesando...")

        ok = extraer_y_guardar_ruts(row['id'], row['pdf_url'], cursor, extractor)
        stats["total"] += 1
        if ok:
            stats["con_ruts"] += 1
        else:
            stats["sin_ruts"] += 1

        # Commit cada RUT_BATCH_SIZE
        if i % RUT_BATCH_SIZE == 0:
            conn.commit()

    conn.commit()

    t_total = time.perf_counter() - t_inicio
    logger.info(
        f"Extracción de RUTs completada: {stats['con_ruts']}/{stats['total']} "
        f"con RUTs ({stats['con_ruts']/stats['total']*100:.0f}%) en {t_total:.1f}s"
    )

    return stats


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
    Ejecutar extraccion completa con upsert.

    Args:
        extractor: Extractor de proyectos
        parser: Parser de proyectos
        repository: Repositorio de proyectos
        max_pages: Limite de paginas (opcional)
        pipeline_run_id: ID del pipeline run para historial

    Returns:
        Dict con estadisticas acumuladas
    """
    print_section("EXTRACCION DE PROYECTOS")

    total_stats = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0, "total": 0}
    total_pages = 0
    batch_num = 0

    logger.info(f"Iniciando extraccion (batch size: {BATCH_SIZE} paginas)")
    if max_pages:
        logger.info(f"Limite de paginas: {max_pages}")

    has_more = True
    while has_more:
        batch_num += 1

        # Verificar limite de paginas
        if max_pages and total_pages >= max_pages:
            logger.info(f"Alcanzado limite de {max_pages} paginas")
            break

        # Calcular cuantas paginas extraer en este batch
        pages_to_extract = BATCH_SIZE
        if max_pages:
            pages_remaining = max_pages - total_pages
            pages_to_extract = min(BATCH_SIZE, pages_remaining)

        # Extraer batch
        batch_start = time.perf_counter()
        logger.info(f"Extrayendo BATCH {batch_num} ({pages_to_extract} paginas)...")
        batch_results, has_more = extractor.extract_batch(pages_to_extract)
        extract_elapsed = time.perf_counter() - batch_start

        if not batch_results:
            logger.info("No hay mas datos por extraer")
            break

        total_pages += len(batch_results)

        # Guardar raw_data
        raw_start = time.perf_counter()
        logger.info("  -> Guardando raw_data...")
        repository.insert_raw_data_bulk(batch_results)
        raw_elapsed = time.perf_counter() - raw_start
        logger.info(f"  -> raw_data guardado ({format_duration(raw_elapsed)})")

        # Parsear proyectos
        parse_start = time.perf_counter()
        logger.info("  -> Parseando proyectos...")
        batch_proyectos = []
        for result in batch_results:
            if result["status_code"] == 200 and result["data"] is not None:
                try:
                    proyectos = parser.parse_proyectos_from_response(result["data"])
                    batch_proyectos.extend(proyectos)
                except Exception as e:
                    logger.error(f"Error parseando: {e}")
        parse_elapsed = time.perf_counter() - parse_start
        logger.info(f"  -> Parseado completado: {len(batch_proyectos)} proyectos ({format_duration(parse_elapsed)})")

        # Upsert proyectos
        if batch_proyectos:
            upsert_start = time.perf_counter()
            logger.info(f"  -> Upsert de {len(batch_proyectos)} proyectos...")
            batch_stats = repository.upsert_proyectos_bulk(batch_proyectos, pipeline_run_id)
            upsert_elapsed = time.perf_counter() - upsert_start

            # Acumular estadisticas
            total_stats["nuevos"] += batch_stats["nuevos"]
            total_stats["actualizados"] += batch_stats["actualizados"]
            total_stats["sin_cambios"] += batch_stats["sin_cambios"]
            total_stats["total"] += batch_stats["total"]

            batch_total = time.perf_counter() - batch_start
            logger.info(
                f"  -> Batch {batch_num}: "
                f"+{batch_stats['nuevos']} nuevos, "
                f"~{batch_stats['actualizados']} actualizados, "
                f"={batch_stats['sin_cambios']} sin cambios "
                f"(extract: {format_duration(extract_elapsed)}, "
                f"raw: {format_duration(raw_elapsed)}, "
                f"parse: {format_duration(parse_elapsed)}, "
                f"upsert: {format_duration(upsert_elapsed)}, "
                f"total: {format_duration(batch_total)})"
            )

    print(f"\nTotal paginas procesadas: {total_pages}")
    return total_stats


def run_preview_extraction(
    extractor,
    parser,
    repository,
    max_pages: int | None = None
) -> dict[str, Any]:
    """
    Ejecutar extraccion en modo preview (sin escribir a BD).
    LEGACY: Usa extracción secuencial. Preferir run_preview_extraction_parallel.

    Args:
        extractor: Extractor de proyectos
        parser: Parser de proyectos
        repository: Repositorio de proyectos
        max_pages: Limite de paginas (opcional)

    Returns:
        Dict con proyectos clasificados y estadisticas
    """
    print_section("PREVIEW - EXTRACCION DE PROYECTOS (SECUENCIAL)")

    all_proyectos: list[dict[str, Any]] = []
    total_pages = 0
    batch_num = 0

    logger.info(f"Modo PREVIEW: extrayendo datos sin escribir a BD")
    logger.info(f"Batch size: {BATCH_SIZE} paginas")
    if max_pages:
        logger.info(f"Limite de paginas: {max_pages}")

    has_more = True
    while has_more:
        batch_num += 1

        # Verificar limite de paginas
        if max_pages and total_pages >= max_pages:
            logger.info(f"Alcanzado limite de {max_pages} paginas")
            break

        # Calcular cuantas paginas extraer en este batch
        pages_to_extract = BATCH_SIZE
        if max_pages:
            pages_remaining = max_pages - total_pages
            pages_to_extract = min(BATCH_SIZE, pages_remaining)

        # Extraer batch
        batch_start = time.perf_counter()
        logger.info(f"Extrayendo BATCH {batch_num} ({pages_to_extract} paginas)...")
        batch_results, has_more = extractor.extract_batch(pages_to_extract)
        extract_elapsed = time.perf_counter() - batch_start

        if not batch_results:
            logger.info("No hay mas datos por extraer")
            break

        total_pages += len(batch_results)

        # Parsear proyectos (sin guardar raw_data en preview)
        parse_start = time.perf_counter()
        logger.info("  -> Parseando proyectos...")
        for result in batch_results:
            if result["status_code"] == 200 and result["data"] is not None:
                try:
                    proyectos = parser.parse_proyectos_from_response(result["data"])
                    all_proyectos.extend(proyectos)
                except Exception as e:
                    logger.error(f"Error parseando: {e}")
        parse_elapsed = time.perf_counter() - parse_start

        batch_total = time.perf_counter() - batch_start
        logger.info(
            f"  -> Batch {batch_num}: {len(all_proyectos)} proyectos acumulados "
            f"(extract: {format_duration(extract_elapsed)}, "
            f"parse: {format_duration(parse_elapsed)}, "
            f"total: {format_duration(batch_total)})"
        )

    # Clasificar proyectos contra BD actual
    logger.info(f"\nClasificando {len(all_proyectos)} proyectos contra BD...")
    preview_result = repository.preview_proyectos_bulk(all_proyectos)

    print(f"\nTotal paginas procesadas: {total_pages}")
    print(f"Total proyectos extraidos: {len(all_proyectos)}")

    return preview_result


def run_preview_extraction_parallel(
    settings,
    parser,
    repository,
    max_pages: int | None = None,
    concurrency: int = 10
) -> dict[str, Any]:
    """
    Ejecutar extraccion en modo preview con requests paralelos.

    Args:
        settings: Settings de la aplicación
        parser: Parser de proyectos
        repository: Repositorio de proyectos
        max_pages: Limite de paginas (opcional)
        concurrency: Número de requests paralelos (default: 10)

    Returns:
        Dict con proyectos clasificados y estadisticas
    """
    print_section("PREVIEW - EXTRACCION DE PROYECTOS (PARALELO)")

    logger.info(f"Modo PREVIEW PARALELO: extrayendo datos sin escribir a BD")
    logger.info(f"Concurrencia: {concurrency} requests paralelos")
    if max_pages:
        logger.info(f"Limite de paginas: {max_pages}")

    # Crear extractor async
    async_extractor = get_async_proyectos_extractor(settings, concurrency=concurrency)

    # Extraer todas las páginas en paralelo
    extract_start = time.perf_counter()
    all_results, total_records, total_proyectos_api = async_extractor.extract_all_sync(max_pages)
    extract_elapsed = time.perf_counter() - extract_start

    logger.info(f"Extracción completada en {format_duration(extract_elapsed)}")

    # Parsear todos los proyectos
    parse_start = time.perf_counter()
    logger.info("Parseando todos los proyectos...")
    all_proyectos: list[dict[str, Any]] = []
    for result in all_results:
        if result["status_code"] == 200 and result["data"] is not None:
            try:
                proyectos = parser.parse_proyectos_from_response(result["data"])
                all_proyectos.extend(proyectos)
            except Exception as e:
                logger.error(f"Error parseando página {result.get('offset', '?')}: {e}")
    parse_elapsed = time.perf_counter() - parse_start
    logger.info(f"Parseados {len(all_proyectos)} proyectos ({format_duration(parse_elapsed)})")

    # Clasificar proyectos contra BD actual
    classify_start = time.perf_counter()
    logger.info(f"Clasificando {len(all_proyectos)} proyectos contra BD...")
    preview_result = repository.preview_proyectos_bulk(all_proyectos)
    classify_elapsed = time.perf_counter() - classify_start
    logger.info(f"Clasificación completada ({format_duration(classify_elapsed)})")

    print(f"\nTotal paginas procesadas: {len(all_results)}")
    print(f"Total proyectos extraidos: {len(all_proyectos)}")
    print(f"Tiempo extracción: {format_duration(extract_elapsed)}")
    print(f"Tiempo parsing: {format_duration(parse_elapsed)}")
    print(f"Tiempo clasificación: {format_duration(classify_elapsed)}")

    return preview_result


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


def print_preview_report(preview_result: dict[str, Any], output_file: str | None = None) -> None:
    """Imprimir reporte de preview."""
    print_header("PREVIEW - RESULTADO")

    counts = preview_result["counts"]
    print("ESTADÍSTICAS (sin escribir a BD):")
    print(f"  Proyectos nuevos:       {counts['nuevos']:,}")
    print(f"  Proyectos actualizados: {counts['actualizados']:,}")
    print(f"  Proyectos sin cambios:  {counts['sin_cambios']:,}")
    print(f"  Total analizados:       {counts['total']:,}")
    print()

    # Mostrar ejemplos de nuevos
    if preview_result["nuevos"]:
        print("\nPROYECTOS NUEVOS (primeros 10):")
        for p in preview_result["nuevos"][:10]:
            nombre = p.get("expediente_nombre", "")[:60]
            print(f"  - [{p.get('expediente_id')}] {nombre}...")
            print(f"    {p.get('workflow_descripcion')} | {p.get('region_nombre')} | {p.get('estado_proyecto')}")

    # Mostrar ejemplos de actualizados
    if preview_result["actualizados"]:
        print("\nPROYECTOS ACTUALIZADOS (primeros 10):")
        for p in preview_result["actualizados"][:10]:
            nombre = p.get("expediente_nombre", "")[:60]
            print(f"  - [{p.get('expediente_id')}] {nombre}...")
            changed = p.get("_changed_fields", [])
            if changed:
                # _changed_fields es lista de dicts con {field, old, new}
                field_names = [c["field"] if isinstance(c, dict) else str(c) for c in changed]
                print(f"    Campos: {', '.join(field_names)}")

    # Guardar JSON si se especificó archivo
    if output_file:
        from src.extractors.proyectos import get_validation_stats
        validation_stats = get_validation_stats()
        total = validation_stats["valid"] + validation_stats["invalid"]

        # Construir reporte con validación
        report = {
            "generated_at": datetime.now().isoformat(),
            "validation": {
                "responses_valid": validation_stats["valid"],
                "responses_invalid": validation_stats["invalid"],
                "total": total,
                "success_rate": f"{(validation_stats['valid'] / total * 100):.1f}%" if total > 0 else "N/A",
                "errors": validation_stats["errors"][:10] if validation_stats["errors"] else []
            },
            "counts": preview_result["counts"],
            "nuevos": preview_result["nuevos"],
            "actualizados": preview_result["actualizados"],
            "sin_cambios_count": len(preview_result["sin_cambios"])
        }

        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nReporte guardado en: {output_path}")

    print("=" * 80)


def main() -> int:
    """Entry point principal."""
    arg_parser = argparse.ArgumentParser(
        description="SEA SEIA - Pipeline Unificado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python pipeline.py                       # Ejecutar pipeline completo
  python pipeline.py --preview             # Ver qué se insertaría/actualizaría
  python pipeline.py --preview --output preview.json  # Guardar preview en JSON
  python pipeline.py --delta               # Solo mostrar delta desde última corrida
  python pipeline.py --max-pages 5         # Limitar a 5 páginas (testing)
  python pipeline.py --extract-ruts        # Extraer RUTs de PDFs pendientes
  python pipeline.py --extract-ruts --rut-limit 100  # Extraer RUTs con límite
        """
    )

    arg_parser.add_argument(
        "--preview",
        action="store_true",
        help="Extraer datos y mostrar qué se insertaría/actualizaría (sin escribir)"
    )

    arg_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Archivo JSON para guardar resultado del preview"
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

    arg_parser.add_argument(
        "--extract-ruts",
        action="store_true",
        help="Extraer RUTs de todos los PDFs pendientes (full run)"
    )

    arg_parser.add_argument(
        "--rut-limit",
        type=int,
        help="Límite de PDFs a procesar para extracción de RUTs"
    )

    args = arg_parser.parse_args()

    # Configuración
    settings = get_settings()

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

        # Modo --extract-ruts: extraer RUTs de todos los PDFs pendientes
        if args.extract_ruts:
            rut_stats = run_rut_extraction(db_manager, limit=args.rut_limit)
            print_header("EXTRACCIÓN DE RUTs - COMPLETADO")
            print(f"Total procesados:  {rut_stats['total']}")
            print(f"Con RUTs:          {rut_stats['con_ruts']}")
            print(f"Sin RUTs:          {rut_stats['sin_ruts']}")
            if rut_stats['total'] > 0:
                print(f"Tasa de éxito:     {rut_stats['con_ruts']/rut_stats['total']*100:.1f}%")
            db_manager.close_connection()
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

        # Inicializar parser
        parser = get_proyectos_parser()

        # Modo --preview: extraer y clasificar sin escribir (PARALELO)
        if args.preview:
            start_time = datetime.now()
            preview_result = run_preview_extraction_parallel(
                settings, parser, repository,
                max_pages=args.max_pages,
                concurrency=10
            )
            elapsed = (datetime.now() - start_time).total_seconds()

            # Generar nombre de archivo automático si no se especificó
            output_file = args.output
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"preview_{timestamp}.json"

            print_preview_report(preview_result, output_file)
            logger.info(f"Preview completado en {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)")
            print("\nPara ejecutar realmente: python pipeline.py")
            db_manager.close_connection()
            return 0

        # Inicializar extractor síncrono para modo normal
        http_client = get_http_client(settings)
        extractor = get_proyectos_extractor(settings, http_client)

        # Modo normal: ejecutar pipeline completo
        run_id = repository.start_pipeline_run()
        start_time = datetime.now()

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
