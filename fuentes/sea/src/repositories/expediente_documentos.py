"""
Repository para operaciones de base de datos relacionadas con documentos del expediente.

Este módulo maneja el almacenamiento de documentos EIA/DIA encontrados
en cada expediente.
"""

import logging
from typing import Any

from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ExpedienteDocumentosRepository:
    """
    Repository para documentos del expediente.

    Maneja la inserción de documentos EIA/DIA y consultas relacionadas.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repository.

        Args:
            db_manager: Gestor de base de datos
        """
        self.db = db_manager

    def insert_documento(self, documento: dict[str, Any]) -> int:
        """
        Insertar un documento del expediente.

        Args:
            documento: Diccionario con datos del documento

        Returns:
            ID del registro insertado

        Raises:
            MySQLError: Si falla la inserción
        """
        query = """
            INSERT INTO expediente_documentos (
                expediente_id, id_documento, folio, tipo_documento,
                remitente, destinatario, fecha_generacion,
                url_documento, url_anexos, extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                folio = VALUES(folio),
                tipo_documento = VALUES(tipo_documento),
                remitente = VALUES(remitente),
                destinatario = VALUES(destinatario),
                fecha_generacion = VALUES(fecha_generacion),
                url_documento = VALUES(url_documento),
                url_anexos = VALUES(url_anexos),
                extracted_at = VALUES(extracted_at)
        """

        params = (
            documento["expediente_id"],
            documento["id_documento"],
            documento.get("folio"),
            documento.get("tipo_documento"),
            documento.get("remitente"),
            documento.get("destinatario"),
            documento.get("fecha_generacion"),
            documento.get("url_documento"),
            documento.get("url_anexos"),
            documento["extracted_at"],
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted expediente_documento with ID: {row_id}")
        return row_id

    def insert_documentos_bulk(self, documentos: list[dict[str, Any]]) -> int:
        """
        Insertar múltiples documentos en bulk.

        Args:
            documentos: Lista de diccionarios con datos de documentos

        Returns:
            Número de registros insertados/actualizados

        Raises:
            MySQLError: Si falla la inserción
        """
        if not documentos:
            logger.warning("No hay documentos para insertar")
            return 0

        query = """
            INSERT INTO expediente_documentos (
                expediente_id, id_documento, folio, tipo_documento,
                remitente, destinatario, fecha_generacion,
                url_documento, url_anexos, extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                folio = VALUES(folio),
                tipo_documento = VALUES(tipo_documento),
                remitente = VALUES(remitente),
                destinatario = VALUES(destinatario),
                fecha_generacion = VALUES(fecha_generacion),
                url_documento = VALUES(url_documento),
                url_anexos = VALUES(url_anexos),
                extracted_at = VALUES(extracted_at)
        """

        params_list = []
        for doc in documentos:
            params_list.append((
                doc["expediente_id"],
                doc["id_documento"],
                doc.get("folio"),
                doc.get("tipo_documento"),
                doc.get("remitente"),
                doc.get("destinatario"),
                doc.get("fecha_generacion"),
                doc.get("url_documento"),
                doc.get("url_anexos"),
                doc["extracted_at"],
            ))

        self.db.execute_many(query, params_list, commit=True)
        logger.info(f"Inserted/updated {len(params_list)} expediente_documentos")
        return len(params_list)

    def get_documentos_sin_resumen_ejecutivo(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Obtener documentos que aún no tienen resumen ejecutivo extraído.

        Args:
            limit: Número máximo de documentos a retornar

        Returns:
            Lista de documentos pendientes
        """
        query = """
            SELECT
                ed.id,
                ed.expediente_id,
                ed.id_documento,
                ed.folio,
                ed.tipo_documento,
                ed.url_documento
            FROM expediente_documentos ed
            LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
            WHERE rel.id IS NULL
            AND ed.parsed_at IS NULL
            ORDER BY ed.extracted_at DESC
            LIMIT %s
        """

        results = self.db.fetch_all(query, params=(limit,), dictionary=True)
        logger.info(f"Found {len(results)} documentos sin resumen ejecutivo")
        return results

    def mark_as_parsed(self, id_documento: int):
        """
        Marcar un documento como parseado.

        Args:
            id_documento: ID del documento
        """
        query = """
            UPDATE expediente_documentos
            SET parsed_at = NOW()
            WHERE id_documento = %s
        """

        self.db.execute_query(query, params=(id_documento,), commit=True)
        logger.debug(f"Marked documento {id_documento} as parsed")

    def get_estadisticas(self) -> dict[str, Any]:
        """
        Obtener estadísticas de documentos del expediente.

        Returns:
            Diccionario con estadísticas
        """
        stats = {}

        # Total de documentos
        result = self.db.fetch_one(
            "SELECT COUNT(*) as total FROM expediente_documentos",
            dictionary=True
        )
        stats["total_documentos"] = result["total"] if result else 0

        # Documentos por tipo
        result = self.db.fetch_all(
            """
            SELECT tipo_documento, COUNT(*) as total
            FROM expediente_documentos
            GROUP BY tipo_documento
            """,
            dictionary=True
        )
        stats["por_tipo"] = {r["tipo_documento"]: r["total"] for r in result}

        # Documentos con resumen ejecutivo
        result = self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT ed.id_documento) as total
            FROM expediente_documentos ed
            INNER JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
            """,
            dictionary=True
        )
        stats["con_resumen_ejecutivo"] = result["total"] if result else 0

        return stats


def get_expediente_documentos_repository(
    db_manager: DatabaseManager,
) -> ExpedienteDocumentosRepository:
    """
    Factory function para crear una instancia de ExpedienteDocumentosRepository.

    Args:
        db_manager: Gestor de base de datos

    Returns:
        Instancia de ExpedienteDocumentosRepository
    """
    return ExpedienteDocumentosRepository(db_manager)
