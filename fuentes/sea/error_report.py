"""
Error Report - Análisis de errores del pipeline.

Este script muestra estadísticas detalladas de qué está fallando y por qué,
permitiendo identificar el problema más común para arreglarlo.

Uso:
    python error_report.py --stage 2
    python error_report.py --stage 3 --top 10
"""
import argparse
import logging
from src.core.database import get_database_manager
from src.settings import get_settings

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def report_stage_2(db, top_n):
    """Generar reporte de errores para Etapa 2."""
    logger.info(f"\n{'='*80}")
    logger.info("REPORTE DE ERRORES - ETAPA 2: DOCUMENTOS DEL EXPEDIENTE")
    logger.info(f"{'='*80}\n")
    
    # Estadísticas generales
    stats = db.fetch_one(
        """
        SELECT
            COUNT(*) as total_proyectos,
            COUNT(DISTINCT ed.expediente_id) as proyectos_con_docs,
            COUNT(DISTINCT ed.expediente_id) - 
                SUM(CASE WHEN ed.processing_status = 'success' THEN 1 ELSE 0 END) as proyectos_con_errors
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        """,
        dictionary=True
    )
    
    logger.info("📊 ESTADÍSTICAS GENERALES")
    logger.info("-" * 80)
    logger.info(f"Total de proyectos:           {stats['total_proyectos']:>6}")
    logger.info(f"Proyectos procesados:         {stats['proyectos_con_docs']:>6}")
    logger.info(f"Proyectos pendientes:         {stats['total_proyectos'] - stats['proyectos_con_docs']:>6}")
    
    if stats['proyectos_con_docs'] > 0:
        tasa_procesamiento = stats['proyectos_con_docs'] / stats['total_proyectos'] * 100
        logger.info(f"Tasa de procesamiento:        {tasa_procesamiento:>5.1f}%\n")
    
    # No hay errores específicos en Etapa 2 por ahora (solo proyectos sin documentos)
    # Mostrar proyectos sin documentos
    sin_docs = db.fetch_all(
        """
        SELECT p.workflow_descripcion, p.estado_proyecto, COUNT(*) as total
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
        GROUP BY p.workflow_descripcion, p.estado_proyecto
        ORDER BY total DESC
        LIMIT %s
        """,
        (top_n,),
        dictionary=True
    )
    
    if sin_docs:
        logger.info("🔍 PROYECTOS SIN DOCUMENTOS (Top patterns)")
        logger.info("-" * 80)
        for row in sin_docs:
            logger.info(f"  • {row['workflow_descripcion']:8} | {row['estado_proyecto']:40} | {row['total']:>5} proyectos")

def report_stage_3(db, top_n):
    """Generar reporte de errores para Etapa 3."""
    logger.info(f"\n{'='*80}")
    logger.info("REPORTE DE ERRORES - ETAPA 3: LINKS A PDF RESUMEN EJECUTIVO")
    logger.info(f"{'='*80}\n")
    
    # Estadísticas generales
    stats = db.fetch_one(
        """
        SELECT
            COUNT(*) as total_documentos,
            SUM(CASE WHEN processing_status = 'success' THEN 1 ELSE 0 END) as exitosos,
            SUM(CASE WHEN processing_status = 'error' THEN 1 ELSE 0 END) as errores,
            SUM(CASE WHEN processing_status = 'pending' THEN 1 ELSE 0 END) as pendientes
        FROM resumen_ejecutivo_links
        """,
        dictionary=True
    )
    
    logger.info("📊 ESTADÍSTICAS GENERALES")
    logger.info("-" * 80)
    logger.info(f"Total de documentos procesados: {stats['total_documentos']:>6}")
    logger.info(f"  ✓ Exitosos:                   {stats['exitosos']:>6} ({stats['exitosos']/stats['total_documentos']*100 if stats['total_documentos'] > 0 else 0:>5.1f}%)")
    logger.info(f"  ✗ Con errores:                {stats['errores']:>6} ({stats['errores']/stats['total_documentos']*100 if stats['total_documentos'] > 0 else 0:>5.1f}%)")
    logger.info(f"  ⏳ Pendientes:                 {stats['pendientes']:>6} ({stats['pendientes']/stats['total_documentos']*100 if stats['total_documentos'] > 0 else 0:>5.1f}%)\n")
    
    # Tipos de error más comunes
    if stats['errores'] > 0:
        error_types = db.fetch_all(
            """
            SELECT error_type, COUNT(*) as total
            FROM resumen_ejecutivo_links
            WHERE processing_status = 'error'
            GROUP BY error_type
            ORDER BY total DESC
            LIMIT %s
            """,
            (top_n,),
            dictionary=True
        )
        
        logger.info("⚠️  TIPOS DE ERROR MÁS COMUNES")
        logger.info("-" * 80)
        for row in error_types:
            pct = row['total'] / stats['errores'] * 100
            logger.info(f"  • {row['error_type']:40} | {row['total']:>5} ({pct:>5.1f}%)")
        
        # Mostrar ejemplos del error más común
        if error_types:
            top_error = error_types[0]['error_type']
            logger.info(f"\n🔬 EJEMPLOS DEL ERROR MÁS COMÚN: {top_error}")
            logger.info("-" * 80)
            
            ejemplos = db.fetch_all(
                """
                SELECT rel.id_documento, rel.error_message, ed.expediente_id
                FROM resumen_ejecutivo_links rel
                LEFT JOIN expediente_documentos ed ON rel.id_documento = ed.id_documento
                WHERE rel.error_type = %s
                LIMIT 5
                """,
                (top_error,),
                dictionary=True
            )
            
            for ej in ejemplos:
                logger.info(f"  Documento: {ej['id_documento']} (Expediente: {ej['expediente_id']})")
                logger.info(f"    Error: {ej['error_message'][:100]}")
    
    # Documentos pendientes de procesar
    docs_pendientes = db.fetch_one(
        """
        SELECT COUNT(*) as total
        FROM expediente_documentos ed
        LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
        WHERE rel.id IS NULL
        """,
        dictionary=True
    )
    
    if docs_pendientes['total'] > 0:
        logger.info(f"\n📝 DOCUMENTOS PENDIENTES DE PROCESAR")
        logger.info("-" * 80)
        logger.info(f"  Total sin procesar: {docs_pendientes['total']:>6}")

def main():
    parser = argparse.ArgumentParser(description="Reporte de errores del pipeline SEA")
    parser.add_argument("--stage", type=int, required=True, choices=[2, 3], help="Etapa a reportar (2 o 3)")
    parser.add_argument("--top", type=int, default=10, help="Top N errores a mostrar")
    args = parser.parse_args()
    
    settings = get_settings()
    db = get_database_manager(settings)
    
    if args.stage == 2:
        report_stage_2(db, args.top)
    else:
        report_stage_3(db, args.top)
    
    logger.info(f"\n{'='*80}\n")
    
    db.close_connection()

if __name__ == "__main__":
    main()
