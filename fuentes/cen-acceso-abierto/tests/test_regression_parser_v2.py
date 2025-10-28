#!/usr/bin/env python3
"""
Test de Regresión: Parser SUCTD v2.0.0

Valida que el nuevo parser NO rompe documentos que antes funcionaban.

Estrategia:
1. Seleccionar 20 documentos SUCTD que parsearon exitosamente con v1.0.0
2. Re-parsear con v2.0.0
3. Comparar campos extraídos
4. Verificar que NINGUNO empeora

Criterio de éxito:
- 20/20 documentos siguen parseando
- 0 documentos con menos campos que antes
- Algunos documentos pueden mejorar (más campos)
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import mysql.connector
from src.parsers.pdf_suctd import SUCTDPDFParser
from src.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_successful_documents(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Obtiene documentos SUCTD que parsearon exitosamente con v1.0.0.

    Returns:
        Lista de diccionarios con documento_id, ruta_archivo, proyecto, campos_extraidos
    """
    settings = get_settings()
    db_config = settings.get_db_config()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        d.id AS documento_id,
        d.local_path,
        s.proyecto,
        fp.id AS formulario_parseado_id,
        fp.parsing_exitoso,
        fsp.razon_social,
        fsp.rut,
        fsp.nombre_proyecto,
        fsp.tipo_proyecto,
        fsp.tipo_tecnologia,
        fsp.potencia_neta_inyeccion_mw,
        fsp.proyecto_comuna,
        fsp.proyecto_region
    FROM documentos d
    INNER JOIN solicitudes s ON d.solicitud_id = s.id
    INNER JOIN formularios_parseados fp ON d.id = fp.documento_id
    INNER JOIN formularios_suctd_parsed fsp ON fp.id = fsp.formulario_parseado_id
    WHERE d.tipo_documento = 'Formulario SUCTD'
      AND fp.parsing_exitoso = 1
      AND d.local_path LIKE '%.pdf'
      AND d.downloaded = 1
    ORDER BY fp.parsed_at DESC
    LIMIT %s;
    """

    cursor.execute(query, (limit,))
    docs = cursor.fetchall()

    cursor.close()
    conn.close()

    return docs


def count_non_null_fields(data: Dict[str, Any]) -> int:
    """Cuenta cuántos campos tienen valor no-null."""
    return len([v for v in data.values() if v is not None and v != ""])


def compare_results(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compara resultados de v1.0.0 vs v2.0.0.

    Returns:
        Diccionario con estadísticas de comparación
    """
    # Campos críticos a comparar
    critical_fields = [
        "razon_social", "rut", "nombre_proyecto",
        "tipo_proyecto", "tipo_tecnologia",
        "potencia_neta_inyeccion_mw",
        "proyecto_comuna", "proyecto_region"
    ]

    old_count = count_non_null_fields(old_data)
    new_count = count_non_null_fields(new_data)

    critical_matches = 0
    critical_diffs = []

    for field in critical_fields:
        old_val = old_data.get(field)
        new_val = new_data.get(field)

        # Normalizar para comparación
        old_str = str(old_val).strip() if old_val else ""
        new_str = str(new_val).strip() if new_val else ""

        if old_str == new_str:
            critical_matches += 1
        else:
            critical_diffs.append({
                "field": field,
                "old": old_val,
                "new": new_val
            })

    return {
        "old_field_count": old_count,
        "new_field_count": new_count,
        "field_diff": new_count - old_count,
        "critical_matches": critical_matches,
        "critical_total": len(critical_fields),
        "critical_diffs": critical_diffs,
        "status": "✅ OK" if new_count >= old_count and len(critical_diffs) == 0 else "⚠️ REVISAR"
    }


