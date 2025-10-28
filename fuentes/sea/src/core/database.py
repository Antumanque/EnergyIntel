"""
Gestor de base de datos para la aplicación.

Este módulo provee una interfaz centralizada para operaciones de base de datos
con manejo apropiado de conexiones y transacciones.
"""

import logging
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.connection import MySQLConnection

from src.settings import Settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestor de base de datos para operaciones de MariaDB/MySQL.

    Esta clase provee métodos para conectarse a la base de datos,
    ejecutar queries, y manejar transacciones.
    """

    def __init__(self, settings: Settings):
        """
        Inicializar el gestor de base de datos con settings.

        Args:
            settings: Settings de aplicación con configuración de BD
        """
        self.settings = settings
        self.db_config = settings.get_db_config()
        self._connection: MySQLConnection | None = None

    def get_connection(self) -> MySQLConnection:
        """
        Obtener una conexión a la base de datos.

        Si no existe una conexión activa, crea una nueva.

        Returns:
            Conexión a MySQL activa

        Raises:
            MySQLError: Si falla la conexión
        """
        if self._connection is None or not self._connection.is_connected():
            try:
                logger.info(
                    f"Connecting to database {self.db_config['database']} "
                    f"at {self.db_config['host']}:{self.db_config['port']}"
                )
                self._connection = mysql.connector.connect(**self.db_config)
                logger.info("Database connection established successfully")
            except MySQLError as e:
                logger.error(f"Failed to connect to database: {e}")
                raise

        return self._connection

    def close_connection(self) -> None:
        """
        Cerrar la conexión a la base de datos.

        Es seguro llamar este método múltiples veces.
        """
        if self._connection and self._connection.is_connected():
            self._connection.close()
            logger.info("Database connection closed")
            self._connection = None

    @contextmanager
    def get_cursor(self, dictionary: bool = False):
        """
        Context manager para obtener un cursor de base de datos.

        Args:
            dictionary: Si True, retorna filas como dicts. Si False, como tuplas.

        Yields:
            Cursor de MySQL

        Example:
            with db.get_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM table")
                rows = cursor.fetchall()
        """
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield cursor
        finally:
            cursor.close()

    def execute_query(
        self,
        query: str,
        params: tuple | dict | None = None,
        commit: bool = False,
    ) -> None:
        """
        Ejecutar un query SQL (INSERT, UPDATE, DELETE).

        Args:
            query: Query SQL a ejecutar
            params: Parámetros para el query (opcional)
            commit: Si True, hace commit después de ejecutar

        Raises:
            MySQLError: Si falla la ejecución del query
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                if commit:
                    self.get_connection().commit()
                    logger.debug(f"Query executed and committed: {query[:100]}")
                else:
                    logger.debug(f"Query executed: {query[:100]}")
        except MySQLError as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query[:200]}")
            raise

    def execute_many(
        self,
        query: str,
        params_list: list[tuple | dict],
        commit: bool = True,
    ) -> None:
        """
        Ejecutar un query múltiples veces con diferentes parámetros.

        Args:
            query: Query SQL a ejecutar
            params_list: Lista de parámetros para cada ejecución
            commit: Si True, hace commit después de todas las ejecuciones

        Raises:
            MySQLError: Si falla la ejecución
        """
        try:
            with self.get_cursor() as cursor:
                cursor.executemany(query, params_list)
                if commit:
                    self.get_connection().commit()
                    logger.debug(
                        f"Query executed {len(params_list)} times and committed"
                    )
        except MySQLError as e:
            logger.error(f"Error executing many: {e}")
            logger.error(f"Query: {query[:200]}")
            raise

    def fetch_one(
        self,
        query: str,
        params: tuple | dict | None = None,
        dictionary: bool = True,
    ) -> dict | tuple | None:
        """
        Ejecutar un query y fetch un solo resultado.

        Args:
            query: Query SQL a ejecutar
            params: Parámetros para el query (opcional)
            dictionary: Si True, retorna dict. Si False, retorna tupla.

        Returns:
            Un dict o tupla con el resultado, o None si no hay resultados
        """
        try:
            with self.get_cursor(dictionary=dictionary) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return result
        except MySQLError as e:
            logger.error(f"Error fetching one: {e}")
            logger.error(f"Query: {query[:200]}")
            raise

    def fetch_all(
        self,
        query: str,
        params: tuple | dict | None = None,
        dictionary: bool = True,
    ) -> list[dict | tuple]:
        """
        Ejecutar un query y fetch todos los resultados.

        Args:
            query: Query SQL a ejecutar
            params: Parámetros para el query (opcional)
            dictionary: Si True, retorna lista de dicts. Si False, lista de tuplas.

        Returns:
            Lista de dicts o tuplas con los resultados
        """
        try:
            with self.get_cursor(dictionary=dictionary) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return results
        except MySQLError as e:
            logger.error(f"Error fetching all: {e}")
            logger.error(f"Query: {query[:200]}")
            raise

    def insert_and_get_id(
        self,
        query: str,
        params: tuple | dict | None = None,
    ) -> int:
        """
        Ejecutar un INSERT query y retornar el ID del row insertado.

        Args:
            query: INSERT query SQL
            params: Parámetros para el query (opcional)

        Returns:
            ID del último row insertado

        Raises:
            MySQLError: Si falla la inserción
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                self.get_connection().commit()
                row_id = cursor.lastrowid
                logger.debug(f"Inserted row with ID: {row_id}")
                return row_id
        except MySQLError as e:
            logger.error(f"Error inserting and getting ID: {e}")
            logger.error(f"Query: {query[:200]}")
            raise

    def table_exists(self, table_name: str) -> bool:
        """
        Verificar si una tabla existe en la base de datos.

        Args:
            table_name: Nombre de la tabla

        Returns:
            True si la tabla existe, False sino
        """
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_name = %s
        """
        result = self.fetch_one(
            query,
            params=(self.db_config["database"], table_name),
            dictionary=False,
        )
        return result[0] > 0 if result else False


def get_database_manager(settings: Settings) -> DatabaseManager:
    """
    Factory function para crear una instancia de DatabaseManager.

    Args:
        settings: Settings de aplicación

    Returns:
        Instancia configurada de DatabaseManager
    """
    return DatabaseManager(settings)
