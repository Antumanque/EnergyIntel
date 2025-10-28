#!/usr/bin/env python3
"""
Re-parsing de Documentos SUCTD Fallidos con Parser v2.0.0

Re-parsea documentos SUCTD que fallaron con v1.0.0 usando el nuevo parser v2.0.0.

Estrategia:
1. Identificar documentos con parsing_exitoso = 0
2. Re-parsear con v2.0.0
3. Actualizar formularios_parseados y formularios_suctd_parsed
4. Reportar mejoras

Seguridad:
- NO borra datos antiguos
- SOLO actualiza si el nuevo parsing es exitoso
- Mantiene trazabilidad con updated_at
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import mysql.connector
from src.parsers.pdf_suctd import SUCTDPDFParser
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_failed_documents(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Obtiene documentos SUCTD que fallaron al parsear.

    Args:
        limit: Límite de documentos (None = todos)

    Returns:
        Lista de documentos fallidos
    """
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        fp.id AS formulario_parseado_id,
        fp.documento_id,
        fp.parsing_error,
        d.local_path,
        d.solicitud_id,
        s.proyecto
    FROM formularios_parseados fp
    INNER JOIN documentos d ON fp.documento_id = d.id
    INNER JOIN solicitudes s ON d.solicitud_id = s.id
    WHERE fp.tipo_formulario = 'SUCTD'
      AND fp.parsing_exitoso = 0
      AND d.local_path LIKE '%.pdf'
      AND d.downloaded = 1
    ORDER BY fp.parsed_at DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    docs = cursor.fetchall()

    cursor.close()
    conn.close()

    return docs


