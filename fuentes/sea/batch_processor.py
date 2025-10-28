"""
Batch Processor - Framework iterativo de procesamiento con tracking de errores.

Este script procesa proyectos en batches pequeños y trackea qué falla y por qué,
permitiendo iterar y mejorar el parser incrementalmente.

Uso:
    python batch_processor.py --batch-size 1000 --stage 2
    python batch_processor.py --batch-size 500 --stage 3
"""
import argparse
import logging
from datetime import datetime
from src.core.database import get_database_manager
from src.core.http_client import get_http_client
from src.extractors.expediente_documentos import get_expediente_documentos_extractor
from src.extractors.resumen_ejecutivo import get_resumen_ejecutivo_extractor
from src.parsers.expediente_documentos import get_expediente_documentos_parser
from src.parsers.resumen_ejecutivo import get_resumen_ejecutivo_parser
from src.repositories.expediente_documentos import get_expediente_documentos_repository
from src.repositories.resumen_ejecutivo_links import get_resumen_ejecutivo_links_repository
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
    
    # Obtener proyectos pendientes (sin documentos aún)
    proyectos = db.fetch_all(
        f"""
        SELECT p.expediente_id, p.expediente_nombre, p.workflow_descripcion
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
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
                error_count += 1
                logger.warning(f"  ✗ HTTP {result['status_code']}: {result.get('error_message', 'Unknown error')}")
                continue
            
            # Parsear
            documentos = parser.parse_documentos(
                result['html_content'],
                proyecto['expediente_id']
            )
            
            if not documentos:
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

def process_stage_3(db, http_client, batch_size):
    """
    Procesar Etapa 3: Extraer links a PDF de resumen ejecutivo.
    
    Args:
        db: Database manager
        http_client: HTTP client
        batch_size: Número de documentos a procesar
    
    Returns:
        dict con estadísticas de procesamiento
    """
    logger.info(f"{'='*80}")
    logger.info("ETAPA 3: EXTRACCIÓN DE LINKS A PDF RESUMEN EJECUTIVO")
    logger.info(f"{'='*80}\n")
    
    # Obtener documentos pendientes (sin link aún)
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
            
            if not link:
                error_type = "NO_RESUMEN_EJECUTIVO"
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_count += 1
                logger.warning(f"  ✗ {error_type}")
                
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
                    (doc['id_documento'], error_type, "No se encontró link al resumen ejecutivo", datetime.now())
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
                (doc['id_documento'], error_type, str(e), datetime.now())
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

def main():
    parser = argparse.ArgumentParser(description="Batch processor para pipeline SEA")
    parser.add_argument("--batch-size", type=int, default=1000, help="Tamaño del batch")
    parser.add_argument("--stage", type=int, required=True, choices=[2, 3], help="Etapa a procesar (2 o 3)")
    args = parser.parse_args()
    
    settings = get_settings()
    db = get_database_manager(settings)
    http_client = get_http_client(settings)
    
    if args.stage == 2:
        results = process_stage_2(db, http_client, args.batch_size)
    else:
        results = process_stage_3(db, http_client, args.batch_size)
    
    db.close_connection()
    
    logger.info("✓ Procesamiento completado")
    logger.info(f"\nPara ver reporte de errores, ejecuta:")
    logger.info(f"  python error_report.py --stage {args.stage}")

if __name__ == "__main__":
    main()
