#!/usr/bin/env python3
"""
Run Sample Pipeline - Script completo de inicio a fin con muestra pequeña.

Este script ejecuta el pipeline completo de extracción con una muestra de 50 proyectos,
demostrando todas las etapas del framework iterativo.

Etapas:
    1. Extracción de proyectos (50)
    2. Extracción de documentos del expediente
    3. Extracción de links a PDF resumen ejecutivo
    4. Reporte de estadísticas finales

Uso:
    python run_sample.py

    # Con cleanup previo
    python run_sample.py --clean
"""
import argparse
import logging
import sys
from datetime import datetime
from src.core.database import get_database_manager
from src.core.http_client import get_http_client
from src.extractors.proyectos import get_proyectos_extractor
from src.extractors.expediente_documentos import get_expediente_documentos_extractor
from src.extractors.resumen_ejecutivo import get_resumen_ejecutivo_extractor
from src.parsers.proyectos import get_proyectos_parser
from src.parsers.expediente_documentos import get_expediente_documentos_parser
from src.parsers.resumen_ejecutivo import get_resumen_ejecutivo_parser
from src.repositories.proyectos import get_proyectos_repository
from src.repositories.expediente_documentos import get_expediente_documentos_repository
from src.repositories.resumen_ejecutivo_links import get_resumen_ejecutivo_links_repository
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SAMPLE_SIZE = 50  # Número de proyectos a extraer
DOCS_BATCH_SIZE = 100  # Tamaño de batch para documentos
LINKS_BATCH_SIZE = 100  # Tamaño de batch para links

def cleanup_all(db):
    """Limpiar todas las tablas para empezar de cero."""
    logger.info("\n" + "="*80)
    logger.info("LIMPIANDO BASE DE DATOS")
    logger.info("="*80)

    confirm = input("\n⚠️  Esto borrará TODOS los datos. ¿Continuar? (escribe 'si'): ")
    if confirm.lower() != 'si':
        logger.info("❌ Cancelado")
        sys.exit(0)

    logger.info("\nBorrando datos...")
    db.execute_query("DELETE FROM resumen_ejecutivo_links", commit=True)
    db.execute_query("DELETE FROM expediente_documentos", commit=True)
    db.execute_query("DELETE FROM proyectos", commit=True)
    db.execute_query("DELETE FROM raw_data", commit=True)
    logger.info("✓ Datos borrados\n")

    # Pausa para verificar que la limpieza fue exitosa
    logger.info("="*80)
    logger.info("LIMPIEZA COMPLETADA")
    logger.info("="*80)
    logger.info("\nPuedes verificar que las tablas están vacías ejecutando:")
    logger.info("  mysql -h 172.29.0.5 -P 3308 -u chris -ppewpew12 sea -e 'SELECT COUNT(*) FROM proyectos;'")
    logger.info("  mysql -h 172.29.0.5 -P 3308 -u chris -ppewpew12 sea -e 'SELECT COUNT(*) FROM expediente_documentos;'")
    logger.info("  mysql -h 172.29.0.5 -P 3308 -u chris -ppewpew12 sea -e 'SELECT COUNT(*) FROM resumen_ejecutivo_links;'")

    input("\n✋ Presiona ENTER para continuar con la extracción...")

def extract_proyectos_sample(db, http_client, settings):
    """Etapa 1: Extraer muestra de proyectos."""
    logger.info("\n" + "="*80)
    logger.info(f"ETAPA 1: EXTRACCIÓN DE {SAMPLE_SIZE} PROYECTOS")
    logger.info("="*80 + "\n")

    extractor = get_proyectos_extractor(settings, http_client)
    parser = get_proyectos_parser()
    repo = get_proyectos_repository(db)

    # Extraer página con proyectos más antiguos (página 200 = proyectos ~20,000)
    # Estos tienen más probabilidad de tener documentos EIA/DIA
    logger.info("Extrayendo página 200 (proyectos antiguos con más documentos)...")
    result = extractor.extract_page(offset=200)

    if result['status_code'] != 200:
        logger.error(f"✗ Error extrayendo proyectos: HTTP {result['status_code']}")
        return False

    # Guardar raw data
    repo.insert_raw_data_bulk([result])

    # Parsear y tomar muestra
    proyectos = parser.parse_proyectos_from_response(result['data'])
    proyectos_sample = proyectos[:SAMPLE_SIZE]

    logger.info(f"Parseados {len(proyectos)} proyectos, tomando muestra de {len(proyectos_sample)}")

    # Guardar muestra
    inserted, duplicates = repo.insert_proyectos_bulk(proyectos_sample)

    logger.info(f"\n✓ Etapa 1 completada:")
    logger.info(f"  - Insertados: {inserted}")
    logger.info(f"  - Duplicados: {duplicates}")

    return True