def validate_parsed_data(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Valida que los datos parseados cumplan requisitos mínimos.

    Returns:
        (es_valido, mensaje_error)
    """
    # Campos críticos obligatorios
    critical_fields = ["razon_social", "rut", "nombre_proyecto"]

    missing = []
    for field in critical_fields:
        value = data.get(field)
        if not value or (isinstance(value, str) and len(value.strip()) == 0):
            missing.append(field)

    if missing:
        return False, f"Campos críticos faltantes: {', '.join(missing)}"

    return True, None


def update_parsed_data(
    conn,
    formulario_parseado_id: int,
    documento_id: int,
    solicitud_id: int,
    data: Dict[str, Any]
) -> bool:
    """
    Actualiza formularios_parseados y formularios_suctd_parsed con nuevos datos.

    Returns:
        True si se actualizó exitosamente
    """
    cursor = conn.cursor()

    try:
        # 1. Actualizar formularios_parseados
        update_fp_query = """
        UPDATE formularios_parseados
        SET parsing_exitoso = 1,
            parsing_error = NULL,
            updated_at = NOW()
        WHERE id = %s
        """
        cursor.execute(update_fp_query, (formulario_parseado_id,))

        # 2. Verificar si ya existe en formularios_suctd_parsed
        check_query = """
        SELECT id FROM formularios_suctd_parsed
        WHERE formulario_parseado_id = %s
        """
        cursor.execute(check_query, (formulario_parseado_id,))
        existing = cursor.fetchone()

        if existing:
            # UPDATE
            update_suctd_query = """
            UPDATE formularios_suctd_parsed
            SET
                solicitud_id = %s,
                razon_social = %s,
                rut = %s,
                domicilio_legal = %s,
                representante_legal_nombre = %s,
                representante_legal_email = %s,
                representante_legal_telefono = %s,
                coordinador_proyecto_1_nombre = %s,
                coordinador_proyecto_1_email = %s,
                coordinador_proyecto_1_telefono = %s,
                coordinador_proyecto_2_nombre = %s,
                coordinador_proyecto_2_email = %s,
                coordinador_proyecto_2_telefono = %s,
                nombre_proyecto = %s,
                tipo_proyecto = %s,
                tipo_tecnologia = %s,
                potencia_neta_inyeccion_mw = %s,
                potencia_neta_retiro_mw = %s,
                factor_potencia_nominal = %s,
                modo_operacion_inversores = %s,
                proyecto_comuna = %s,
                proyecto_region = %s,
                nombre_se_o_linea = %s,
                tipo_conexion = %s,
                nivel_tension_kv = %s,
                fecha_estimada_construccion = %s,
                fecha_estimada_operacion = %s,
                updated_at = NOW()
            WHERE formulario_parseado_id = %s
            """
            params = (
                solicitud_id,
                data.get("razon_social"),
                data.get("rut"),
                data.get("domicilio_legal"),
                data.get("representante_legal_nombre"),
                data.get("representante_legal_email"),
                data.get("representante_legal_telefono"),
                data.get("coordinador_proyecto_1_nombre"),
                data.get("coordinador_proyecto_1_email"),
                data.get("coordinador_proyecto_1_telefono"),
                data.get("coordinador_proyecto_2_nombre"),
                data.get("coordinador_proyecto_2_email"),
                data.get("coordinador_proyecto_2_telefono"),
                data.get("nombre_proyecto"),
                data.get("tipo_proyecto"),
                data.get("tipo_tecnologia"),
                data.get("potencia_neta_inyeccion_mw"),
                data.get("potencia_neta_retiro_mw"),
                data.get("factor_potencia_nominal"),
                data.get("modo_operacion_inversores"),
                data.get("proyecto_comuna"),
                data.get("proyecto_region"),
                data.get("nombre_se_o_linea"),
                data.get("tipo_conexion"),
                data.get("nivel_tension_kv"),
                data.get("fecha_estimada_construccion"),
                data.get("fecha_estimada_operacion"),
                formulario_parseado_id
            )
        else:
            # INSERT
            insert_suctd_query = """
            INSERT INTO formularios_suctd_parsed (
                formulario_parseado_id, solicitud_id,
                razon_social, rut, domicilio_legal,
                representante_legal_nombre, representante_legal_email, representante_legal_telefono,
                coordinador_proyecto_1_nombre, coordinador_proyecto_1_email, coordinador_proyecto_1_telefono,
                coordinador_proyecto_2_nombre, coordinador_proyecto_2_email, coordinador_proyecto_2_telefono,
                nombre_proyecto, tipo_proyecto, tipo_tecnologia,
                potencia_neta_inyeccion_mw, potencia_neta_retiro_mw, factor_potencia_nominal,
                modo_operacion_inversores,
                proyecto_comuna, proyecto_region,
                nombre_se_o_linea, tipo_conexion, nivel_tension_kv,
                fecha_estimada_construccion, fecha_estimada_operacion
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            params = (
                formulario_parseado_id, solicitud_id,
                data.get("razon_social"),
                data.get("rut"),
                data.get("domicilio_legal"),
                data.get("representante_legal_nombre"),
                data.get("representante_legal_email"),
                data.get("representante_legal_telefono"),
                data.get("coordinador_proyecto_1_nombre"),
                data.get("coordinador_proyecto_1_email"),
                data.get("coordinador_proyecto_1_telefono"),
                data.get("coordinador_proyecto_2_nombre"),
                data.get("coordinador_proyecto_2_email"),
                data.get("coordinador_proyecto_2_telefono"),
                data.get("nombre_proyecto"),
                data.get("tipo_proyecto"),
                data.get("tipo_tecnologia"),
                data.get("potencia_neta_inyeccion_mw"),
                data.get("potencia_neta_retiro_mw"),
                data.get("factor_potencia_nominal"),
                data.get("modo_operacion_inversores"),
                data.get("proyecto_comuna"),
                data.get("proyecto_region"),
                data.get("nombre_se_o_linea"),
                data.get("tipo_conexion"),
                data.get("nivel_tension_kv"),
                data.get("fecha_estimada_construccion"),
                data.get("fecha_estimada_operacion")
            )

        cursor.execute(insert_suctd_query if not existing else update_suctd_query, params)
        conn.commit()

        cursor.close()
        return True

    except Exception as e:
        logger.error(f"Error al actualizar BD: {str(e)}")
        conn.rollback()
        cursor.close()
        return False


def reparse_failed_documents(dry_run: bool = False, limit: Optional[int] = None):
    """
    Re-parsea documentos fallidos con parser v2.0.0.

    Args:
        dry_run: Si True, no actualiza la BD (solo simula)
        limit: Límite de documentos a procesar
    """
    logger.info("=" * 80)
    logger.info("RE-PARSING DOCUMENTOS SUCTD FALLIDOS - Parser v2.0.0")
    logger.info("=" * 80)
    logger.info("")

    if dry_run:
        logger.warning("⚠️  MODO DRY-RUN: NO se actualizará la base de datos")
        logger.info("")

    # 1. Obtener documentos fallidos
    logger.info(f"📋 Obteniendo documentos fallidos{f' (límite: {limit})' if limit else ''}...")
    docs = get_failed_documents(limit)
    logger.info(f"✅ {len(docs)} documentos fallidos encontrados")
    logger.info("")

    if not docs:
        logger.info("No hay documentos fallidos para re-parsear")
        return

    # 2. Inicializar parser v2.0.0
    parser = SUCTDPDFParser()
    logger.info(f"🔧 Parser version: {parser.version}")
    logger.info("")

    # Estadísticas
    exitosos = 0
    aun_fallidos = 0
    no_encontrados = 0

    # Conexión BD
    settings = get_settings()
    db_config = settings.get_db_config()
    conn = mysql.connector.connect(**db_config)

    # 3. Procesar cada documento
    for i, doc in enumerate(docs, 1):
        formulario_parseado_id = doc['formulario_parseado_id']
        documento_id = doc['documento_id']
        solicitud_id = doc['solicitud_id']
        ruta = doc['local_path']
        proyecto = doc['proyecto']
        error_anterior = doc['parsing_error']

        logger.info(f"[{i}/{len(docs)}] {proyecto}")
        logger.info(f"         Doc ID: {documento_id}, Form ID: {formulario_parseado_id}")
        logger.info(f"         Ruta: {ruta}")
        logger.info(f"         Error anterior: {error_anterior}")

        # Verificar archivo existe
        pdf_path = Path(ruta)
        if not pdf_path.exists():
            logger.warning(f"         ⚠️  Archivo no encontrado")
            no_encontrados += 1
            logger.info("")
            continue

        try:
            # Re-parsear
            data = parser.parse(str(pdf_path))

            # Validar
            es_valido, mensaje_error = validate_parsed_data(data)

            if es_valido:
                logger.info(f"         ✅ PARSING EXITOSO")
                logger.info(f"            - Razón Social: {data.get('razon_social')}")
                logger.info(f"            - RUT: {data.get('rut')}")
                logger.info(f"            - Proyecto: {data.get('nombre_proyecto')}")

                if not dry_run:
                    # Actualizar BD
                    if update_parsed_data(conn, formulario_parseado_id, documento_id, solicitud_id, data):
                        logger.info(f"         💾 Base de datos actualizada")
                        exitosos += 1
                    else:
                        logger.error(f"         ❌ Error al actualizar BD")
                        aun_fallidos += 1
                else:
                    logger.info(f"         🔍 DRY-RUN: NO se actualizó la BD")
                    exitosos += 1
            else:
                logger.warning(f"         ⚠️  AÚN FALLA: {mensaje_error}")
                aun_fallidos += 1

        except Exception as e:
            logger.error(f"         ❌ ERROR: {str(e)}")
            aun_fallidos += 1

        logger.info("")

    # 4. Cerrar conexión
    conn.close()

    # 5. Resumen
    logger.info("=" * 80)
    logger.info("RESUMEN DE RE-PARSING")
    logger.info("=" * 80)
    logger.info(f"Total procesados: {len(docs)}")
    logger.info(f"✅ Exitosos (recuperados): {exitosos}")
    logger.info(f"❌ Aún fallidos: {aun_fallidos}")
    logger.info(f"⚠️  Archivos no encontrados: {no_encontrados}")
    logger.info("")

    if exitosos > 0:
        tasa_recuperacion = (exitosos / len(docs)) * 100
        logger.info(f"🎉 Tasa de recuperación: {tasa_recuperacion:.1f}%")
        logger.info(f"   {exitosos} documentos que antes fallaban ahora funcionan!")
    else:
        logger.warning("No se recuperaron documentos")

    logger.info("")
    logger.info("=" * 80)


if __name__ == "__main__":
    import argparse

    parser_cli = argparse.ArgumentParser(description="Re-parsear documentos SUCTD fallidos")
    parser_cli.add_argument("--dry-run", action="store_true", help="Modo simulación (no actualiza BD)")
    parser_cli.add_argument("--limit", type=int, help="Límite de documentos a procesar")

    args = parser_cli.parse_args()

    try:
        reparse_failed_documents(dry_run=args.dry_run, limit=args.limit)
    except Exception as e:
        logger.error(f"❌ Error fatal: {str(e)}", exc_info=True)
        sys.exit(1)
