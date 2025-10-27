"""
Repositorio para la tabla raw_data.

Este módulo provee funcionalidad para interactuar con la tabla raw_data.
"""

import json
import logging
from datetime import datetime
from typing import Any

from src.core.database import DatabaseManager
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class RawDataRepository(BaseRepository):
    """
    Repositorio para operaciones sobre la tabla raw_data.

    Maneja inserción y consulta de datos crudos extraídos.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repositorio.

        Args:
            db_manager: Instancia de DatabaseManager
        """
        super().__init__(db_manager)

    def insert(
        self,
        source_url: str,
        source_type: str,
        status_code: int,
        data: Any,
        error_message: str | None = None,
        extracted_at: datetime | None = None,
    ) -> int:
        """
        Insertar un registro de extracción en raw_data.

        Args:
            source_url: URL o identificador de la fuente
            source_type: Tipo de fuente (api_rest, web_static, etc.)
            status_code: Código de status HTTP o custom
            data: Datos extraídos (se convertirán a JSON)
            error_message: Mensaje de error opcional
            extracted_at: Timestamp de extracción (usa now() si None)

        Returns:
            ID del registro insertado
        """
        # Convert data to JSON string if it's not None
        data_json = json.dumps(data) if data is not None else None

        # Use current time if not provided
        if extracted_at is None:
            extracted_at = datetime.now()

        query = """
            INSERT INTO raw_data (
                source_url, source_type, status_code, data, error_message, extracted_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
        """

        params = (
            source_url,
            source_type,
            status_code,
            data_json,
            error_message,
            extracted_at,
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted raw_data record with ID: {row_id}")

        return row_id

    def insert_many(self, records: list[dict[str, Any]]) -> list[int]:
        """
        Insertar múltiples registros de extracción.

        Args:
            records: Lista de dicts con keys: source_url, source_type, status_code,
                     data, error_message, extracted_at

        Returns:
            Lista de IDs insertados
        """
        ids = []
        for record in records:
            row_id = self.insert(
                source_url=record["source_url"],
                source_type=record.get("source_type", "other"),
                status_code=record["status_code"],
                data=record.get("data"),
                error_message=record.get("error_message"),
                extracted_at=record.get("extracted_at"),
            )
            ids.append(row_id)

        logger.info(f"Inserted {len(ids)} records into raw_data")
        return ids

    def get_by_id(self, record_id: int) -> dict | None:
        """
        Obtener un registro por ID.

        Args:
            record_id: ID del registro

        Returns:
            Diccionario con el registro o None si no existe
        """
        query = "SELECT * FROM raw_data WHERE id = %s"
        return self.db.fetch_one(query, (record_id,))

    def get_latest_by_url(self, source_url: str) -> dict | None:
        """
        Obtener la extracción más reciente para una URL.

        Args:
            source_url: URL de la fuente

        Returns:
            Diccionario con el registro más reciente o None
        """
        query = """
            SELECT * FROM raw_data
            WHERE source_url = %s
            ORDER BY extracted_at DESC
            LIMIT 1
        """
        return self.db.fetch_one(query, (source_url,))

    def get_successful_extractions(
        self, source_type: str | None = None, limit: int = 100
    ) -> list[dict]:
        """
        Obtener extracciones exitosas.

        Args:
            source_type: Filtrar por tipo de fuente (opcional)
            limit: Número máximo de registros a retornar

        Returns:
            Lista de registros exitosos
        """
        if source_type:
            query = """
                SELECT * FROM successful_extractions
                WHERE source_type = %s
                ORDER BY extracted_at DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (source_type, limit))
        else:
            query = """
                SELECT * FROM successful_extractions
                ORDER BY extracted_at DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (limit,))

    def get_statistics(self) -> list[dict]:
        """
        Obtener estadísticas de extracción.

        Returns:
            Lista de dicts con estadísticas por tipo de fuente
        """
        query = "SELECT * FROM extraction_statistics"
        return self.db.fetch_all(query)


class ParsedDataRepository(BaseRepository):
    """
    Repositorio para operaciones sobre la tabla parsed_data.

    Maneja inserción y consulta de datos parseados.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repositorio.

        Args:
            db_manager: Instancia de DatabaseManager
        """
        super().__init__(db_manager)

    def insert(
        self,
        raw_data_id: int,
        parser_type: str,
        parsing_successful: bool,
        parsed_content: Any | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """
        Insertar un registro de parseo.

        Args:
            raw_data_id: ID del registro raw_data correspondiente
            parser_type: Tipo de parser (json, pdf, xlsx, etc.)
            parsing_successful: Si el parseo fue exitoso
            parsed_content: Contenido parseado (se convertirá a JSON)
            error_message: Mensaje de error opcional
            metadata: Metadata adicional opcional

        Returns:
            ID del registro insertado
        """
        parsed_json = json.dumps(parsed_content) if parsed_content is not None else None
        metadata_json = json.dumps(metadata) if metadata is not None else None

        query = """
            INSERT INTO parsed_data (
                raw_data_id, parser_type, parsing_successful,
                parsed_content, error_message, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
        """

        params = (
            raw_data_id,
            parser_type,
            parsing_successful,
            parsed_json,
            error_message,
            metadata_json,
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted parsed_data record with ID: {row_id}")

        return row_id

    def get_successful_parsings(
        self, parser_type: str | None = None, limit: int = 100
    ) -> list[dict]:
        """
        Obtener parseos exitosos.

        Args:
            parser_type: Filtrar por tipo de parser (opcional)
            limit: Número máximo de registros a retornar

        Returns:
            Lista de registros de parseos exitosos
        """
        if parser_type:
            query = """
                SELECT * FROM successful_parsings
                WHERE parser_type = %s
                ORDER BY parsed_at DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (parser_type, limit))
        else:
            query = """
                SELECT * FROM successful_parsings
                ORDER BY parsed_at DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (limit,))


def get_raw_data_repository(db_manager: DatabaseManager) -> RawDataRepository:
    """Factory function para crear RawDataRepository."""
    return RawDataRepository(db_manager)


def get_parsed_data_repository(db_manager: DatabaseManager) -> ParsedDataRepository:
    """Factory function para crear ParsedDataRepository."""
    return ParsedDataRepository(db_manager)
