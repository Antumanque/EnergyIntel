"""
Batch Processor - Framework iterativo de procesamiento con tracking de errores.

Este script procesa proyectos en batches pequeños y trackea qué falla y por qué,
permitiendo iterar y mejorar el parser incrementalmente.

Uso:
    python batch_processor.py --batch-size 1000 --stage 2
    python batch_processor.py --batch-size 500 --stage 3
    python batch_processor.py --batch-size 100 --stage 4
"""
import argparse
import logging
from datetime import datetime
from src.core.database import get_database_manager
from src.core.http_client import get_http_client
from src.extractors.expediente_documentos import get_expediente_documentos_extractor
from src.extractors.resumen_ejecutivo import get_resumen_ejecutivo_extractor
from src.extractors.pdf_text import get_pdf_text_extractor
from src.parsers.expediente_documentos import get_expediente_documentos_parser
from src.parsers.resumen_ejecutivo import get_resumen_ejecutivo_parser
from src.parsers.proyecto_inteligencia import get_proyecto_inteligencia_parser
from src.repositories.expediente_documentos import get_expediente_documentos_repository
from src.repositories.resumen_ejecutivo_links import get_resumen_ejecutivo_links_repository
from src.repositories.proyecto_inteligencia import get_proyecto_inteligencia_repository
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_stage_2(db, http_client, batch_size):
    """
    Procesar Etapa 2: Extraer documentos del expediente.
    
    Args:
        db: Database manager
        http_client: HTTP client
        batch_size: Número de proyectos a procesar
    
    Returns:
        dict con estadísticas de procesamiento
    """
    logger.info(f"{'='*80}")
    logger.info("ETAPA 2: EXTRACCIÓN DE DOCUMENTOS DEL EXPEDIENTE")
    logger.info(f"{'='*80}\n")
    
    # Obtener proyectos pendientes (que no han sido intentados aún)
    # Excluye proyectos que ya tienen registros en expediente_documentos
    # (tanto éxitos como intentos fallidos)
    proyectos = db.fetch_all(
        f"""
        SELECT p.expediente_id, p.expediente_nombre, p.workflow_descripcion
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
        ORDER BY p.expediente_id DESC
        LIMIT {batch_size}
        """,
        dictionary=True
    )
    
    if not proyectos:
        logger.info("✓ No hay proyectos pendientes de procesar")
        return {"processed": 0, "success": 0, "errors": 0}
    
    logger.info(f"Procesando {len(proyectos)} proyectos...")
    
    extractor = get_expediente_documentos_extractor(http_client)
    parser = get_expediente_documentos_parser()
    repo = get_expediente_documentos_repository(db)
    
    success_count = 0
    error_count = 0
    
    for i, proyecto in enumerate(proyectos, 1):
        logger.info(f"[{i}/{len(proyectos)}] {proyecto['expediente_id']}: {proyecto['expediente_nombre'][:50]}...")

        try:
            # Extraer
            result = extractor.extract_documentos(proyecto['expediente_id'])

            if result['status_code'] != 200:
                # Insertar registro de intento fallido por error HTTP
                error_message = result.get('error_message', 'Unknown error')
                repo.insert_no_documents_record(
                    expediente_id=proyecto['expediente_id'],
                    extracted_at=result.get('extracted_at', datetime.now()),
                    failure_reason=f"HTTP {result['status_code']}: {error_message}",
                    processing_status='error'
                )
                error_count += 1
                logger.warning(f"  ✗ HTTP {result['status_code']}: {error_message}")
                continue

            # Parsear
            documentos = parser.parse_documentos(
                result['html_content'],
                proyecto['expediente_id']
            )

            if not documentos:
                # Insertar registro indicando que no se encontraron documentos EIA/DIA
                repo.insert_no_documents_record(
                    expediente_id=proyecto['expediente_id'],
                    extracted_at=result['extracted_at'],
                    failure_reason="No se encontraron documentos EIA/DIA en el expediente",
                    processing_status='no_documents'
                )
                error_count += 1
                logger.warning(f"  ✗ No se encontraron documentos")
                continue

            # Agregar extracted_at y marcar como success
            for doc in documentos:
                doc['extracted_at'] = result['extracted_at']
                doc['processing_status'] = 'success'
                doc['attempts'] = 1
                doc['last_attempt_at'] = datetime.now()

            # Guardar
            repo.insert_documentos_bulk(documentos)
            success_count += 1
            logger.info(f"  ✓ {len(documentos)} documentos guardados")

        except Exception as e:
            # Insertar registro de excepción
            repo.insert_no_documents_record(
                expediente_id=proyecto['expediente_id'],
                extracted_at=datetime.now(),
                failure_reason=f"Exception: {str(e)}",
                processing_status='error'
            )
            error_count += 1
            logger.error(f"  ✗ Error: {str(e)}")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"RESULTADOS ETAPA 2:")
    logger.info(f"  Procesados: {len(proyectos)}")
    logger.info(f"  Exitosos:   {success_count} ({success_count/len(proyectos)*100:.1f}%)")
    logger.info(f"  Errores:    {error_count} ({error_count/len(proyectos)*100:.1f}%)")
    logger.info(f"{'='*80}\n")
    
    return {
        "processed": len(proyectos),
        "success": success_count,
        "errors": error_count
    }

