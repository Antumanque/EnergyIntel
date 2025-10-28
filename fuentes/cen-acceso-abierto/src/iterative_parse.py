#!/usr/bin/env python3
"""
Framework Iterativo de Parsing con Feedback

Este es EL SCRIPT MÁS IMPORTANTE del proyecto.
Permite mejorar el parser de forma sistemática e iterativa.

Uso:
    # Primera iteración - parsear batch
    python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 1

    # Ver feedback de iteración
    python -m src.iterative_parse --feedback --iteracion 1 --tipo SUCTD

    # Re-parse después de fix
    python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 2 --reparse

    # Comparar iteraciones
    python -m src.iterative_parse --compare --tipo SUCTD
"""

import logging
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import Counter
import mysql.connector

from src.parsers.pdf_suctd import SUCTDPDFParser
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_feedback_table_exists(conn):
    """Crea la tabla parsing_feedback si no existe."""
    cursor = conn.cursor()

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS parsing_feedback (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,

        -- Iteración
        iteracion INT NOT NULL,
        fecha_iteracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        parser_version VARCHAR(50),

        -- Estadísticas Generales
        tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE') NOT NULL,
        total_documentos INT NOT NULL,
        documentos_exitosos INT NOT NULL,
        documentos_fallidos INT NOT NULL,
        tasa_exito DECIMAL(5,2),

        -- Errores Agrupados
        error_pattern VARCHAR(500),
        error_count INT,
        error_sample_ids TEXT,

        -- Campos Faltantes Más Comunes
        campos_faltantes_top JSON,

        -- Metadata
        notas TEXT,
        duracion_segundos INT,

        INDEX idx_iteracion (iteracion),
        INDEX idx_tipo (tipo_formulario),
        INDEX idx_fecha (fecha_iteracion)
    );
    """

    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()


def get_documents_to_parse(
    tipo: str,
    limit: Optional[int] = None,
    reparse: bool = False
) -> List[Dict[str, Any]]:
    """
    Obtiene documentos a parsear.

    Args:
        tipo: Tipo de formulario (SUCTD, SAC, FEHACIENTE)
        limit: Límite de documentos
        reparse: Si True, incluye documentos ya parseados

    Returns:
        Lista de documentos
    """
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    tipo_documento_map = {
        "SUCTD": "Formulario SUCTD",
        "SAC": "Formulario SAC",
        "FEHACIENTE": "Formulario_proyecto_fehaciente"
    }

    if reparse:
        # Re-parsear TODOS los documentos
        query = """
        SELECT
            d.id AS documento_id,
            d.local_path,
            d.solicitud_id,
            s.proyecto,
            fp.id AS formulario_parseado_id
        FROM documentos d
        INNER JOIN solicitudes s ON d.solicitud_id = s.id
        LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
        WHERE d.tipo_documento = %s
          AND d.local_path LIKE '%.pdf'
          AND d.downloaded = 1
        ORDER BY d.id
        """
    else:
        # Solo documentos NO parseados
        query = """
        SELECT
            d.id AS documento_id,
            d.local_path,
            d.solicitud_id,
            s.proyecto
        FROM documentos d
        INNER JOIN solicitudes s ON d.solicitud_id = s.id
        LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
        WHERE d.tipo_documento = %s
          AND d.local_path LIKE '%.pdf'
          AND d.downloaded = 1
          AND fp.id IS NULL
        ORDER BY d.id
        """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, (tipo_documento_map[tipo],))
    docs = cursor.fetchall()

    cursor.close()
    conn.close()

    return docs


def parse_batch(
    tipo: str,
    docs: List[Dict[str, Any]],
    parser_version: str
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Parsea un batch de documentos.

    Returns:
        (exitosos, fallidos, lista_errores)
    """
    logger.info(f"🔧 Parser: {tipo} v{parser_version}")
    logger.info(f"📊 Documentos a procesar: {len(docs)}")
    logger.info("")

    # Inicializar parser
    if tipo == "SUCTD":
        parser = SUCTDPDFParser()
    # TODO: elif tipo == "SAC": parser = SACPDFParser()
    # TODO: elif tipo == "FEHACIENTE": parser = FEHACIENTEPDFParser()
    else:
        raise ValueError(f"Tipo no soportado: {tipo}")

    # Conexión BD
    settings = get_settings()
    db_config = settings.get_db_config()
    conn = mysql.connector.connect(**db_config)

    exitosos = 0
    fallidos = 0
    errores_detalle = []

    for i, doc in enumerate(docs, 1):
        documento_id = doc['documento_id']
        local_path = doc['local_path']
        solicitud_id = doc['solicitud_id']
        proyecto = doc['proyecto']

        if i % 100 == 0:
            logger.info(f"  [{i}/{len(docs)}] Progreso: {exitosos} exitosos, {fallidos} fallidos")

        # Verificar archivo existe
        pdf_path = Path(local_path)
        if not pdf_path.exists():
            fallidos += 1
            errores_detalle.append({
                "documento_id": documento_id,
                "error": "Archivo no encontrado",
                "proyecto": proyecto
            })
            continue

        try:
            # Parsear
            data = parser.parse(str(pdf_path))

            # Validar campos críticos
            critical_fields = ["razon_social", "rut", "nombre_proyecto"]
            missing = [f for f in critical_fields if not data.get(f)]

            if missing:
                # Parsing fallido
                fallidos += 1
                error_msg = f"Campos críticos faltantes: {', '.join(missing)}"
                errores_detalle.append({
                    "documento_id": documento_id,
                    "error": error_msg,
                    "proyecto": proyecto,
                    "campos_faltantes": missing
                })

                # Guardar en BD (parsing fallido)
                save_failed_parsing(conn, documento_id, tipo, error_msg, parser_version)
            else:
                # Parsing exitoso
                exitosos += 1

                # Guardar en BD
                save_successful_parsing(conn, documento_id, solicitud_id, tipo, data, parser_version)

        except Exception as e:
            fallidos += 1
            error_msg = str(e)[:500]
            errores_detalle.append({
                "documento_id": documento_id,
                "error": error_msg,
                "proyecto": proyecto
            })

            # Guardar en BD (parsing fallido)
            save_failed_parsing(conn, documento_id, tipo, error_msg, parser_version)

    conn.close()

    logger.info("")
    logger.info(f"✅ Exitosos: {exitosos}")
    logger.info(f"❌ Fallidos: {fallidos}")

    return exitosos, fallidos, errores_detalle