def extract_documentos(db, http_client):
    """Etapa 2: Extraer documentos de expedientes."""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 2: EXTRACCIÓN DE DOCUMENTOS DEL EXPEDIENTE")
    logger.info("="*80 + "\n")

    # Obtener proyectos sin documentos (ordenados por ID DESC = más nuevos primero, fácil de validar)
    proyectos = db.fetch_all(
        f"""
        SELECT p.expediente_id, p.expediente_nombre
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
        ORDER BY p.expediente_id DESC
        LIMIT {DOCS_BATCH_SIZE}
        """,
        dictionary=True
    )

    if not proyectos:
        logger.info("✓ No hay proyectos pendientes de procesar")
        return True

    logger.info(f"Procesando {len(proyectos)} proyectos...")

    extractor = get_expediente_documentos_extractor(http_client)
    parser = get_expediente_documentos_parser()
    repo = get_expediente_documentos_repository(db)

    success_count = 0
    error_count = 0
    total_docs = 0

    for i, proyecto in enumerate(proyectos, 1):
        logger.info(f"[{i}/{len(proyectos)}] {proyecto['expediente_id']}")

        try:
            # Extraer
            result = extractor.extract_documentos(proyecto['expediente_id'])

            if result['status_code'] != 200:
                error_count += 1
                continue

            # Parsear
            documentos = parser.parse_documentos(
                result['html_content'],
                proyecto['expediente_id']
            )

            if not documentos:
                error_count += 1
                continue

            # Agregar metadata
            for doc in documentos:
                doc['extracted_at'] = result['extracted_at']
                doc['processing_status'] = 'success'
                doc['attempts'] = 1
                doc['last_attempt_at'] = datetime.now()

            # Guardar
            repo.insert_documentos_bulk(documentos)
            success_count += 1
            total_docs += len(documentos)
            logger.info(f"  ✓ {len(documentos)} documentos guardados")

        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Error: {str(e)}")

    logger.info(f"\n✓ Etapa 2 completada:")
    logger.info(f"  - Proyectos procesados: {len(proyectos)}")
    logger.info(f"  - Exitosos: {success_count}")
    logger.info(f"  - Errores: {error_count}")
    logger.info(f"  - Total documentos: {total_docs}")

    return True

