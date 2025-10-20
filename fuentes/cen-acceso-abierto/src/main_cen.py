#!/usr/bin/env python3
"""
Script principal para extracción de solicitudes y documentos del CEN.

Este script:
1. Extrae solicitudes por año (tipo=6)
2. Guarda solicitudes en la base de datos
3. Extrae documentos por solicitud (tipo=11)
4. Filtra y guarda solo documentos importantes (SUCTD, SAC, Formulario_proyecto_fehaciente)

Estrategia: Append-only (solo inserta nuevos registros, nunca actualiza ni elimina)
"""

import logging
import sys
from typing import Dict, List

from src.cen_database import get_cen_db_manager
from src.cen_extractor import get_cen_extractor
from src.client import get_api_client
from src.settings import get_settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def flatten_documentos(documentos_by_solicitud: Dict[int, List[dict]]) -> List[dict]:
    """
    Convierte dict de {solicitud_id: [documentos]} a lista plana de documentos.

    Args:
        documentos_by_solicitud: Diccionario con documentos por solicitud

    Returns:
        Lista plana de documentos
    """
    all_documentos = []
    for solicitud_id, documentos in documentos_by_solicitud.items():
        all_documentos.extend(documentos)
    return all_documentos


def main():
    """
    Función principal del script.

    Orquesta el proceso completo de extracción y almacenamiento.
    """
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO EXTRACCIÓN CEN ACCESO ABIERTO")
    logger.info("=" * 70)

    try:
        # Cargar configuración
        logger.info("\n📋 Cargando configuración...")
        settings = get_settings()
        logger.info(f"  Base URL: {settings.cen_api_base_url}")
        logger.info(f"  Años a procesar: {settings.cen_years_list}")
        logger.info(f"  Tipos de documento: {settings.cen_document_types_list}")

        # Inicializar dependencias
        logger.info("\n🔧 Inicializando componentes...")
        api_client = get_api_client(settings)
        db_manager = get_cen_db_manager()
        extractor = get_cen_extractor(settings, api_client, db_manager)

        # Verificar conexión a base de datos
        logger.info("\n🔌 Verificando conexión a base de datos...")
        if not db_manager.test_connection():
            logger.error("❌ No se pudo conectar a la base de datos. Abortando.")
            return 1

        # Crear tablas si no existen
        logger.info("\n🏗️  Creando/verificando tablas...")
        db_manager.create_tables()

        # PASO 1: Extraer solicitudes
        logger.info("\n" + "=" * 70)
        logger.info("PASO 1: EXTRACCIÓN DE SOLICITUDES")
        logger.info("=" * 70)

        solicitudes_results = extractor.extract_all_years()

        if solicitudes_results["total_solicitudes"] == 0:
            logger.warning("⚠️ No se extrajeron solicitudes. Abortando.")
            return 1

        # Aplanar solicitudes de todos los años
        all_solicitudes = []
        for anio, solicitudes in solicitudes_results["solicitudes_by_year"].items():
            all_solicitudes.extend(solicitudes)

        logger.info(f"\n📥 Guardando {len(all_solicitudes)} solicitudes en la base de datos...")
        inserted_solicitudes = db_manager.insert_solicitudes_bulk(all_solicitudes)
        logger.info(f"✅ {inserted_solicitudes} solicitudes nuevas insertadas")

        # PASO 2: Extraer documentos
        logger.info("\n" + "=" * 70)
        logger.info("PASO 2: EXTRACCIÓN DE DOCUMENTOS")
        logger.info("=" * 70)

        # Obtener IDs de todas las solicitudes extraídas
        solicitud_ids = [s["id"] for s in all_solicitudes]
        logger.info(f"📋 Procesando documentos de {len(solicitud_ids)} solicitudes...")

        documentos_results = extractor.extract_documentos_for_solicitudes(solicitud_ids)

        if documentos_results["documentos_importantes"] == 0:
            logger.warning("⚠️ No se encontraron documentos importantes.")
        else:
            # Aplanar documentos
            all_documentos = flatten_documentos(documentos_results["documentos_by_solicitud"])

            logger.info(f"\n📥 Guardando {len(all_documentos)} documentos en la base de datos...")
            inserted_documentos = db_manager.insert_documentos_bulk(all_documentos)
            logger.info(f"✅ {inserted_documentos} documentos nuevos insertados")

        # PASO 3: Mostrar estadísticas finales
        logger.info("\n" + "=" * 70)
        logger.info("📊 ESTADÍSTICAS FINALES")
        logger.info("=" * 70)

        stats = db_manager.get_stats()
        logger.info(f"  Total solicitudes en BD: {stats.get('total_solicitudes', 0)}")
        logger.info(f"  Total documentos en BD: {stats.get('total_documentos', 0)}")
        logger.info(f"    - Formulario SUCTD: {stats.get('docs_suctd', 0)}")
        logger.info(f"    - Formulario SAC: {stats.get('docs_sac', 0)}")
        logger.info(f"    - Formulario_proyecto_fehaciente: {stats.get('docs_fehaciente', 0)}")
        logger.info(f"  Total raw API responses: {stats.get('total_raw_responses', 0)}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
        logger.info("=" * 70)

        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Proceso interrumpido por el usuario")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Error inesperado: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
