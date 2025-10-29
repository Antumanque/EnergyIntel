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
from src.parsers.pdf_sac import SACPDFParser
from src.parsers.pdf_fehaciente import FehacientePDFParser
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Crea y retorna una conexión a la base de datos.

    Returns:
        mysql.connector.connection: Conexión a la base de datos
    """
    settings = get_settings()
    db_config = settings.get_db_config()
    return mysql.connector.connect(**db_config)


def ensure_feedback_table_exists(conn):
    """Crea la tabla parsing_feedback si no existe."""
    cursor = conn.cursor()

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS parsing_feedback (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,

        -- Iteración
        iteracion INT NOT NULL,
        fecha_parsing TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        parser_version VARCHAR(50),

        -- Documento parseado
        tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE') NOT NULL,
        documento_id BIGINT NOT NULL,
        solicitud_id BIGINT,
        nombre_proyecto VARCHAR(500),

        -- Resultado del parsing
        parse_exitoso BOOLEAN NOT NULL,
        campos_extraidos INT DEFAULT 0,
        campos_vacios INT DEFAULT 0,

        -- Error (si hubo)
        error_message TEXT,
        error_type VARCHAR(200),

        -- Tiempos
        tiempo_segundos DECIMAL(10,3),

        INDEX idx_iteracion (iteracion),
        INDEX idx_tipo (tipo_formulario),
        INDEX idx_exitoso (parse_exitoso),
        INDEX idx_documento (documento_id),
        INDEX idx_fecha (fecha_parsing),

        FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE
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
    conn = get_db_connection()
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
    elif tipo == "SAC":
        parser = SACPDFParser()
    elif tipo == "FEHACIENTE":
        parser = FehacientePDFParser()
    else:
        raise ValueError(f"Tipo no soportado: {tipo}")

    # Conexión BD
    conn = get_db_connection()

    exitosos = 0
    fallidos = 0
    errores_detalle = []  # Guardará TODOS los documentos (exitosos + fallidos)

    for i, doc in enumerate(docs, 1):
        documento_id = doc['documento_id']
        local_path = doc['local_path']
        solicitud_id = doc['solicitud_id']
        proyecto = doc['proyecto']

        if i % 100 == 0:
            logger.info(f"  [{i}/{len(docs)}] Progreso: {exitosos} exitosos, {fallidos} fallidos")

        start_doc_time = datetime.now()

        # Construir ruta completa (agregar downloads/ si es ruta relativa)
        pdf_path = Path(local_path)
        if not pdf_path.is_absolute():
            pdf_path = Path("downloads") / local_path

        # Verificar archivo existe
        if not pdf_path.exists():
            fallidos += 1
            doc_time = (datetime.now() - start_doc_time).total_seconds()
            errores_detalle.append({
                "documento_id": documento_id,
                "solicitud_id": solicitud_id,
                "proyecto": proyecto,
                "exitoso": False,
                "error": "Archivo no encontrado",
                "campos_extraidos": 0,
                "campos_vacios": 0,
                "tiempo": doc_time
            })
            continue

        try:
            # Parsear (pasar solicitud_id para consolidación multi-página)
            data = parser.parse(str(pdf_path), solicitud_id=solicitud_id)

            # Contar campos extraidos vs vacios
            campos_extraidos = sum(1 for v in data.values() if v)
            campos_vacios = len(data) - campos_extraidos

            # Validar campos críticos
            critical_fields = ["razon_social", "rut", "nombre_proyecto"]
            missing = [f for f in critical_fields if not data.get(f)]

            doc_time = (datetime.now() - start_doc_time).total_seconds()

            if missing:
                # Parsing fallido
                fallidos += 1
                error_msg = f"Campos críticos faltantes: {', '.join(missing)}"
                errores_detalle.append({
                    "documento_id": documento_id,
                    "solicitud_id": solicitud_id,
                    "proyecto": proyecto,
                    "exitoso": False,
                    "error": error_msg,
                    "campos_extraidos": campos_extraidos,
                    "campos_vacios": campos_vacios,
                    "tiempo": doc_time
                })

                # Guardar en BD (parsing fallido)
                save_failed_parsing(conn, documento_id, tipo, error_msg, parser_version)
            else:
                # Parsing exitoso
                exitosos += 1

                errores_detalle.append({
                    "documento_id": documento_id,
                    "solicitud_id": solicitud_id,
                    "proyecto": proyecto,
                    "exitoso": True,
                    "campos_extraidos": campos_extraidos,
                    "campos_vacios": campos_vacios,
                    "tiempo": doc_time
                })

                # Guardar en BD
                save_successful_parsing(conn, documento_id, solicitud_id, tipo, data, parser_version)

        except Exception as e:
            fallidos += 1
            doc_time = (datetime.now() - start_doc_time).total_seconds()
            error_msg = str(e)[:500]
            errores_detalle.append({
                "documento_id": documento_id,
                "solicitud_id": solicitud_id,
                "proyecto": proyecto,
                "exitoso": False,
                "error": error_msg,
                "campos_extraidos": 0,
                "campos_vacios": 0,
                "tiempo": doc_time
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
    """
    Guarda feedback de la iteración en BD (un registro por documento).

    errores_detalle debe ser una lista de dicts con:
    {
        'documento_id': int,
        'solicitud_id': int,
        'proyecto': str,
        'exitoso': bool,
        'error': str (opcional),
        'campos_extraidos': int (opcional),
        'campos_vacios': int (opcional),
        'tiempo': float (opcional)
    }
    """
    conn = get_db_connection()
    ensure_feedback_table_exists(conn)

    cursor = conn.cursor()

    insert_query = """
    INSERT INTO parsing_feedback (
        iteracion, parser_version, tipo_formulario,
        documento_id, solicitud_id, nombre_proyecto,
        parse_exitoso, campos_extraidos, campos_vacios,
        error_message, error_type, tiempo_segundos
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Insertar cada documento
    registros_insertados = 0
    for detalle in errores_detalle:
        # Extraer tipo de error (primera línea del mensaje)
        error_msg = detalle.get('error', '')
        error_type = error_msg.split('\n')[0][:200] if error_msg else None

        cursor.execute(insert_query, (
            iteracion,
            parser_version,
            tipo,
            detalle['documento_id'],
            detalle.get('solicitud_id'),
            detalle.get('proyecto', '')[:500],
            detalle.get('exitoso', False),
            detalle.get('campos_extraidos', 0),
            detalle.get('campos_vacios', 0),
            error_msg if error_msg else None,
            error_type,
            detalle.get('tiempo', 0)
        ))
        registros_insertados += 1

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"💾 Feedback guardado en BD: {registros_insertados} documentos")



def show_feedback(iteracion: int, tipo: str):
    """Muestra feedback de una iteración."""
    conn = get_db_connection()
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
    conn = get_db_connection()
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
