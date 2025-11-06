"""
Repository para operaciones de base de datos relacionadas con links de Resumen Ejecutivo.

Este módulo maneja el almacenamiento de links a PDFs de Capítulo 20 - Resumen Ejecutivo.
"""

import logging
from typing import Any

from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ResumenEjecutivoLinksRepository:
    """
    Repository para links de Resumen Ejecutivo.

    Maneja la inserción de links a PDFs y consultas relacionadas.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repository.

        Args:
            db_manager: Gestor de base de datos
        """
        self.db = db_manager

    def insert_link(self, link: dict[str, Any]) -> int:
        """
        Insertar un link de resumen ejecutivo.

        Args:
            link: Diccionario con datos del link

        Returns:
            ID del registro insertado

        Raises:
            MySQLError: Si falla la inserción
        """
        query = """
            INSERT INTO resumen_ejecutivo_links (
                id_documento, pdf_url, pdf_filename, texto_link,
                documento_firmado_url, documento_firmado_docid,
                extracted_at, status, match_criteria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pdf_url = VALUES(pdf_url),
                pdf_filename = VALUES(pdf_filename),
                texto_link = VALUES(texto_link),
                documento_firmado_url = VALUES(documento_firmado_url),
                documento_firmado_docid = VALUES(documento_firmado_docid),
                extracted_at = VALUES(extracted_at),
                match_criteria = VALUES(match_criteria)
        """

        params = (
            link["id_documento"],
            link["pdf_url"],
            link.get("pdf_filename"),
            link.get("texto_link"),
            link.get("documento_firmado_url"),
            link.get("documento_firmado_docid"),
            link["extracted_at"],
            link.get("status", "pending"),
            link.get("match_criteria"),
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted resumen_ejecutivo_link with ID: {row_id}")
        return row_id

    def insert_links_bulk(self, links: list[dict[str, Any]]) -> int:
        """
        Insertar múltiples links en bulk.

        Args:
            links: Lista de diccionarios con datos de links

        Returns:
            Número de registros insertados/actualizados

        Raises:
            MySQLError: Si falla la inserción
        """
        if not links:
            logger.warning("No hay links para insertar")
            return 0

        query = """
            INSERT INTO resumen_ejecutivo_links (
                id_documento, pdf_url, pdf_filename, texto_link,
                documento_firmado_url, documento_firmado_docid,
                extracted_at, status, match_criteria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pdf_url = VALUES(pdf_url),
                pdf_filename = VALUES(pdf_filename),
                texto_link = VALUES(texto_link),
                documento_firmado_url = VALUES(documento_firmado_url),
                documento_firmado_docid = VALUES(documento_firmado_docid),
                extracted_at = VALUES(extracted_at),
                match_criteria = VALUES(match_criteria)
        """

        params_list = []
        for link in links:
            params_list.append((
                link["id_documento"],
                link["pdf_url"],
                link.get("pdf_filename"),
                link.get("texto_link"),
                link.get("documento_firmado_url"),
                link.get("documento_firmado_docid"),
                link["extracted_at"],
                link.get("status", "pending"),
                link.get("match_criteria"),
            ))

        self.db.execute_many(query, params_list, commit=True)
        logger.info(f"Inserted/updated {len(params_list)} resumen_ejecutivo_links")
        return len(params_list)

    def get_links_pending_download(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Obtener links que aún no han sido descargados.

        Args:
            limit: Número máximo de links a retornar

        Returns:
            Lista de links pendientes de descarga
        """
        query = """
            SELECT
                id,
                id_documento,
                pdf_url,
                pdf_filename,
                texto_link
            FROM resumen_ejecutivo_links
            WHERE status = 'pending'
            AND pdf_downloaded_at IS NULL
            ORDER BY extracted_at DESC
            LIMIT %s
        """

        results = self.db.fetch_all(query, params=(limit,), dictionary=True)
        logger.info(f"Found {len(results)} links pendientes de descarga")
        return results

    def mark_as_downloaded(self, id_documento: int):
        """
        Marcar un link como descargado.

        Args:
            id_documento: ID del documento
        """
        query = """
            UPDATE resumen_ejecutivo_links
            SET pdf_downloaded_at = NOW(),
                status = 'downloaded'
            WHERE id_documento = %s
        """

        self.db.execute_query(query, params=(id_documento,), commit=True)
        logger.debug(f"Marked link {id_documento} as downloaded")

    def mark_as_parsed(self, id_documento: int):
        """
        Marcar un link como parseado.

        Args:
            id_documento: ID del documento
        """
        query = """
            UPDATE resumen_ejecutivo_links
            SET pdf_parsed_at = NOW(),
                status = 'parsed'
            WHERE id_documento = %s
        """

        self.db.execute_query(query, params=(id_documento,), commit=True)
        logger.debug(f"Marked link {id_documento} as parsed")

    def update_status(
        self, id_documento: int, status: str, error_message: str | None = None
    ):
        """
        Actualizar el status de un link y opcionalmente un mensaje de error.

        Args:
            id_documento: ID del documento
            status: Nuevo status ('pending', 'downloaded', 'parsed', 'error')
            error_message: Mensaje de error opcional
        """
        query = """
            UPDATE resumen_ejecutivo_links
            SET status = %s,
                error_message = %s
            WHERE id_documento = %s
        """

        params = (status, error_message, id_documento)
        self.db.execute_query(query, params=params, commit=True)
        logger.debug(f"Updated status for link {id_documento} to {status}")

    def get_estadisticas(self) -> dict[str, Any]:
        """
        Obtener estadísticas de links de resumen ejecutivo.

        Returns:
            Diccionario con estadísticas
        """
        stats = {}

        # Total de links
        result = self.db.fetch_one(
            "SELECT COUNT(*) as total FROM resumen_ejecutivo_links",
            dictionary=True
        )
        stats["total_links"] = result["total"] if result else 0

        # Links por status
        result = self.db.fetch_all(
            """
            SELECT status, COUNT(*) as total
            FROM resumen_ejecutivo_links
            GROUP BY status
            """,
            dictionary=True
        )
        stats["por_status"] = {r["status"]: r["total"] for r in result}

        # Links con documento firmado
        result = self.db.fetch_one(
            """
            SELECT COUNT(*) as total
            FROM resumen_ejecutivo_links
            WHERE documento_firmado_url IS NOT NULL
            """,
            dictionary=True
        )
        stats["con_documento_firmado"] = result["total"] if result else 0

        # Tasa de éxito (documentos con link encontrado vs total de documentos)
        result = self.db.fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM resumen_ejecutivo_links) as con_link,
                (SELECT COUNT(*) FROM expediente_documentos) as total_docs
            """,
            dictionary=True
        )
        if result and result["total_docs"] > 0:
            stats["tasa_exito"] = round(
                (result["con_link"] / result["total_docs"]) * 100, 2
            )
        else:
            stats["tasa_exito"] = 0.0

        return stats


def get_resumen_ejecutivo_links_repository(
    db_manager: DatabaseManager,
) -> ResumenEjecutivoLinksRepository:
    """
    Factory function para crear una instancia de ResumenEjecutivoLinksRepository.

    Args:
        db_manager: Gestor de base de datos

    Returns:
        Instancia de ResumenEjecutivoLinksRepository
    """
    return ResumenEjecutivoLinksRepository(db_manager)
