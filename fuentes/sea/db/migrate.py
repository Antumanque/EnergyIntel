#!/usr/bin/env python3
"""
Script de migraciones automáticas para la base de datos SEA.

Ejecuta todas las migraciones pendientes en orden.

Uso:
    python db/migrate.py                    # Ejecutar migraciones pendientes
    python db/migrate.py --status           # Ver estado de migraciones
    python db/migrate.py --dry-run          # Ver qué se ejecutaría
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


class MigrationManager:
    """
    Gestor de migraciones de base de datos.

    Mantiene un registro de qué migraciones se han ejecutado en la tabla
    `schema_migrations` y ejecuta solo las pendientes.
    """

    def __init__(self):
        """Inicializa el gestor de migraciones."""
        settings = get_settings()
        self.db_config = {
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "password": settings.db_password,
            "database": settings.db_name,
        }
        self.migrations_dir = Path(__file__).parent / "migrations"

    def _get_connection(self):
        """Obtiene conexión a la base de datos."""
        return mysql.connector.connect(**self.db_config)

    def _create_migrations_table(self, conn) -> None:
        """
        Crea la tabla schema_migrations si no existe.
        """
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_migration_name (migration_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='Tracking de migraciones aplicadas'
        """)
        conn.commit()
        logger.debug("Tabla schema_migrations verificada")

    def _get_executed_migrations(self, conn) -> set:
        """
        Obtiene lista de migraciones ya ejecutadas.

        Returns:
            Set de nombres de archivos de migraciones ejecutadas
        """
        cursor = conn.cursor()
        cursor.execute("SELECT migration_name FROM schema_migrations")
        executed = {row[0] for row in cursor.fetchall()}
        logger.debug(f"{len(executed)} migraciones ya ejecutadas")
        return executed

    def _get_pending_migrations(self, executed: set) -> list[Path]:
        """
        Obtiene lista de migraciones pendientes en orden.

        Args:
            executed: Set de migraciones ya ejecutadas

        Returns:
            Lista de archivos de migración ordenados por nombre
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Directorio de migraciones no existe: {self.migrations_dir}")
            return []

        # Obtener todos los archivos .sql
        all_migrations = sorted(self.migrations_dir.glob("*.sql"))

        # Filtrar solo los pendientes
        pending = [m for m in all_migrations if m.name not in executed]

        logger.info(f"{len(pending)} migraciones pendientes de {len(all_migrations)} totales")
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
            logger.info(f"Ejecutando migración: {migration_path.name}")

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
                        # Consumir resultados si los hay
                        try:
                            cursor.fetchall()
                        except Exception:
                            pass
                    except Error as e:
                        err_msg = str(e).lower()
                        # Ignorar errores de objetos que ya existen
                        ignorable = (
                            "already exists" in err_msg or
                            "duplicate column" in err_msg or
                            "duplicate entry" in err_msg or
                            "duplicate key" in err_msg
                        )
                        if not ignorable:
                            raise
                        logger.debug(f"Ya existe (ignorado): {str(e)[:100]}")

            # Registrar migración como ejecutada (IGNORE si ya existe)
            cursor.execute("""
                INSERT IGNORE INTO schema_migrations (migration_name, applied_at)
                VALUES (%s, NOW())
            """, (migration_path.name,))

            conn.commit()
            logger.info(f"OK: {migration_path.name}")
            return True

        except Error as e:
            conn.rollback()
            logger.error(f"ERROR en {migration_path.name}: {e}", exc_info=True)
            return False

    def run_migrations(self) -> tuple[int, int]:
        """
        Ejecuta todas las migraciones pendientes.

        Returns:
            Tuple (exitosas, fallidas)
        """
        logger.info("Iniciando migraciones...")

        try:
            conn = self._get_connection()

            # Crear tabla de tracking si no existe
            self._create_migrations_table(conn)

            # Obtener migraciones ejecutadas y pendientes
            executed = self._get_executed_migrations(conn)
            pending = self._get_pending_migrations(executed)

            if not pending:
                logger.info("No hay migraciones pendientes")
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
                    logger.error(f"Deteniendo por error en: {migration_path.name}")
                    break

            conn.close()

            # Resumen
            restantes = len(pending) - exitosas - fallidas
            print("\n" + "=" * 60)
            print("RESUMEN DE MIGRACIONES")
            print("=" * 60)
            print(f"Exitosas:   {exitosas}")
            print(f"Fallidas:   {fallidas}")
            if restantes > 0:
                print(f"Restantes:  {restantes}")
            print("=" * 60)

            return (exitosas, fallidas)

        except Error as e:
            logger.error(f"Error de conexión: {e}", exc_info=True)
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

            print("\n" + "=" * 60)
            print("ESTADO DE MIGRACIONES")
            print("=" * 60)
            print(f"Total disponibles: {len(all_migrations)}")
            print(f"Ejecutadas:        {len(executed)}")
            print(f"Pendientes:        {len(all_migrations) - len(executed)}")
            print("=" * 60)

            if all_migrations:
                print("\nMIGRACIONES:")
                for migration in all_migrations:
                    status = "[OK]     " if migration.name in executed else "[PENDING]"
                    print(f"  {status} {migration.name}")
            else:
                print("\nNo hay migraciones disponibles")

            print()

            # Mostrar últimas migraciones ejecutadas
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT migration_name, applied_at
                FROM schema_migrations
                ORDER BY applied_at DESC
                LIMIT 5
            """)

            recent = cursor.fetchall()
            if recent:
                print("=" * 60)
                print("ÚLTIMAS EJECUTADAS")
                print("=" * 60)
                for row in recent:
                    print(f"  {row['applied_at']} - {row['migration_name']}")
                print()

            conn.close()

        except Error as e:
            logger.error(f"Error al obtener estado: {e}", exc_info=True)


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Gestor de migraciones SEA",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estado de migraciones"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué migraciones se ejecutarían"
    )

    args = parser.parse_args()

    manager = MigrationManager()

    if args.status:
        manager.show_status()
        sys.exit(0)

    if args.dry_run:
        logger.info("Modo dry-run: mostrando migraciones pendientes")
        conn = manager._get_connection()
        manager._create_migrations_table(conn)
        executed = manager._get_executed_migrations(conn)
        pending = manager._get_pending_migrations(executed)
        conn.close()

        if pending:
            print("\nMIGRACIONES PENDIENTES:")
            for migration in pending:
                print(f"  - {migration.name}")
            print()
        else:
            print("\nNo hay migraciones pendientes")

        sys.exit(0)

    # Ejecutar migraciones
    exitosas, fallidas = manager.run_migrations()

    sys.exit(0 if fallidas == 0 else 1)


if __name__ == "__main__":
    main()