def save_failed_parsing(conn, documento_id: int, tipo: str, error: str, parser_version: str):
    """Guarda parsing fallido en BD."""
    cursor = conn.cursor()

    # Verificar si ya existe
    check_query = "SELECT id FROM formularios_parseados WHERE documento_id = %s"
    cursor.execute(check_query, (documento_id,))
    existing = cursor.fetchone()

    if existing:
        # UPDATE
        update_query = """
        UPDATE formularios_parseados
        SET parsing_exitoso = 0,
            parsing_error = %s,
            parser_version = %s,
            parsed_at = NOW()
        WHERE documento_id = %s
        """
        cursor.execute(update_query, (error, parser_version, documento_id))
    else:
        # INSERT
        insert_query = """
        INSERT INTO formularios_parseados (
            documento_id, tipo_formulario, formato_archivo,
            parsing_exitoso, parsing_error, parser_version
        ) VALUES (%s, %s, 'PDF', 0, %s, %s)
        """
        cursor.execute(insert_query, (documento_id, tipo, error, parser_version))

    conn.commit()
    cursor.close()


def save_successful_parsing(
    conn,
    documento_id: int,
    solicitud_id: int,
    tipo: str,
    data: Dict[str, Any],
    parser_version: str
):
    """Guarda parsing exitoso en BD."""
    # TODO: Implementar guardado completo en formularios_*_parsed
    cursor = conn.cursor()

    # Por ahora solo guardar en formularios_parseados
    check_query = "SELECT id FROM formularios_parseados WHERE documento_id = %s"
    cursor.execute(check_query, (documento_id,))
    existing = cursor.fetchone()

    if existing:
        update_query = """
        UPDATE formularios_parseados
        SET parsing_exitoso = 1,
            parsing_error = NULL,
            parser_version = %s,
            parsed_at = NOW()
        WHERE documento_id = %s
        """
        cursor.execute(update_query, (parser_version, documento_id))
    else:
        insert_query = """
        INSERT INTO formularios_parseados (
            documento_id, tipo_formulario, formato_archivo,
            parsing_exitoso, parser_version
        ) VALUES (%s, %s, 'PDF', 1, %s)
        """
        cursor.execute(insert_query, (documento_id, tipo, parser_version))

    conn.commit()
    cursor.close()