def extract_pdf_links(db, http_client):
    """Etapa 3: Extraer links a PDFs de resumen ejecutivo."""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3: EXTRACCIÓN DE LINKS A PDF RESUMEN EJECUTIVO")
    logger.info("="*80 + "\n")

    # Obtener documentos sin link (ordenados por ID DESC = más nuevos primero, fácil de validar)
    documentos = db.fetch_all(
        f"""
        SELECT ed.id_documento, ed.expediente_id
        FROM expediente_documentos ed
        LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
        WHERE rel.id IS NULL
        ORDER BY ed.id_documento DESC
        LIMIT {LINKS_BATCH_SIZE}
        """,
        dictionary=True
    )

    if not documentos:
        logger.info("✓ No hay documentos pendientes de procesar")
        return True

    logger.info(f"Procesando {len(documentos)} documentos...")

    extractor = get_resumen_ejecutivo_extractor(http_client)
    parser = get_resumen_ejecutivo_parser()
    repo = get_resumen_ejecutivo_links_repository(db)

    success_count = 0
    error_count = 0
    error_types = {}

    for i, doc in enumerate(documentos, 1):
        logger.info(f"[{i}/{len(documentos)}] Documento {doc['id_documento']}")

        try:
            # Extraer
            result = extractor.extract_documento_content(doc['id_documento'])

            if result['status_code'] != 200:
                error_type = f"HTTP_{result['status_code']}"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1

                # Guardar error
                db.execute_query(
                    """
                    INSERT INTO resumen_ejecutivo_links
                    (id_documento, pdf_url, extracted_at, processing_status, error_type, error_message, attempts, last_attempt_at)
                    VALUES (%s, '', %s, 'error', %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        processing_status = 'error',
                        error_type = VALUES(error_type),
                        error_message = VALUES(error_message),
                        attempts = attempts + 1,
                        last_attempt_at = VALUES(last_attempt_at)
                    """,
                    (doc['id_documento'], datetime.now(), error_type, result.get('error_message'), datetime.now())
                )
                continue

            # Parsear
            link = parser.parse_resumen_ejecutivo_link(
                result['html_content'],
                doc['id_documento']
            )

            # El parser ahora siempre retorna dict, revisar si hay failure_reason
            if 'failure_reason' in link:
                error_type = "NO_RESUMEN_EJECUTIVO"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1

                # Guardar error con info de debug
                db.execute_query(
                    """
                    INSERT INTO resumen_ejecutivo_links
                    (id_documento, pdf_url, extracted_at, processing_status, error_type, error_message,
                     failure_reason, debug_snippet, attempts, last_attempt_at)
                    VALUES (%s, '', %s, 'error', %s, %s, %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        processing_status = 'error',
                        error_type = VALUES(error_type),
                        error_message = VALUES(error_message),
                        failure_reason = VALUES(failure_reason),
                        debug_snippet = VALUES(debug_snippet),
                        attempts = attempts + 1,
                        last_attempt_at = VALUES(last_attempt_at)
                    """,
                    (doc['id_documento'], datetime.now(), error_type, "No se encontró link al resumen ejecutivo",
                     link.get('failure_reason'), link.get('debug_snippet'), datetime.now())
                )
                continue

            # Agregar metadata
            link['extracted_at'] = result['extracted_at']
            link['processing_status'] = 'success'
            link['attempts'] = 1
            link['last_attempt_at'] = datetime.now()

            # Buscar documento firmado
            doc_firmado = parser.parse_documento_firmado_link(result['html_content'])
            if doc_firmado:
                link.update(doc_firmado)

            # Guardar
            repo.insert_links_bulk([link])
            success_count += 1
            logger.info(f"  ✓ Link guardado")

        except Exception as e:
            error_type = "EXCEPTION"
            error_types[error_type] = error_types.get(error_type, 0) + 1
            error_count += 1

            # Guardar error
            db.execute_query(
                """
                INSERT INTO resumen_ejecutivo_links
                (id_documento, pdf_url, extracted_at, processing_status, error_type, error_message, attempts, last_attempt_at)
                VALUES (%s, '', %s, 'error', %s, %s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    processing_status = 'error',
                    error_type = VALUES(error_type),
                    error_message = VALUES(error_message),
                    attempts = attempts + 1,
                    last_attempt_at = VALUES(last_attempt_at)
                """,
                (doc['id_documento'], datetime.now(), error_type, str(e), datetime.now())
            )

    logger.info(f"\n✓ Etapa 3 completada:")
    logger.info(f"  - Documentos procesados: {len(documentos)}")
    logger.info(f"  - Exitosos: {success_count} ({success_count/len(documentos)*100:.1f}%)")
    logger.info(f"  - Errores: {error_count} ({error_count/len(documentos)*100:.1f}%)")

    if error_types:
        logger.info(f"\n  Tipos de error:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"    • {error_type}: {count} ({count/error_count*100:.1f}%)")

    return True

def show_final_stats(db):
    """Mostrar estadísticas finales del pipeline."""
    logger.info("\n" + "="*80)
    logger.info("ESTADÍSTICAS FINALES")
    logger.info("="*80)

    # Proyectos
    proyectos_count = db.fetch_one("SELECT COUNT(*) as total FROM proyectos", dictionary=True)
    logger.info(f"\n📊 PROYECTOS: {proyectos_count['total']}")

    # Documentos
    docs_stats = db.fetch_one(
        """
        SELECT
            COUNT(*) as total_docs,
            COUNT(DISTINCT expediente_id) as proyectos_con_docs
        FROM expediente_documentos
        """,
        dictionary=True
    )

    pct_proyectos_con_docs = (docs_stats['proyectos_con_docs'] / proyectos_count['total'] * 100) if proyectos_count['total'] > 0 else 0

    logger.info(f"\n📄 DOCUMENTOS: {docs_stats['total_docs']}")
    logger.info(f"  - Proyectos con documentos: {docs_stats['proyectos_con_docs']} ({pct_proyectos_con_docs:.1f}%)")

    # Links
    links_stats = db.fetch_one(
        """
        SELECT
            COUNT(*) as total_links,
            SUM(CASE WHEN processing_status = 'success' THEN 1 ELSE 0 END) as exitosos,
            SUM(CASE WHEN processing_status = 'error' THEN 1 ELSE 0 END) as errores
        FROM resumen_ejecutivo_links
        """,
        dictionary=True
    )

    pct_exitosos = (links_stats['exitosos'] / links_stats['total_links'] * 100) if links_stats['total_links'] > 0 else 0

    logger.info(f"\n🔗 LINKS A PDF: {links_stats['total_links']}")
    logger.info(f"  - Exitosos: {links_stats['exitosos']} ({pct_exitosos:.1f}%)")
    logger.info(f"  - Errores: {links_stats['errores']} ({100-pct_exitosos:.1f}%)")

    # Conversión global
    conversion_rate = (links_stats['exitosos'] / proyectos_count['total'] * 100) if proyectos_count['total'] > 0 else 0
    logger.info(f"\n📈 CONVERSIÓN GLOBAL: {conversion_rate:.1f}%")
    logger.info(f"  ({links_stats['exitosos']} PDFs de {proyectos_count['total']} proyectos)")

    logger.info("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(description="Ejecutar pipeline completo con muestra")
    parser.add_argument("--clean", action="store_true", help="Limpiar BD antes de empezar")
    args = parser.parse_args()

    settings = get_settings()
    db = get_database_manager(settings)
    http_client = get_http_client(settings)

    try:
        # Cleanup opcional
        if args.clean:
            cleanup_all(db)

        # Ejecutar pipeline completo
        logger.info("\n" + "="*80)
        logger.info("INICIANDO PIPELINE COMPLETO CON MUESTRA")
        logger.info("="*80)

        # Verificar si ya tenemos proyectos en la BD
        existing_count = db.fetch_one("SELECT COUNT(*) as total FROM proyectos", dictionary=True)
        logger.info(f"\nProyectos existentes en BD: {existing_count['total']}")

        # Etapa 1: Proyectos (solo si no hay proyectos)
        if existing_count['total'] < SAMPLE_SIZE:
            if not extract_proyectos_sample(db, http_client, settings):
                logger.error("✗ Error en Etapa 1")
                return 1
        else:
            logger.info(f"⏭️  Saltando Etapa 1: Ya hay {existing_count['total']} proyectos en la BD")

        # Etapa 2: Documentos
        if not extract_documentos(db, http_client):
            logger.error("✗ Error en Etapa 2")
            return 1

        # Etapa 3: Links a PDFs
        if not extract_pdf_links(db, http_client):
            logger.error("✗ Error en Etapa 3")
            return 1

        # Estadísticas finales
        show_final_stats(db)

        logger.info("\n✅ PIPELINE COMPLETADO EXITOSAMENTE")

        logger.info("\nPara análisis detallado:")
        logger.info("  python error_report.py --stage 3")
        logger.info("  python stats.py")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Error fatal: {str(e)}", exc_info=True)
        return 1
    finally:
        db.close_connection()

if __name__ == "__main__":
    sys.exit(main())
