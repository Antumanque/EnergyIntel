#!/usr/bin/env python3
"""
Script de limpieza COMPLETA de la base de datos.

Este script elimina TODOS los datos procesados para empezar de cero:
1. Formularios parseados (SAC, SUCTD, Fehaciente)
2. Flags de descarga en documentos
3. Archivos físicos descargados

IMPORTANTE: Respeta el orden de foreign keys para evitar errores.

Uso:
    python -m src.clean_all

    # Con confirmación
    python -m src.clean_all --confirm
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from src.repositories.cen import get_cen_db_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def clean_database():
    """Limpia TODAS las tablas - empezar de 0 absoluto."""
    logger.info("🧹 Limpiando base de datos COMPLETA...")
    logger.info("="*70)

    db = get_cen_db_manager()

    with db.connection() as conn:
        cursor = conn.cursor()

        # 1. Limpiar formularios parseados (tienen FKs, van primero)
        logger.info("Paso 1: Eliminando formularios parseados...")

        cursor.execute("DELETE FROM formularios_sac_parsed")
        sac_deleted = cursor.rowcount
        logger.info(f"  ✅ SAC: {sac_deleted} registros")

        cursor.execute("DELETE FROM formularios_suctd_parsed")
        suctd_deleted = cursor.rowcount
        logger.info(f"  ✅ SUCTD: {suctd_deleted} registros")

        cursor.execute("DELETE FROM formularios_fehaciente_parsed")
        feh_deleted = cursor.rowcount
        logger.info(f"  ✅ Fehaciente: {feh_deleted} registros")

        cursor.execute("DELETE FROM formularios_parseados")
        form_deleted = cursor.rowcount
        logger.info(f"  ✅ Formularios_parseados: {form_deleted} registros")

        # 2. Limpiar documentos (tienen FK a solicitudes)
        logger.info("\nPaso 2: Eliminando documentos...")
        cursor.execute("DELETE FROM documentos")
        docs_deleted = cursor.rowcount
        logger.info(f"  ✅ Documentos: {docs_deleted} registros")

        # 3. Limpiar solicitudes
        logger.info("\nPaso 3: Eliminando solicitudes...")
        cursor.execute("DELETE FROM solicitudes")
        sol_deleted = cursor.rowcount
        logger.info(f"  ✅ Solicitudes: {sol_deleted} registros")

        # 4. Limpiar interesados
        logger.info("\nPaso 4: Eliminando interesados...")
        cursor.execute("DELETE FROM interesados")
        int_deleted = cursor.rowcount
        logger.info(f"  ✅ Interesados: {int_deleted} registros")

        # 5. Limpiar raw_api_data
        logger.info("\nPaso 5: Eliminando raw_api_data...")
        cursor.execute("DELETE FROM raw_api_data")
        raw_deleted = cursor.rowcount
        logger.info(f"  ✅ Raw_api_data: {raw_deleted} registros")

        conn.commit()

    logger.info("\n✅ Base de datos limpiada COMPLETAMENTE (TODO eliminado)")


def clean_downloads():
    """Elimina todos los archivos descargados."""
    logger.info("\n🗑️  Limpiando archivos descargados...")
    logger.info("="*70)

    downloads_dir = Path("downloads")

    if not downloads_dir.exists():
        logger.info("  ℹ️  Directorio downloads/ no existe, nada que limpiar")
        return

    # Contar archivos antes de eliminar
    file_count = sum(1 for _ in downloads_dir.rglob("*") if _.is_file())

    if file_count == 0:
        logger.info("  ℹ️  No hay archivos en downloads/, nada que limpiar")
        return

    logger.info(f"  📁 Encontrados {file_count} archivos en downloads/")

    # Eliminar todo el directorio
    shutil.rmtree(downloads_dir)
    logger.info(f"  ✅ Directorio downloads/ eliminado")

    # Recrear directorio vacío
    downloads_dir.mkdir(exist_ok=True)
    logger.info(f"  ✅ Directorio downloads/ recreado (vacío)")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Limpieza completa de base de datos y archivos descargados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  ADVERTENCIA: Este script eliminará TODOS los datos procesados.

Se eliminarán:
  - Todos los formularios parseados (SAC, SUCTD, Fehaciente)
  - Flags de descarga en tabla documentos
  - Archivos físicos en downloads/

NO se eliminarán:
  - raw_api_data
  - interesados
  - solicitudes
  - documentos (metadata)

Uso:
  python -m src.clean_all --confirm
        """
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirmar que deseas eliminar todos los datos"
    )

    args = parser.parse_args()

    if not args.confirm:
        logger.error("❌ ERROR: Debes usar --confirm para ejecutar la limpieza")
        logger.error("   Ejemplo: python -m src.clean_all --confirm")
        return 1

    logger.info("="*70)
    logger.info("🚨 LIMPIEZA COMPLETA DE BASE DE DATOS")
    logger.info("="*70)
    logger.info("")
    logger.info("Se eliminarán:")
    logger.info("  ❌ Formularios parseados (SAC, SUCTD, Fehaciente)")
    logger.info("  ❌ Flags de descarga en documentos")
    logger.info("  ❌ Archivos en downloads/")
    logger.info("")

    try:
        # 1. Limpiar BD
        clean_database()

        # 2. Limpiar archivos
        clean_downloads()

        logger.info("\n" + "="*70)
        logger.info("✅ LIMPIEZA COMPLETA EXITOSA")
        logger.info("="*70)
        logger.info("")
        logger.info("Ahora puedes ejecutar:")
        logger.info("  python -m src.main")
        logger.info("")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Error durante la limpieza: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