def save_feedback(
    iteracion: int,
    tipo: str,
    parser_version: str,
    total: int,
    exitosos: int,
    fallidos: int,
    errores_detalle: List[Dict[str, Any]],
    duracion: int,
    notas: Optional[str] = None
):
    """Guarda feedback de la iteración en BD."""
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    ensure_feedback_table_exists(conn)

    cursor = conn.cursor()

    tasa_exito = (exitosos / total * 100) if total > 0 else 0

    # Agrupar errores por patrón
    error_counts = Counter([e["error"][:500] for e in errores_detalle])
    top_error = error_counts.most_common(1)[0] if error_counts else (None, 0)

    # Campos faltantes más comunes
    campos_faltantes = []
    for e in errores_detalle:
        if "campos_faltantes" in e:
            campos_faltantes.extend(e["campos_faltantes"])

    campos_count = Counter(campos_faltantes)
    campos_json = json.dumps(dict(campos_count.most_common(10)))

    # Sample IDs del error más común
    sample_ids = [str(e["documento_id"]) for e in errores_detalle if e["error"][:500] == top_error[0]][:10]
    sample_ids_str = json.dumps(sample_ids)

    insert_query = """
    INSERT INTO parsing_feedback (
        iteracion, parser_version, tipo_formulario,
        total_documentos, documentos_exitosos, documentos_fallidos,
        tasa_exito, error_pattern, error_count, error_sample_ids,
        campos_faltantes_top, notas, duracion_segundos
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    cursor.execute(insert_query, (
        iteracion, parser_version, tipo,
        total, exitosos, fallidos,
        tasa_exito, top_error[0], top_error[1], sample_ids_str,
        campos_json, notas, duracion
    ))

    conn.commit()
    cursor.close()
    conn.close()

    logger.info("💾 Feedback guardado en BD")


def show_feedback(iteracion: int, tipo: str):
    """Muestra feedback de una iteración."""
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT *
    FROM parsing_feedback
    WHERE iteracion = %s AND tipo_formulario = %s
    """

    cursor.execute(query, (iteracion, tipo))
    feedback = cursor.fetchone()

    cursor.close()
    conn.close()

    if not feedback:
        logger.error(f"No se encontró feedback para Iteración {iteracion}, Tipo {tipo}")
        return

    logger.info("=" * 80)
    logger.info(f"FEEDBACK: ITERACIÓN {iteracion} - {tipo}")
    logger.info("=" * 80)
    logger.info(f"Fecha: {feedback['fecha_iteracion']}")
    logger.info(f"Parser: v{feedback['parser_version']}")
    logger.info("")
    logger.info(f"Total documentos: {feedback['total_documentos']}")
    logger.info(f"✅ Exitosos: {feedback['documentos_exitosos']} ({feedback['tasa_exito']:.1f}%)")
    logger.info(f"❌ Fallidos: {feedback['documentos_fallidos']}")
    logger.info(f"⏱️  Duración: {feedback['duracion_segundos']}s")
    logger.info("")
    logger.info("ERROR MÁS COMÚN:")
    logger.info(f"  {feedback['error_pattern']}")
    logger.info(f"  Casos: {feedback['error_count']} ({feedback['error_count']/feedback['documentos_fallidos']*100:.1f}% de fallos)")
    logger.info(f"  Sample IDs: {feedback['error_sample_ids']}")
    logger.info("")
    logger.info("CAMPOS FALTANTES MÁS COMUNES:")
    campos = json.loads(feedback['campos_faltantes_top'])
    for campo, count in list(campos.items())[:5]:
        logger.info(f"  - {campo}: {count} casos")
    logger.info("")
    if feedback['notas']:
        logger.info(f"NOTAS: {feedback['notas']}")
    logger.info("=" * 80)


