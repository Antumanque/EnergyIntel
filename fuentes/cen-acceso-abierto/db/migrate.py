#!/usr/bin/env python3
"""
Script de migraciones automáticas para la base de datos.

Ejecuta todas las migraciones pendientes en orden.
Se puede ejecutar manualmente o como parte de un deployment script.

Uso:
    python db/migrate.py                    # Ejecutar migraciones pendientes
    python db/migrate.py --status           # Ver estado de migraciones
    python db/migrate.py --rollback <n>     # Rollback últimas N migraciones
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple

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


class MigrationManager:
    """
    Gestor de migraciones de base de datos.

    Mantiene un registro de qué migraciones se han ejecutado en la tabla
    `schema_migrations` y ejecuta solo las pendientes.
    """

    def __init__(self):
        """Inicializa el gestor de migraciones."""
        settings = get_settings()
        self.db_config = settings.get_db_config()
        self.migrations_dir = Path(__file__).parent / "migrations"

    def _get_connection(self):
        """Obtiene conexión a la base de datos."""
        return mysql.connector.connect(**self.db_config)

    def _create_migrations_table(self, conn) -> None:
        """
        Crea la tabla schema_migrations si no existe.

        Esta tabla mantiene registro de qué migraciones se han ejecutado.
        """
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                migration_file VARCHAR(255) NOT NULL UNIQUE,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_migration_file (migration_file)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='Tracking de migraciones de schema ejecutadas'
        """)
        conn.commit()
        logger.debug("✅ Tabla schema_migrations verificada")

    def _get_executed_migrations(self, conn) -> set:
        """
        Obtiene lista de migraciones ya ejecutadas.

        Returns:
            Set de nombres de archivos de migraciones ejecutadas
        """
        cursor = conn.cursor()
        cursor.execute("SELECT migration_file FROM schema_migrations")
        executed = {row[0] for row in cursor.fetchall()}
        logger.debug(f"📊 {len(executed)} migraciones ya ejecutadas")
        return executed

    def _get_pending_migrations(self, executed: set) -> List[Path]:
        """
        Obtiene lista de migraciones pendientes en orden.

        Args:
            executed: Set de migraciones ya ejecutadas

        Returns:
            Lista de archivos de migración ordenados por nombre
        """
        if not self.migrations_dir.exists():
            logger.warning(f"⚠️  Directorio de migraciones no existe: {self.migrations_dir}")
            return []

        # Obtener todos los archivos .sql
        all_migrations = sorted(self.migrations_dir.glob("*.sql"))

        # Filtrar solo los pendientes
        pending = [m for m in all_migrations if m.name not in executed]

        logger.info(f"📋 {len(pending)} migraciones pendientes de {len(all_migrations)} totales")
        return pending

    def _execute_migration(self, conn, migration_path: Path) -> bool:
        """
        Ejecuta una migración individual.

        Args:
            conn: Conexión a la base de datos
            migration_path: Ruta al archivo de migración

        Returns:
            True si la migración fue exitosa, False en caso contrario
        """
        cursor = conn.cursor()

        try:
            logger.info(f"🔄 Ejecutando migración: {migration_path.name}")

            # Leer el archivo SQL
            sql_content = migration_path.read_text(encoding='utf-8')

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
                        # Consumir resultados si los hay (evita "Unread result found")
                        try:
                            cursor.fetchall()
                        except Exception:
                            pass  # No hay resultados para consumir
                    except Error as e:
                        # Ignorar errores de "already exists" para CREATE TABLE/VIEW
                        if "already exists" not in str(e).lower():
                            raise
                        logger.debug(f"⚠️  Objeto ya existe (ignorado): {str(e)[:100]}")

            # Registrar migración como ejecutada
            cursor.execute("""
                INSERT INTO schema_migrations (migration_file, executed_at)
                VALUES (%s, NOW())
            """, (migration_path.name,))

            conn.commit()
            logger.info(f"✅ Migración exitosa: {migration_path.name}")
            return True

        except Error as e:
            conn.rollback()
            logger.error(f"❌ Error en migración {migration_path.name}: {e}", exc_info=True)
            return False

    def run_migrations(self) -> Tuple[int, int]:
        """
        Ejecuta todas las migraciones pendientes.

        Returns:
            Tuple (exitosas, fallidas)
        """
        logger.info("🚀 Iniciando proceso de migraciones")

        try:
            conn = self._get_connection()

            # Crear tabla de tracking si no existe
            self._create_migrations_table(conn)

            # Obtener migraciones ejecutadas y pendientes
            executed = self._get_executed_migrations(conn)
            pending = self._get_pending_migrations(executed)

            if not pending:
                logger.info("✅ No hay migraciones pendientes")
                conn.close()
                return (0, 0)

            # Ejecutar migraciones pendientes
            exitosas = 0
            fallidas = 0

            for migration_path in pending:
                success = self._execute_migration(conn, migration_path)
                if success:
                    exitosas += 1
                else:
                    fallidas += 1
                    # Si falla una migración, detener el proceso
                    logger.error(f"❌ Deteniendo migraciones por error en: {migration_path.name}")
                    break

            conn.close()

            # Resumen
            restantes = len(pending) - exitosas - fallidas
            logger.info("\n" + "="*70)
            logger.info("📊 RESUMEN DE MIGRACIONES")
            logger.info("="*70)
            logger.info(f"✅ Exitosas: {exitosas}")
            logger.info(f"❌ Fallidas: {fallidas}")
            if restantes > 0:
                logger.info(f"⏳ Restantes: {restantes}")
            logger.info("="*70)

            return (exitosas, fallidas)

        except Error as e:
            logger.error(f"❌ Error de conexión a la base de datos: {e}", exc_info=True)
            return (0, 1)

    def show_status(self) -> None:
        """
        Muestra el estado actual de las migraciones.
        """
        try:
            conn = self._get_connection()
            self._create_migrations_table(conn)

            # Obtener migraciones ejecutadas
            executed = self._get_executed_migrations(conn)

            # Obtener todas las migraciones disponibles
            all_migrations = sorted(self.migrations_dir.glob("*.sql")) if self.migrations_dir.exists() else []

            print("\n" + "="*70)
            print("📊 ESTADO DE MIGRACIONES")
            print("="*70)
            print(f"Total migraciones disponibles: {len(all_migrations)}")
            print(f"Migraciones ejecutadas: {len(executed)}")
            print(f"Migraciones pendientes: {len(all_migrations) - len(executed)}")
            print("="*70)

            if all_migrations:
                print("\n📋 MIGRACIONES:")
                for migration in all_migrations:
                    status = "✅ EJECUTADA" if migration.name in executed else "⏳ PENDIENTE"
                    print(f"  {status:15s} {migration.name}")
            else:
                print("\n⚠️  No hay migraciones disponibles")

            print()

            # Mostrar últimas migraciones ejecutadas
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT migration_file, executed_at
                FROM schema_migrations
                ORDER BY executed_at DESC
                LIMIT 5
            """)

            recent = cursor.fetchall()
            if recent:
                print("="*70)
                print("🕐 ÚLTIMAS MIGRACIONES EJECUTADAS")
                print("="*70)
                for row in recent:
                    print(f"  {row['executed_at']} - {row['migration_file']}")
                print()

            conn.close()

        except Error as e:
            logger.error(f"❌ Error al obtener estado: {e}", exc_info=True)


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Gestor de migraciones de base de datos",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estado de migraciones sin ejecutar"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué migraciones se ejecutarían sin ejecutarlas"
    )

    args = parser.parse_args()

    manager = MigrationManager()

    if args.status:
        manager.show_status()
        sys.exit(0)

    if args.dry_run:
        logger.info("🔍 Modo dry-run: mostrando migraciones pendientes")
        conn = manager._get_connection()
        manager._create_migrations_table(conn)
        executed = manager._get_executed_migrations(conn)
        pending = manager._get_pending_migrations(executed)
        conn.close()

        if pending:
            print("\n📋 MIGRACIONES PENDIENTES QUE SE EJECUTARÍAN:")
            for migration in pending:
                print(f"  - {migration.name}")
            print()
        else:
            print("\n✅ No hay migraciones pendientes")

        sys.exit(0)

    # Ejecutar migraciones
    exitosas, fallidas = manager.run_migrations()

    # Exit code basado en resultado
    sys.exit(0 if fallidas == 0 else 1)


if __name__ == "__main__":
    main()