def run_regression_test(limit: int = 20) -> Tuple[int, int, int]:
    """
    Ejecuta test de regresión completo.

    Returns:
        Tupla (exitosos, empeorados, mejorados)
    """
    logger.info("=" * 80)
    logger.info("TEST DE REGRESIÓN: Parser SUCTD v2.0.0")
    logger.info("=" * 80)
    logger.info("")

    # 1. Obtener documentos exitosos de v1.0.0
    logger.info(f"📋 Obteniendo {limit} documentos que parsearon exitosamente con v1.0.0...")
    docs = get_successful_documents(limit)
    logger.info(f"✅ {len(docs)} documentos encontrados")
    logger.info("")

    if not docs:
        logger.error("❌ No se encontraron documentos para probar")
        return 0, 0, 0

    # 2. Re-parsear con v2.0.0
    parser = SUCTDPDFParser()
    logger.info(f"🔧 Parser version: {parser.version}")
    logger.info("")

    exitosos = 0
    empeorados = 0
    mejorados = 0

    results = []

    for i, doc in enumerate(docs, 1):
        documento_id = doc['documento_id']
        ruta = doc['local_path']
        proyecto = doc['proyecto']

        logger.info(f"[{i}/{len(docs)}] Procesando: {proyecto} (ID: {documento_id})")
        logger.info(f"         Ruta: {ruta}")

        # Verificar que el archivo existe
        pdf_path = Path(ruta)
        if not pdf_path.exists():
            logger.warning(f"         ⚠️  Archivo no encontrado: {ruta}")
            logger.info("")
            continue

        # Datos antiguos (v1.0.0)
        old_data = {
            "razon_social": doc.get("razon_social"),
            "rut": doc.get("rut"),
            "nombre_proyecto": doc.get("nombre_proyecto"),
            "tipo_proyecto": doc.get("tipo_proyecto"),
            "tipo_tecnologia": doc.get("tipo_tecnologia"),
            "potencia_neta_inyeccion_mw": doc.get("potencia_neta_inyeccion_mw"),
            "proyecto_comuna": doc.get("proyecto_comuna"),
            "proyecto_region": doc.get("proyecto_region")
        }

        try:
            # Re-parsear con v2.0.0
            new_data = parser.parse(str(pdf_path))

            # Comparar
            comparison = compare_results(old_data, new_data)

            logger.info(f"         {comparison['status']}")
            logger.info(f"         Campos: {comparison['old_field_count']} → {comparison['new_field_count']} ({comparison['field_diff']:+d})")
            logger.info(f"         Críticos: {comparison['critical_matches']}/{comparison['critical_total']} coinciden")

            if comparison['critical_diffs']:
                logger.warning(f"         ⚠️  Diferencias en campos críticos:")
                for diff in comparison['critical_diffs']:
                    logger.warning(f"           - {diff['field']}: '{diff['old']}' → '{diff['new']}'")

            # Clasificar resultado
            if comparison['field_diff'] < 0:
                empeorados += 1
                logger.error(f"         ❌ EMPEORÓ: {-comparison['field_diff']} campos perdidos")
            elif comparison['field_diff'] > 0:
                mejorados += 1
                logger.info(f"         🎉 MEJORÓ: +{comparison['field_diff']} campos nuevos")
            else:
                exitosos += 1
                logger.info(f"         ✅ IGUAL")

            results.append({
                "documento_id": documento_id,
                "proyecto": proyecto,
                "comparison": comparison
            })

        except Exception as e:
            logger.error(f"         ❌ ERROR AL PARSEAR: {str(e)}")
            empeorados += 1

        logger.info("")

    # 3. Resumen final
    logger.info("=" * 80)
    logger.info("RESUMEN DEL TEST DE REGRESIÓN")
    logger.info("=" * 80)
    logger.info(f"Total documentos probados: {len(docs)}")
    logger.info(f"✅ Exitosos (igual): {exitosos}")
    logger.info(f"🎉 Mejorados (+campos): {mejorados}")
    logger.info(f"❌ Empeorados (-campos): {empeorados}")
    logger.info("")

    # Resultado final
    if empeorados == 0:
        logger.info("🎉 ✅ TEST DE REGRESIÓN EXITOSO")
        logger.info("El parser v2.0.0 NO rompe documentos que antes funcionaban")
        logger.info("")
        if mejorados > 0:
            logger.info(f"Bonus: {mejorados} documentos MEJORARON con v2.0.0")
    else:
        logger.error("❌ TEST DE REGRESIÓN FALLIDO")
        logger.error(f"{empeorados} documentos EMPEORARON con v2.0.0")
        logger.error("NO DESPLEGAR A PRODUCCIÓN hasta resolver estos casos")

    logger.info("")
    logger.info("=" * 80)

    return exitosos, empeorados, mejorados


if __name__ == "__main__":
    try:
        exitosos, empeorados, mejorados = run_regression_test(limit=20)

        # Exit code: 0 si todo OK, 1 si hubo empeoramientos
        sys.exit(0 if empeorados == 0 else 1)

    except Exception as e:
        logger.error(f"❌ Error fatal: {str(e)}", exc_info=True)
        sys.exit(1)