def compare_iterations(tipo: str):
    """Compara todas las iteraciones de un tipo."""
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        iteracion,
        fecha_iteracion,
        parser_version,
        total_documentos,
        documentos_exitosos,
        tasa_exito,
        error_pattern,
        error_count
    FROM parsing_feedback
    WHERE tipo_formulario = %s
    ORDER BY iteracion
    """

    cursor.execute(query, (tipo,))
    iterations = cursor.fetchall()

    cursor.close()
    conn.close()

    if not iterations:
        logger.error(f"No se encontraron iteraciones para tipo {tipo}")
        return

    logger.info("=" * 100)
    logger.info(f"COMPARACIÓN DE ITERACIONES: {tipo}")
    logger.info("=" * 100)
    logger.info("")
    logger.info(f"{'Iter':<6} {'Fecha':<12} {'Parser':<10} {'Total':<8} {'Exitosos':<10} {'Tasa':<8} {'Mejora':<8} {'Error Principal':<40}")
    logger.info("-" * 100)

    prev_tasa = None
    for it in iterations:
        mejora = ""
        if prev_tasa is not None:
            diff = it['tasa_exito'] - prev_tasa
            mejora = f"+{diff:.1f}%" if diff > 0 else f"{diff:.1f}%"

        error_short = it['error_pattern'][:40] if it['error_pattern'] else "N/A"

        logger.info(
            f"{it['iteracion']:<6} "
            f"{it['fecha_iteracion'].strftime('%Y-%m-%d'):<12} "
            f"{it['parser_version']:<10} "
            f"{it['total_documentos']:<8} "
            f"{it['documentos_exitosos']:<10} "
            f"{it['tasa_exito']:.1f}%{'':<5} "
            f"{mejora:<8} "
            f"{error_short}"
        )

        prev_tasa = it['tasa_exito']

    logger.info("-" * 100)
    first = iterations[0]
    last = iterations[-1]
    total_mejora = last['tasa_exito'] - first['tasa_exito']
    logger.info(f"MEJORA TOTAL: {total_mejora:.1f}% (Iteración {first['iteracion']} → {last['iteracion']})")
    logger.info("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="Framework Iterativo de Parsing")

    parser.add_argument("--tipo", choices=["SUCTD", "SAC", "FEHACIENTE"], help="Tipo de formulario")
    parser.add_argument("--batch", type=int, help="Número de documentos a procesar")
    parser.add_argument("--iteracion", type=int, help="Número de iteración")
    parser.add_argument("--parser-version", help="Versión del parser")
    parser.add_argument("--reparse", action="store_true", help="Re-parsear documentos ya procesados")
    parser.add_argument("--feedback", action="store_true", help="Mostrar feedback de iteración")
    parser.add_argument("--compare", action="store_true", help="Comparar iteraciones")
    parser.add_argument("--notas", help="Notas sobre esta iteración")

    args = parser.parse_args()

    if args.feedback:
        if not args.iteracion or not args.tipo:
            logger.error("--feedback requiere --iteracion y --tipo")
            sys.exit(1)
        show_feedback(args.iteracion, args.tipo)
        return

    if args.compare:
        if not args.tipo:
            logger.error("--compare requiere --tipo")
            sys.exit(1)
        compare_iterations(args.tipo)
        return

    # Modo parsing
    if not args.tipo or not args.batch or not args.iteracion:
        logger.error("Modo parsing requiere: --tipo, --batch, --iteracion")
        sys.exit(1)

    # Determinar versión del parser
    if args.tipo == "SUCTD":
        from src.parsers.pdf_suctd import SUCTDPDFParser
        parser_obj = SUCTDPDFParser()
        parser_version = args.parser_version or parser_obj.version
    else:
        parser_version = args.parser_version or "1.0.0"

    logger.info("=" * 80)
    logger.info(f"ITERACIÓN {args.iteracion}: {args.tipo}")
    logger.info("=" * 80)
    logger.info("")

    # Obtener documentos
    start_time = datetime.now()
    docs = get_documents_to_parse(args.tipo, args.batch, args.reparse)

    if not docs:
        logger.warning("No hay documentos para procesar")
        return

    # Parsear
    exitosos, fallidos, errores_detalle = parse_batch(args.tipo, docs, parser_version)

    # Calcular duración
    duracion = int((datetime.now() - start_time).total_seconds())

    # Guardar feedback
    logger.info("")
    save_feedback(
        args.iteracion,
        args.tipo,
        parser_version,
        len(docs),
        exitosos,
        fallidos,
        errores_detalle,
        duracion,
        args.notas
    )

    logger.info("")
    logger.info("✅ Iteración completada")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Error fatal: {str(e)}", exc_info=True)
        sys.exit(1)