def process_stage_3(db, http_client, batch_size, reprocess_errors=False):
    """
    Procesar Etapa 3: Extraer links a PDF de resumen ejecutivo.

    Args:
        db: Database manager
        http_client: HTTP client
        batch_size: Número de documentos a procesar
        reprocess_errors: Si True, reprocesa documentos con errores previos

    Returns:
        dict con estadísticas de procesamiento
    """
    logger.info(f"{'='*80}")
    logger.info("ETAPA 3: EXTRACCIÓN DE LINKS A PDF RESUMEN EJECUTIVO")
    if reprocess_errors:
        logger.info("MODO: Reprocesando errores previos")
    logger.info(f"{'='*80}\n")

    # Obtener documentos pendientes
    if reprocess_errors:
        # Reprocesar documentos que fallaron antes (solo IDs positivos = publicados)
        documentos = db.fetch_all(
            f"""
            SELECT ed.id_documento, ed.expediente_id
            FROM expediente_documentos ed
            INNER JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
            WHERE rel.processing_status = 'error'
              AND ed.id_documento > 0
            LIMIT {batch_size}
            """,
            dictionary=True
        )
    else:
        # Solo documentos sin link aún (comportamiento original)
        documentos = db.fetch_all(
            f"""
            SELECT ed.id_documento, ed.expediente_id
            FROM expediente_documentos ed
            LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
            WHERE rel.id IS NULL
            LIMIT {batch_size}
            """,
            dictionary=True
        )
    
    if not documentos:
        logger.info("✓ No hay documentos pendientes de procesar")
        return {"processed": 0, "success": 0, "errors": 0}
    
    logger.info(f"Procesando {len(documentos)} documentos...")
    
    extractor = get_resumen_ejecutivo_extractor(http_client)
    parser = get_resumen_ejecutivo_parser()
    repo = get_resumen_ejecutivo_links_repository(db)
    
    success_count = 0
    error_count = 0
    error_types = {}
    
    for i, doc in enumerate(documentos, 1):
        logger.info(f"[{i}/{len(documentos)}] Documento {doc['id_documento']}...")
        
        try:
            # Extraer
            result = extractor.extract_documento_content(doc['id_documento'])
            
            if result['status_code'] != 200:
                error_type = f"HTTP_{result['status_code']}"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}: {result.get('error_message', 'Unknown error')}")
                
                # Guardar error en BD
                db.execute_query(
                    """
                    INSERT INTO resumen_ejecutivo_links 
                    (id_documento, processing_status, error_type, error_message, attempts, last_attempt_at)
                    VALUES (%s, 'error', %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        processing_status = 'error',
                        error_type = VALUES(error_type),
                        error_message = VALUES(error_message),
                        attempts = attempts + 1,
                        last_attempt_at = VALUES(last_attempt_at)
                    """,
                    (doc['id_documento'], error_type, result.get('error_message'), datetime.now())
                )
                continue
            
            # Parsear
            link = parser.parse_resumen_ejecutivo_link(
                result['html_content'],
                doc['id_documento']
            )

            if not link or 'pdf_url' not in link:
                error_type = "NO_RESUMEN_EJECUTIVO"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}")

                # Guardar error en BD con pdf_url = NULL
                db.execute_query(
                    """
                    INSERT INTO resumen_ejecutivo_links
                    (id_documento, pdf_url, processing_status, error_type, error_message, attempts, last_attempt_at, extracted_at, match_criteria)
                    VALUES (%s, NULL, 'error', %s, %s, 1, %s, %s, NULL)
                    ON DUPLICATE KEY UPDATE
                        processing_status = 'error',
                        error_type = VALUES(error_type),
                        error_message = VALUES(error_message),
                        attempts = attempts + 1,
                        last_attempt_at = VALUES(last_attempt_at)
                    """,
                    (doc['id_documento'], error_type, "No se encontró link al resumen ejecutivo", datetime.now(), result['extracted_at'])
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
            logger.info(f"  ✓ Link guardado: {link['texto_link']}")
            
        except Exception as e:
            error_type = "EXCEPTION"
            error_types[error_type] = error_types.get(error_type, 0) + 1
            error_count += 1
            logger.error(f"  ✗ {error_type}: {str(e)}")

            # Guardar error en BD con pdf_url = NULL
            db.execute_query(
                """
                INSERT INTO resumen_ejecutivo_links
                (id_documento, pdf_url, processing_status, error_type, error_message, attempts, last_attempt_at, extracted_at, match_criteria)
                VALUES (%s, NULL, 'error', %s, %s, 1, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE
                    processing_status = 'error',
                    error_type = VALUES(error_type),
                    error_message = VALUES(error_message),
                    attempts = attempts + 1,
                    last_attempt_at = VALUES(last_attempt_at)
                """,
                (doc['id_documento'], error_type, str(e), datetime.now(), datetime.now())
            )
    
    logger.info(f"\n{'='*80}")
    logger.info(f"RESULTADOS ETAPA 3:")
    logger.info(f"  Procesados: {len(documentos)}")
    logger.info(f"  Exitosos:   {success_count} ({success_count/len(documentos)*100:.1f}%)")
    logger.info(f"  Errores:    {error_count} ({error_count/len(documentos)*100:.1f}%)")
    
    if error_types:
        logger.info(f"\n  Tipos de error:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"    • {error_type}: {count} ({count/error_count*100:.1f}%)")
    
    logger.info(f"{'='*80}\n")
    
    return {
        "processed": len(documentos),
        "success": success_count,
        "errors": error_count,
        "error_types": error_types
    }

def process_stage_4(db, http_client, batch_size, reprocess_errors=False):
    """
    Procesar Etapa 4: Extraer inteligencia de negocio con Claude Haiku 4.5.

    Args:
        db: Database manager
        http_client: HTTP client
        batch_size: Número de documentos a procesar
        reprocess_errors: Si True, reprocesa documentos con errores previos

    Returns:
        dict con estadísticas de procesamiento
    """
    logger.info(f"{'='*80}")
    logger.info("ETAPA 4: EXTRACCIÓN DE INTELIGENCIA CON CLAUDE HAIKU 4.5")
    if reprocess_errors:
        logger.info("MODO: Reprocesando errores previos")
    logger.info(f"{'='*80}\n")

    # Obtener documentos pendientes
    if reprocess_errors:
        # Reprocesar documentos que fallaron antes
        documentos = db.fetch_all(
            f"""
            SELECT pi.id_documento, rel.pdf_url
            FROM proyecto_inteligencia pi
            JOIN resumen_ejecutivo_links rel ON pi.id_documento = rel.id_documento
            WHERE pi.status = 'error'
            AND rel.pdf_url IS NOT NULL
            LIMIT {batch_size}
            """,
            dictionary=True
        )
    else:
        # Solo documentos sin inteligencia aún (con pdf_url válido)
        documentos = db.fetch_all(
            f"""
            SELECT rel.id_documento, rel.pdf_url
            FROM resumen_ejecutivo_links rel
            LEFT JOIN proyecto_inteligencia pi ON rel.id_documento = pi.id_documento
            WHERE pi.id IS NULL
            AND rel.pdf_url IS NOT NULL
            ORDER BY rel.id_documento DESC
            LIMIT {batch_size}
            """,
            dictionary=True
        )

    if not documentos:
        logger.info("✓ No hay documentos pendientes de procesar")
        return {"processed": 0, "success": 0, "errors": 0}

    logger.info(f"Procesando {len(documentos)} documentos...")

    pdf_extractor = get_pdf_text_extractor(http_client)
    inteligencia_parser = get_proyecto_inteligencia_parser()
    repo = get_proyecto_inteligencia_repository(db)

    success_count = 0
    error_count = 0
    error_types = {}

    for i, doc in enumerate(documentos, 1):
        logger.info(f"[{i}/{len(documentos)}] Documento {doc['id_documento']}...")

        try:
            # 1. Extraer texto del PDF
            result = pdf_extractor.extract_text_from_url(
                doc['pdf_url'],
                doc['id_documento']
            )

            if 'error_message' in result:
                error_type = "PDF_EXTRACTION_ERROR"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}: {result['error_message']}")

                # Guardar error en BD
                repo.insert_inteligencia({
                    "id_documento": doc['id_documento'],
                    "status": "error",
                    "error_message": result['error_message']
                })
                continue

            pdf_text = result.get('pdf_text')
            if not pdf_text:
                error_type = "EMPTY_PDF_TEXT"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}")

                repo.insert_inteligencia({
                    "id_documento": doc['id_documento'],
                    "status": "error",
                    "error_message": "No se pudo extraer texto del PDF"
                })
                continue

            # 2. Analizar con Claude
            logger.info(f"  → Analizando con Claude ({len(pdf_text)} caracteres)...")
            inteligencia = inteligencia_parser.parse_proyecto_intelligence(
                pdf_text,
                doc['id_documento']
            )

            if inteligencia.get('status') == 'error':
                error_type = "CLAUDE_ANALYSIS_ERROR"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}: {inteligencia.get('error_message')}")

                # Guardar error en BD
                repo.insert_inteligencia(inteligencia)
                continue

            # 3. Guardar inteligencia
            repo.insert_inteligencia(inteligencia)
            success_count += 1
            logger.info(f"  ✓ Industria: {inteligencia.get('industria')} | Energía: {inteligencia.get('es_energia')}")

        except Exception as e:
            error_type = "EXCEPTION"
            error_types[error_type] = error_types.get(error_type, 0) + 1
            error_count += 1
            logger.error(f"  ✗ {error_type}: {str(e)}")

            # Guardar error en BD
            repo.insert_inteligencia({
                "id_documento": doc['id_documento'],
                "status": "error",
                "error_message": f"Excepción: {str(e)}"
            })

    logger.info(f"\n{'='*80}")
    logger.info(f"RESULTADOS ETAPA 4:")
    logger.info(f"  Procesados: {len(documentos)}")
    logger.info(f"  Exitosos:   {success_count} ({success_count/len(documentos)*100:.1f}%)")
    logger.info(f"  Errores:    {error_count} ({error_count/len(documentos)*100:.1f}%)")

    if error_types:
        logger.info(f"\n  Tipos de error:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"    • {error_type}: {count} ({count/error_count*100:.1f}%)")

    logger.info(f"{'='*80}\n")

    return {
        "processed": len(documentos),
        "success": success_count,
        "errors": error_count,
        "error_types": error_types
    }

def main():
    parser = argparse.ArgumentParser(description="Batch processor para pipeline SEA")
    parser.add_argument("--batch-size", type=int, default=1000, help="Tamaño del batch")
    parser.add_argument("--stage", type=int, required=True, choices=[2, 3, 4], help="Etapa a procesar (2, 3 o 4)")
    parser.add_argument("--reprocess-errors", action="store_true", help="Reprocesar documentos con errores previos")
    args = parser.parse_args()

    settings = get_settings()
    db = get_database_manager(settings)
    http_client = get_http_client(settings)

    if args.stage == 2:
        results = process_stage_2(db, http_client, args.batch_size)
    elif args.stage == 3:
        results = process_stage_3(db, http_client, args.batch_size, reprocess_errors=args.reprocess_errors)
    else:
        results = process_stage_4(db, http_client, args.batch_size, reprocess_errors=args.reprocess_errors)

    db.close_connection()

    logger.info("✓ Procesamiento completado")
    logger.info(f"\nPara ver reporte de errores, ejecuta:")
    logger.info(f"  python error_report.py --stage {args.stage}")

if __name__ == "__main__":
    main()
