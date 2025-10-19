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

# Configure logging
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
        Initialize the database manager with settings.

        Args:
            settings: Application settings with database configuration
        """
        self.settings = settings
        self._connection: Optional[MySQLConnection] = None

    def get_connection(self) -> MySQLConnection:
        """
        Get or create a database connection.

        Returns:
            Active MySQL connection

        Raises:
            MySQLError: If connection fails
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
        Close the database connection if it's open.
        """
        if self._connection is not None and self._connection.is_connected():
            self._connection.close()
            logger.info("Database connection closed")
            self._connection = None

    @contextmanager
    def connection(self) -> Generator[MySQLConnection, None, None]:
        """
        Context manager for safe database connection handling.

        Yields:
            Active MySQL connection

        Example:
            with db_manager.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            # Note: We don't close the connection here as it's managed by the instance
            # This allows connection reuse across multiple operations
            pass

    def create_tables(self) -> None:
        """
        Create necessary database tables if they don't exist.

        This method is idempotent - it can be called multiple times safely.
        """
        create_table_sql = """
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

        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_table_sql)
                conn.commit()
                logger.info("Database tables created/verified successfully")
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
        Insert raw API response data into the database.

        Args:
            source_url: The URL that was fetched
            status_code: HTTP status code from the response
            data: The response data (will be converted to JSON)
            error_message: Optional error message if the request failed

        Returns:
            The ID of the inserted row

        Raises:
            MySQLError: If insert operation fails
        """
        insert_sql = """
        INSERT INTO raw_api_data (source_url, status_code, data, error_message)
        VALUES (%s, %s, %s, %s)
        """

        # Convert data to JSON string if it's not already
        json_data = None
        if data is not None:
            if isinstance(data, str):
                # Verify it's valid JSON
                try:
                    json.loads(data)
                    json_data = data
                except json.JSONDecodeError:
                    # If it's not valid JSON, wrap it
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
        Get the most recent fetch result for a given URL.

        Args:
            source_url: The URL to query

        Returns:
            Dictionary with fetch data or None if not found
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

    def __enter__(self):
        """Context manager entry."""
        self.get_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_connection()


def get_database_manager(settings: Settings) -> DatabaseManager:
    """
    Factory function to create a DatabaseManager instance.

    Args:
        settings: Application settings

    Returns:
        Configured DatabaseManager instance
    """
    return DatabaseManager(settings)
