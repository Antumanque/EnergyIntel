"""
Repository para operaciones de base de datos relacionadas con inteligencia de proyectos.

Este módulo maneja el almacenamiento de datos de inteligencia de negocio
extraídos mediante Claude Haiku 4.5 desde los PDFs de Resumen Ejecutivo.
"""

import logging
from typing import Any

from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ProyectoInteligenciaRepository:
    """
    Repository para inteligencia de proyectos.

    Maneja la inserción de datos de inteligencia de negocio y consultas relacionadas.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repository.

        Args:
            db_manager: Gestor de base de datos
        """
        self.db = db_manager

    def insert_inteligencia(self, inteligencia: dict[str, Any]) -> int:
        """
        Insertar inteligencia de un proyecto.

        Args:
            inteligencia: Diccionario con datos de inteligencia

        Returns:
            ID del registro insertado

        Raises:
            MySQLError: Si falla la inserción
        """
        query = """
            INSERT INTO proyecto_inteligencia (
                id_documento, industria, es_energia, sub_industria,
                ubicacion_geografica, capacidad_electrica, capacidad_termica,
                requerimientos_infraestructura, requerimientos_ingenieria,
                oportunidad_negocio, datos_clave, modelo_usado,
                status, error_message, pdf_text_length, extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                industria = VALUES(industria),
                es_energia = VALUES(es_energia),
                sub_industria = VALUES(sub_industria),
                ubicacion_geografica = VALUES(ubicacion_geografica),
                capacidad_electrica = VALUES(capacidad_electrica),
                capacidad_termica = VALUES(capacidad_termica),
                requerimientos_infraestructura = VALUES(requerimientos_infraestructura),
                requerimientos_ingenieria = VALUES(requerimientos_ingenieria),
                oportunidad_negocio = VALUES(oportunidad_negocio),
                datos_clave = VALUES(datos_clave),
                modelo_usado = VALUES(modelo_usado),
                status = VALUES(status),
                error_message = VALUES(error_message),
                pdf_text_length = VALUES(pdf_text_length),
                extracted_at = NOW()
        """

        params = (
            inteligencia["id_documento"],
            inteligencia.get("industria") or "error",  # "error" si no hay industria
            inteligencia.get("es_energia", False),
            inteligencia.get("sub_industria"),
            inteligencia.get("ubicacion_geografica"),
            inteligencia.get("capacidad_electrica"),
            inteligencia.get("capacidad_termica"),
            inteligencia.get("requerimientos_infraestructura"),
            inteligencia.get("requerimientos_ingenieria"),
            inteligencia.get("oportunidad_negocio"),
            inteligencia.get("datos_clave"),
            inteligencia.get("modelo_usado", "claude-haiku-4-5"),
            inteligencia.get("status", "pending"),
            inteligencia.get("error_message"),
            inteligencia.get("pdf_text_length"),
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted proyecto_inteligencia with ID: {row_id}")
        return row_id

    def insert_inteligencia_bulk(self, inteligencias: list[dict[str, Any]]) -> int:
        """
        Insertar múltiples registros de inteligencia en bulk.

        Args:
            inteligencias: Lista de diccionarios con datos de inteligencia

        Returns:
            Número de registros insertados/actualizados

        Raises:
            MySQLError: Si falla la inserción
        """
        if not inteligencias:
            logger.warning("No hay inteligencias para insertar")
            return 0

        query = """
            INSERT INTO proyecto_inteligencia (
                id_documento, industria, es_energia, sub_industria,
                ubicacion_geografica, capacidad_electrica, capacidad_termica,
                requerimientos_infraestructura, requerimientos_ingenieria,
                oportunidad_negocio, datos_clave, modelo_usado,
                status, error_message, pdf_text_length, extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                industria = VALUES(industria),
                es_energia = VALUES(es_energia),
                sub_industria = VALUES(sub_industria),
                ubicacion_geografica = VALUES(ubicacion_geografica),
                capacidad_electrica = VALUES(capacidad_electrica),
                capacidad_termica = VALUES(capacidad_termica),
                requerimientos_infraestructura = VALUES(requerimientos_infraestructura),
                requerimientos_ingenieria = VALUES(requerimientos_ingenieria),
                oportunidad_negocio = VALUES(oportunidad_negocio),
                datos_clave = VALUES(datos_clave),
                modelo_usado = VALUES(modelo_usado),
                status = VALUES(status),
                error_message = VALUES(error_message),
                pdf_text_length = VALUES(pdf_text_length),
                extracted_at = NOW()
        """

        params_list = []
        for intel in inteligencias:
            params_list.append((
                intel["id_documento"],
                intel.get("industria") or "error",  # "error" si no hay industria
                intel.get("es_energia", False),
                intel.get("sub_industria"),
                intel.get("ubicacion_geografica"),
                intel.get("capacidad_electrica"),
                intel.get("capacidad_termica"),
                intel.get("requerimientos_infraestructura"),
                intel.get("requerimientos_ingenieria"),
                intel.get("oportunidad_negocio"),
                intel.get("datos_clave"),
                intel.get("modelo_usado", "claude-haiku-4-5"),
                intel.get("status", "pending"),
                intel.get("error_message"),
                intel.get("pdf_text_length"),
            ))

        self.db.execute_many(query, params_list, commit=True)
        logger.info(f"Inserted/updated {len(params_list)} proyecto_inteligencia records")
        return len(params_list)

    def get_documentos_pending_intelligence(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Obtener documentos con PDF extraído que aún no tienen inteligencia procesada.

        Args:
            limit: Número máximo de documentos a retornar

        Returns:
            Lista de documentos pendientes de análisis
        """
        query = """
            SELECT
                rel.id_documento,
                rel.pdf_url
            FROM resumen_ejecutivo_links rel
            LEFT JOIN proyecto_inteligencia pi ON rel.id_documento = pi.id_documento
            WHERE rel.status IN ('pending', 'downloaded')
            AND pi.id IS NULL
            ORDER BY rel.extracted_at DESC
            LIMIT %s
        """

        results = self.db.fetch_all(query, params=(limit,), dictionary=True)
        logger.info(f"Found {len(results)} documentos pendientes de análisis de inteligencia")
        return results

    def get_documentos_with_errors(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Obtener documentos cuyo análisis de inteligencia falló.

        Args:
            limit: Número máximo de documentos a retornar

        Returns:
            Lista de documentos con errores
        """
        query = """
            SELECT
                pi.id_documento,
                pi.error_message,
                pi.extracted_at,
                rel.pdf_url
            FROM proyecto_inteligencia pi
            JOIN resumen_ejecutivo_links rel ON pi.id_documento = rel.id_documento
            WHERE pi.status = 'error'
            ORDER BY pi.extracted_at DESC
            LIMIT %s
        """

        results = self.db.fetch_all(query, params=(limit,), dictionary=True)
        logger.info(f"Found {len(results)} documentos con errores de análisis")
        return results

    def get_proyectos_energia(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Obtener proyectos del sector energía con su inteligencia.

        Args:
            limit: Número máximo de proyectos a retornar

        Returns:
            Lista de proyectos del sector energía
        """
        query = """
            SELECT
                pi.*,
                ed.expediente_id,
                ed.tipo_documento,
                p.expediente_nombre,
                p.titular,
                p.inversion_mm
            FROM proyecto_inteligencia pi
            JOIN expediente_documentos ed ON pi.id_documento = ed.id_documento
            JOIN proyectos p ON ed.expediente_id = p.expediente_id
            WHERE pi.es_energia = TRUE
            AND pi.status = 'completed'
            ORDER BY pi.extracted_at DESC
            LIMIT %s
        """

        results = self.db.fetch_all(query, params=(limit,), dictionary=True)
        logger.info(f"Found {len(results)} proyectos del sector energía")
        return results

    def get_estadisticas(self) -> dict[str, Any]:
        """
        Obtener estadísticas de inteligencia de proyectos.

        Returns:
            Diccionario con estadísticas
        """
        stats = {}

        # Total de registros de inteligencia
        result = self.db.fetch_one(
            "SELECT COUNT(*) as total FROM proyecto_inteligencia",
            dictionary=True
        )
        stats["total_inteligencia"] = result["total"] if result else 0

        # Registros por status
        result = self.db.fetch_all(
            """
            SELECT status, COUNT(*) as total
            FROM proyecto_inteligencia
            GROUP BY status
            """,
            dictionary=True
        )
        stats["por_status"] = {r["status"]: r["total"] for r in result}

        # Registros por industria
        result = self.db.fetch_all(
            """
            SELECT industria, COUNT(*) as total
            FROM proyecto_inteligencia
            WHERE status = 'completed'
            GROUP BY industria
            ORDER BY total DESC
            """,
            dictionary=True
        )
        stats["por_industria"] = {r["industria"]: r["total"] for r in result}

        # Proyectos del sector energía
        result = self.db.fetch_one(
            """
            SELECT COUNT(*) as total
            FROM proyecto_inteligencia
            WHERE es_energia = TRUE
            AND status = 'completed'
            """,
            dictionary=True
        )
        stats["total_energia"] = result["total"] if result else 0

        # Tasa de éxito (inteligencia completada vs total de links)
        result = self.db.fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM proyecto_inteligencia WHERE status = 'completed') as completados,
                (SELECT COUNT(*) FROM resumen_ejecutivo_links) as total_links
            """,
            dictionary=True
        )
        if result and result["total_links"] > 0:
            stats["tasa_exito"] = round(
                (result["completados"] / result["total_links"]) * 100, 2
            )
        else:
            stats["tasa_exito"] = 0.0

        return stats


def get_proyecto_inteligencia_repository(
    db_manager: DatabaseManager,
) -> ProyectoInteligenciaRepository:
    """
    Factory function para crear una instancia de ProyectoInteligenciaRepository.

    Args:
        db_manager: Gestor de base de datos

    Returns:
        Instancia de ProyectoInteligenciaRepository
    """
    return ProyectoInteligenciaRepository(db_manager)
