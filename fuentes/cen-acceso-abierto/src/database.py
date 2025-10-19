"""
Database module for MariaDB connection and data persistence.

This module provides a clean interface for database operations with proper
connection management and error handling.
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.connection import MySQLConnection

from src.settings import Settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and operations for raw API data storage.

    This class provides a simple interface for connecting to MariaDB and
    storing raw API responses.
    """

    def __init__(self, settings: Settings):
        """
        Inicializa el gestor de base de datos con la configuración.
        """
        self.settings = settings
        self._connection: Optional[MySQLConnection] = None

    def get_connection(self) -> MySQLConnection:
        """
        Obtiene o crea una conexión a la base de datos.
        """
        if self._connection is None or not self._connection.is_connected():
            try:
                config = self.settings.get_db_config()
                self._connection = mysql.connector.connect(**config)
                logger.info(
                    f"Connected to database '{self.settings.db_name}' "
                    f"at {self.settings.db_host}:{self.settings.db_port}"
                )
            except MySQLError as e:
                logger.error(f"Failed to connect to database: {e}")
                raise

        return self._connection

    def close_connection(self) -> None:
        """
        Cierra la conexión a la base de datos si está abierta.
        """
        if self._connection is not None and self._connection.is_connected():
            self._connection.close()
            logger.info("Database connection closed")
            self._connection = None

    @contextmanager
    def connection(self) -> Generator[MySQLConnection, None, None]:
        """
        Context manager para manejo seguro de conexión a la base de datos.

        Ejemplo:
            with db_manager.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            # Nota: No cerramos la conexión aquí ya que es gestionada por la instancia
            # Esto permite reutilizar la conexión entre múltiples operaciones
            pass

    def create_tables(self) -> None:
        """
        Crea las tablas de base de datos necesarias si no existen.

        Este método es idempotente - puede ser llamado múltiples veces de forma segura.
        Crea tanto raw_api_data como tablas normalizadas (ej: interesados).
        """
        # Tabla de datos raw
        create_raw_table_sql = """
        CREATE TABLE IF NOT EXISTS raw_api_data (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            source_url VARCHAR(512) NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status_code INT,
            data JSON,
            error_message TEXT,
            INDEX idx_source_url (source_url),
            INDEX idx_fetched_at (fetched_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        # Tabla normalizada de interesados
        # NOTA: Sin UNIQUE constraint - cargamos datos tal cual vienen del API
        # El análisis de duplicados y normalización final se hará posteriormente
        create_interesados_table_sql = """
        CREATE TABLE IF NOT EXISTS interesados (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            solicitud_id INT NOT NULL,
            razon_social VARCHAR(255),
            nombre_fantasia VARCHAR(255),
            raw_data_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_solicitud_id (solicitud_id),
            INDEX idx_razon_social (razon_social),
            INDEX idx_nombre_fantasia (nombre_fantasia),
            INDEX idx_solicitud_razon (solicitud_id, razon_social),
            FOREIGN KEY (raw_data_id) REFERENCES raw_api_data(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                # Crear tabla de datos raw
                cursor.execute(create_raw_table_sql)
                logger.info("raw_api_data table created/verified")

                # Crear tabla interesados
                cursor.execute(create_interesados_table_sql)
                logger.info("interesados table created/verified")

                conn.commit()
                logger.info("All database tables created/verified successfully")
                cursor.close()
        except MySQLError as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def insert_raw_data(
        self,
        source_url: str,
        status_code: int,
        data: Any,
        error_message: Optional[str] = None,
    ) -> int:
        """
        Inserta datos raw de respuesta API en la base de datos.
        """
        insert_sql = """
        INSERT INTO raw_api_data (source_url, status_code, data, error_message)
        VALUES (%s, %s, %s, %s)
        """

        # Convertir datos a string JSON si aún no lo es
        json_data = None
        if data is not None:
            if isinstance(data, str):
                # Verificar que es JSON válido
                try:
                    json.loads(data)
                    json_data = data
                except json.JSONDecodeError:
                    # Si no es JSON válido, envolverlo
                    json_data = json.dumps({"raw": data})
            else:
                json_data = json.dumps(data)

        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    insert_sql, (source_url, status_code, json_data, error_message)
                )
                conn.commit()
                row_id = cursor.lastrowid
                logger.info(
                    f"Inserted data from {source_url} "
                    f"(status: {status_code}, row_id: {row_id})"
                )
                cursor.close()
                return row_id
        except MySQLError as e:
            logger.error(f"Failed to insert data for {source_url}: {e}")
            raise

    def get_latest_fetch(self, source_url: str) -> Optional[dict]:
        """
        Obtiene el resultado de fetch más reciente para una URL dada.
        """
        select_sql = """
        SELECT id, source_url, fetched_at, status_code, data, error_message
        FROM raw_api_data
        WHERE source_url = %s
        ORDER BY fetched_at DESC
        LIMIT 1
        """

        try:
            with self.connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(select_sql, (source_url,))
                result = cursor.fetchone()
                cursor.close()
                return result
        except MySQLError as e:
            logger.error(f"Failed to query latest fetch for {source_url}: {e}")
            raise

    def insert_interesado(
        self,
        solicitud_id: int,
        razon_social: Optional[str] = None,
        nombre_fantasia: Optional[str] = None,
        raw_data_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Inserta un registro de interesado tal como viene del API.

        Sin verificación de duplicados - la normalización se hará posteriormente.
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                insert_sql = """
                INSERT INTO interesados (solicitud_id, razon_social, nombre_fantasia, raw_data_id)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(
                    insert_sql, (solicitud_id, razon_social, nombre_fantasia, raw_data_id)
                )
                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Inserted interesado ({solicitud_id}, {razon_social}) (row_id: {row_id})")
                cursor.close()
                return row_id

        except MySQLError as e:
            logger.error(f"Failed to insert interesado ({solicitud_id}, {razon_social}): {e}")
            raise

    def insert_interesados_bulk(
        self, records: list[dict], raw_data_id: Optional[int] = None
    ) -> int:
        """
        Inserción masiva de registros de interesados tal como vienen del API.

        ESTRATEGIA: Cargar datos sin filtros de duplicados
        - Inserta todos los registros tal cual vienen del API
        - Preserva duplicados para análisis posterior
        - La normalización final se hará en una fase posterior
        """
        if not records:
            logger.warning("No records to insert")
            return 0

        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                # Insertar todos los registros
                insert_sql = """
                INSERT INTO interesados (solicitud_id, razon_social, nombre_fantasia, raw_data_id)
                VALUES (%s, %s, %s, %s)
                """

                values = []
                for record in records:
                    if record.get("solicitud_id") is not None:
                        values.append(
                            (
                                record.get("solicitud_id"),
                                record.get("razon_social"),
                                record.get("nombre_fantasia"),
                                raw_data_id,
                            )
                        )

                if not values:
                    logger.warning("No valid records to insert")
                    cursor.close()
                    return 0

                logger.info(f"Inserting {len(values)} records from API")

                cursor.executemany(insert_sql, values)
                conn.commit()
                inserted_count = cursor.rowcount

                logger.info(
                    f"Successfully inserted {inserted_count} interesados records"
                )
                cursor.close()
                return inserted_count

        except MySQLError as e:
            logger.error(f"Failed to bulk insert interesados: {e}")
            raise

    def __enter__(self):
        """Entrada del context manager."""
        self.get_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Salida del context manager."""
        self.close_connection()


def get_database_manager(settings: Settings) -> DatabaseManager:
    """
    Función factory para crear una instancia de DatabaseManager.
    """
    return DatabaseManager(settings)
