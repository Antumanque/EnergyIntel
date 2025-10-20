#!/usr/bin/env python3
"""
Script de setup inicial de base de datos.

Este script:
1. Detecta si la BD está vacía (fresh install)
2. Si está vacía: Ejecuta schemas base completos
3. Si ya existe: Solo ejecuta migraciones pendientes

Uso:
    python db/setup.py              # Setup completo (auto-detecta)
    python db/setup.py --fresh      # Forzar fresh install
    python db/setup.py --migrate    # Solo migraciones
"""

import argparse
import logging
import sys
from pathlib import Path

import mysql.connector
from mysql.connector import Error

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseSetup:
    """Gestor de setup inicial de base de datos."""

    def __init__(self):
        """Inicializa el gestor de setup."""
        settings = get_settings()
        self.db_config = settings.get_db_config()
        self.db_dir = Path(__file__).parent

    def _get_connection(self):
        """Obtiene conexión a la base de datos."""
        return mysql.connector.connect(**self.db_config)

    def _is_fresh_install(self, conn) -> bool:
        """
        Detecta si es una instalación fresca (BD vacía).

        Returns:
            True si la BD está vacía o le faltan tablas críticas
        """
        cursor = conn.cursor()

        # Obtener lista de tablas
        cursor.execute("SHOW TABLES")
        tables = {row[0] for row in cursor.fetchall()}

        logger.debug(f"📊 Tablas existentes: {tables}")

        # Tablas críticas que DEBEN existir para considerar que la BD está configurada
        critical_tables = {
            'raw_api_data',
            'interesados',
            'solicitudes',
            'documentos'
        }

        # Si no hay tablas O faltan tablas críticas, es fresh install
        missing_critical = critical_tables - tables

        if missing_critical:
            logger.debug(f"⚠️  Faltan tablas críticas: {missing_critical}")
            return True

        return False

    def _execute_sql_file(self, conn, sql_file: Path) -> bool:
        """
        Ejecuta un archivo SQL completo.

        Args:
            conn: Conexión a la base de datos
            sql_file: Ruta al archivo SQL

        Returns:
            True si fue exitoso, False en caso contrario
        """
        cursor = conn.cursor()

        try:
            logger.info(f"🔄 Ejecutando: {sql_file.name}")

            # Leer el archivo SQL
            sql_content = sql_file.read_text(encoding='utf-8')

            # Ejecutar cada statement
            statements = []
            current_statement = []

            for line in sql_content.split("\n"):
                stripped = line.strip()

                # Ignorar comentarios y líneas vacías
                if not stripped or stripped.startswith("--"):
                    continue

                current_statement.append(line)

                # Si termina con ; es fin del statement
                if stripped.endswith(";"):
                    statements.append("\n".join(current_statement))
                    current_statement = []

            # Ejecutar cada statement
            for statement in statements:
                if statement.strip():
                    try:
                        cursor.execute(statement)
                        # Consumir resultados si los hay (para evitar "Unread result found")
                        try:
                            cursor.fetchall()
                        except:
                            pass  # No hay resultados, está bien
                    except Error as e:
                        # Ignorar errores de "already exists"
                        if "already exists" not in str(e).lower():
                            logger.warning(f"⚠️  Warning: {str(e)[:100]}")

            conn.commit()
            logger.info(f"✅ {sql_file.name} ejecutado exitosamente")
            return True

        except Error as e:
            conn.rollback()
            logger.error(f"❌ Error ejecutando {sql_file.name}: {e}", exc_info=True)
            return False

    def fresh_install(self, drop_existing: bool = False) -> bool:
        """
        Ejecuta setup completo desde cero.

        Ejecuta todos los schemas base en orden:
        1. init.sql (raw_api_data)
        2. schema_solicitudes.sql (solicitudes, documentos)
        3. schema_formularios_parsed.sql (formularios parseados)

        Args:
            drop_existing: Si True, borra tablas existentes antes de crearlas

        Returns:
            True si fue exitoso
        """
        logger.info("🆕 Ejecutando FRESH INSTALL")

        try:
            conn = self._get_connection()

            # Si se solicita, borrar tablas existentes primero
            if drop_existing:
                logger.warning("⚠️  BORRANDO TABLAS EXISTENTES")
                cursor = conn.cursor()

                # Orden inverso para respetar foreign keys
                tables_to_drop = [
                    'formularios_suctd_parsed',
                    'formularios_fehaciente_parsed',
                    'formularios_sac_parsed',
                    'formularios_parseados',
                    'documentos',
                    'solicitudes',
                    'interesados',
                    'raw_api_data',
                    'schema_migrations'
                ]

                for table in tables_to_drop:
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        logger.info(f"  🗑️  Borrada tabla: {table}")
                    except Error as e:
                        logger.warning(f"  ⚠️  No se pudo borrar {table}: {e}")

                # También borrar vistas
                views_to_drop = [
                    'documentos_listos_para_parsear',
                    'documentos_ultimas_versiones',
                    'successful_fetches',
                    'latest_fetches'
                ]

                for view in views_to_drop:
                    try:
                        cursor.execute(f"DROP VIEW IF EXISTS {view}")
                        logger.info(f"  🗑️  Borrada vista: {view}")
                    except Error as e:
                        logger.warning(f"  ⚠️  No se pudo borrar vista {view}: {e}")

                conn.commit()
                logger.info("✅ Tablas y vistas existentes eliminadas")

            # Archivos de schema en orden
            schema_files = [
                self.db_dir / "init.sql",
                self.db_dir / "schema_solicitudes.sql",
                self.db_dir / "schema_formularios_parsed.sql",
            ]

            # Verificar que todos existan
            for schema_file in schema_files:
                if not schema_file.exists():
                    logger.error(f"❌ Archivo no encontrado: {schema_file}")
                    return False

            # Ejecutar cada schema
            for schema_file in schema_files:
                success = self._execute_sql_file(conn, schema_file)
                if not success:
                    logger.error(f"❌ Error en fresh install: {schema_file.name}")
                    conn.close()
                    return False

            conn.close()

            logger.info("\n" + "="*70)
            logger.info("✅ FRESH INSTALL COMPLETADO")
            logger.info("="*70)
            logger.info("Tablas creadas:")
            logger.info("  - raw_api_data")
            logger.info("  - solicitudes")
            logger.info("  - documentos")
            logger.info("  - formularios_parseados")
            logger.info("  - formularios_sac_parsed")
            logger.info("  - formularios_suctd_parsed")
            logger.info("  - formularios_fehaciente_parsed")
            logger.info("="*70)

            return True

        except Error as e:
            logger.error(f"❌ Error en fresh install: {e}", exc_info=True)
            return False

    def run_migrations(self) -> bool:
        """
        Ejecuta solo las migraciones pendientes.

        Returns:
            True si fue exitoso
        """
        from db.migrate import MigrationManager

        logger.info("🔄 Ejecutando MIGRACIONES")

        manager = MigrationManager()
        exitosas, fallidas = manager.run_migrations()

        return fallidas == 0

    def auto_setup(self) -> bool:
        """
        Setup automático: detecta si es fresh install o migración.

        Returns:
            True si fue exitoso
        """
        logger.info("🔍 Auto-detectando tipo de setup necesario...")

        try:
            conn = self._get_connection()
            is_fresh = self._is_fresh_install(conn)
            conn.close()

            if is_fresh:
                logger.info("📊 Base de datos VACÍA detectada → Fresh install")
                return self.fresh_install()
            else:
                logger.info("📊 Base de datos EXISTENTE detectada → Solo migraciones")
                return self.run_migrations()

        except Error as e:
            logger.error(f"❌ Error en auto-setup: {e}", exc_info=True)
            return False


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Setup inicial de base de datos",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Forzar fresh install (ejecutar todos los schemas)"
    )

    parser.add_argument(
        "--drop",
        action="store_true",
        help="Borrar tablas existentes antes de fresh install (usar con --fresh)"
    )

    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Solo ejecutar migraciones (no fresh install)"
    )

    args = parser.parse_args()

    setup = DatabaseSetup()

    if args.fresh:
        logger.info("🔨 Modo: FRESH INSTALL (forzado)")
        success = setup.fresh_install(drop_existing=args.drop)
    elif args.migrate:
        logger.info("🔨 Modo: SOLO MIGRACIONES (forzado)")
        success = setup.run_migrations()
    else:
        logger.info("🔨 Modo: AUTO-DETECT")
        success = setup.auto_setup()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
