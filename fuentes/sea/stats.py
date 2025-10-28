"""
Script para generar estadísticas detalladas del pipeline.

Muestra qué proyectos tienen datos en cada etapa y dónde se pierde información.
"""
import logging
from src.core.database import get_database_manager
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def print_section(title):
    logger.info("\n" + "=" * 80)
    logger.info(title)
    logger.info("=" * 80)

def main():
    settings = get_settings()
    db = get_database_manager(settings)

    print_section("ESTADÍSTICAS DEL PIPELINE SEA")

    # ETAPA 1: Proyectos
    logger.info("\n📊 ETAPA 1 - PROYECTOS")
    logger.info("-" * 80)

    stats = db.fetch_one(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN workflow_descripcion = 'DIA' THEN 1 ELSE 0 END) as dias,
            SUM(CASE WHEN workflow_descripcion = 'EIA' THEN 1 ELSE 0 END) as eias
        FROM proyectos
        """,
        dictionary=True
    )

    logger.info(f"Total de proyectos:     {stats['total']:>6}")
    logger.info(f"  • DIAs:               {stats['dias']:>6} ({stats['dias']/stats['total']*100:.1f}%)")
    logger.info(f"  • EIAs:               {stats['eias']:>6} ({stats['eias']/stats['total']*100:.1f}%)")

    # Proyectos por estado
    logger.info("\nPor estado:")
    estados = db.fetch_all(
        """
        SELECT estado_proyecto, COUNT(*) as total
        FROM proyectos
        GROUP BY estado_proyecto
        ORDER BY total DESC
        LIMIT 10
        """,
        dictionary=True
    )

    for estado in estados:
        pct = estado['total'] / stats['total'] * 100
        logger.info(f"  • {estado['estado_proyecto']:<30} {estado['total']:>6} ({pct:>5.1f}%)")

    # ETAPA 2: Documentos
    logger.info("\n📄 ETAPA 2 - DOCUMENTOS DEL EXPEDIENTE")
    logger.info("-" * 80)

    doc_stats = db.fetch_one(
        """
        SELECT
            COUNT(DISTINCT p.expediente_id) as proyectos_totales,
            COUNT(DISTINCT ed.expediente_id) as proyectos_con_docs,
            COUNT(ed.id) as total_documentos
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        """,
        dictionary=True
    )

    cobertura_docs = (doc_stats['proyectos_con_docs'] / doc_stats['proyectos_totales'] * 100) if doc_stats['proyectos_totales'] > 0 else 0

    logger.info(f"Proyectos con documentos: {doc_stats['proyectos_con_docs']:>6} / {doc_stats['proyectos_totales']:>6} ({cobertura_docs:.1f}%)")
    logger.info(f"Total de documentos:      {doc_stats['total_documentos']:>6}")

    if doc_stats['proyectos_con_docs'] > 0:
        promedio_docs = doc_stats['total_documentos'] / doc_stats['proyectos_con_docs']
        logger.info(f"Documentos por proyecto:  {promedio_docs:>6.1f} (promedio)")

    # Proyectos SIN documentos por tipo
    logger.info("\nProyectos SIN documentos:")
    sin_docs = db.fetch_all(
        """
        SELECT
            p.workflow_descripcion,
            COUNT(*) as total
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
        GROUP BY p.workflow_descripcion
        """,
        dictionary=True
    )

    for row in sin_docs:
        logger.info(f"  • {row['workflow_descripcion']}: {row['total']:>6} proyectos sin documentos")

    # ETAPA 3: Links a PDFs
    logger.info("\n📑 ETAPA 3 - LINKS A PDFs DE RESUMEN EJECUTIVO")
    logger.info("-" * 80)

    pdf_stats = db.fetch_one(
        """
        SELECT
            COUNT(DISTINCT ed.id_documento) as documentos_totales,
            COUNT(DISTINCT rel.id_documento) as documentos_con_pdf,
            COUNT(rel.id) as total_links
        FROM expediente_documentos ed
        LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
        """,
        dictionary=True
    )

    cobertura_pdf = (pdf_stats['documentos_con_pdf'] / pdf_stats['documentos_totales'] * 100) if pdf_stats['documentos_totales'] > 0 else 0

    logger.info(f"Documentos con link a PDF: {pdf_stats['documentos_con_pdf']:>6} / {pdf_stats['documentos_totales']:>6} ({cobertura_pdf:.1f}%)")
    logger.info(f"Total de links:            {pdf_stats['total_links']:>6}")

    # Estados de los links
    if pdf_stats['total_links'] > 0:
        logger.info("\nEstados de los links:")
        link_estados = db.fetch_all(
            """
            SELECT status, COUNT(*) as total
            FROM resumen_ejecutivo_links
            GROUP BY status
            ORDER BY total DESC
            """,
            dictionary=True
        )

        for row in link_estados:
            pct = row['total'] / pdf_stats['total_links'] * 100
            logger.info(f"  • {row['status']:<20} {row['total']:>6} ({pct:>5.1f}%)")

    # CONVERSIÓN COMPLETA
    logger.info("\n🔄 CONVERSIÓN COMPLETA DEL PIPELINE")
    logger.info("-" * 80)

    conversion = db.fetch_one(
        """
        SELECT
            COUNT(DISTINCT p.expediente_id) as total_proyectos,
            COUNT(DISTINCT ed.expediente_id) as con_documentos,
            COUNT(DISTINCT CASE WHEN rel.id IS NOT NULL THEN p.expediente_id END) as con_pdf
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
        """,
        dictionary=True
    )

    tasa_docs = (conversion['con_documentos'] / conversion['total_proyectos'] * 100) if conversion['total_proyectos'] > 0 else 0
    tasa_pdf = (conversion['con_pdf'] / conversion['total_proyectos'] * 100) if conversion['total_proyectos'] > 0 else 0

    logger.info(f"Proyectos totales:           {conversion['total_proyectos']:>6}")
    logger.info(f"  → Con documentos:          {conversion['con_documentos']:>6} ({tasa_docs:>5.1f}%)")
    logger.info(f"  → Con PDF de resumen:      {conversion['con_pdf']:>6} ({tasa_pdf:>5.1f}%)")

    # PÉRDIDA DE DATOS
    logger.info("\n⚠️  PÉRDIDA DE DATOS POR ETAPA")
    logger.info("-" * 80)

    perdida_etapa1_2 = conversion['total_proyectos'] - conversion['con_documentos']
    perdida_pct_1_2 = (perdida_etapa1_2 / conversion['total_proyectos'] * 100) if conversion['total_proyectos'] > 0 else 0

    logger.info(f"Etapa 1 → 2:  {perdida_etapa1_2:>6} proyectos sin documentos ({perdida_pct_1_2:.1f}%)")

    if conversion['con_documentos'] > 0:
        perdida_etapa2_3 = conversion['con_documentos'] - conversion['con_pdf']
        perdida_pct_2_3 = (perdida_etapa2_3 / conversion['con_documentos'] * 100)
        logger.info(f"Etapa 2 → 3:  {perdida_etapa2_3:>6} documentos sin PDF ({perdida_pct_2_3:.1f}%)")

    # EJEMPLOS DE PROYECTOS CON DATOS COMPLETOS
    logger.info("\n✅ EJEMPLOS DE PROYECTOS CON DATOS COMPLETOS")
    logger.info("-" * 80)

    ejemplos = db.fetch_all(
        """
        SELECT
            p.expediente_id,
            p.expediente_nombre,
            p.workflow_descripcion,
            p.estado_proyecto,
            rel.pdf_filename
        FROM proyectos p
        INNER JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        INNER JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
        LIMIT 5
        """,
        dictionary=True
    )

    if ejemplos:
        for ej in ejemplos:
            logger.info(f"\nProyecto: {ej['expediente_nombre'][:60]}")
            logger.info(f"  ID: {ej['expediente_id']}")
            logger.info(f"  Tipo: {ej['workflow_descripcion']}")
            logger.info(f"  Estado: {ej['estado_proyecto']}")
            logger.info(f"  PDF: {ej['pdf_filename']}")
    else:
        logger.info("(Aún no hay proyectos con datos completos)")

    # TOP PROYECTOS SIN DOCUMENTOS (para investigar)
    logger.info("\n🔍 EJEMPLOS DE PROYECTOS SIN DOCUMENTOS (para investigar)")
    logger.info("-" * 80)

    sin_docs_ejemplos = db.fetch_all(
        """
        SELECT
            p.expediente_id,
            p.expediente_nombre,
            p.workflow_descripcion,
            p.estado_proyecto
        FROM proyectos p
        LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
        WHERE ed.id IS NULL
        AND p.workflow_descripcion = 'EIA'
        LIMIT 5
        """,
        dictionary=True
    )

    if sin_docs_ejemplos:
        for ej in sin_docs_ejemplos:
            logger.info(f"\nProyecto: {ej['expediente_nombre'][:60]}")
            logger.info(f"  ID: {ej['expediente_id']}")
            logger.info(f"  Tipo: {ej['workflow_descripcion']}")
            logger.info(f"  Estado: {ej['estado_proyecto']}")
    else:
        logger.info("(Todos los EIAs tienen documentos)")

    logger.info("\n" + "=" * 80)
    db.close_connection()

if __name__ == "__main__":
    main()
