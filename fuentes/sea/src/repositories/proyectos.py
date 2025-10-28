"""
Repository para operaciones de base de datos relacionadas con proyectos del SEA.

Este módulo maneja el almacenamiento de datos crudos y proyectos parseados
siguiendo una estrategia append-only.
"""

import json
import logging
from typing import Any

from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ProyectosRepository:
    """
    Repository para proyectos del SEA.

    Maneja la inserción de datos crudos (raw_data) y datos parseados (proyectos)
    en la base de datos, siguiendo una estrategia append-only.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repository.

        Args:
            db_manager: Gestor de base de datos
        """
        self.db = db_manager

    def insert_raw_data(self, extraction_result: dict[str, Any]) -> int:
        """
        Insertar datos crudos de extracción en la tabla raw_data.

        Args:
            extraction_result: Diccionario con resultado de extracción

        Returns:
            ID del registro insertado

        Raises:
            MySQLError: Si falla la inserción
        """
        # Preparar datos para inserción
        data_json = None
        if extraction_result.get("data") is not None:
            # Si data es dict, convertir a JSON
            if isinstance(extraction_result["data"], dict):
                data_json = json.dumps(extraction_result["data"], ensure_ascii=False)
            else:
                # Si es string, usarlo directamente
                data_json = extraction_result["data"]

        query = """
            INSERT INTO raw_data (
                source_url,
                source_type,
                status_code,
                data,
                error_message,
                extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        params = (
            extraction_result["source_url"],
            extraction_result.get("source_type", "api_rest"),
            extraction_result["status_code"],
            data_json,
            extraction_result.get("error_message"),
            extraction_result["extracted_at"],
        )

        row_id = self.db.insert_and_get_id(query, params)
        logger.debug(f"Inserted raw_data with ID: {row_id}")
        return row_id

    def insert_raw_data_bulk(self, extraction_results: list[dict[str, Any]]) -> int:
        """
        Insertar múltiples registros de datos crudos en bulk.

        Args:
            extraction_results: Lista de diccionarios con resultados de extracción

        Returns:
            Número de registros insertados

        Raises:
            MySQLError: Si falla la inserción
        """
        if not extraction_results:
            logger.warning("No hay resultados de extracción para insertar")
            return 0

        query = """
            INSERT INTO raw_data (
                source_url,
                source_type,
                status_code,
                data,
                error_message,
                extracted_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        params_list = []
        for result in extraction_results:
            # Preparar data JSON
            data_json = None
            if result.get("data") is not None:
                if isinstance(result["data"], dict):
                    data_json = json.dumps(result["data"], ensure_ascii=False)
                else:
                    data_json = result["data"]

            params_list.append(
                (
                    result["source_url"],
                    result.get("source_type", "api_rest"),
                    result["status_code"],
                    data_json,
                    result.get("error_message"),
                    result["extracted_at"],
                )
            )

        self.db.execute_many(query, params_list, commit=True)
        logger.info(f"Inserted {len(params_list)} raw_data records")
        return len(params_list)

    def get_existing_expediente_ids(self) -> set[int]:
        """
        Obtener todos los expediente_id existentes en la tabla proyectos.

        Esto se usa para implementar la estrategia append-only: solo insertar
        proyectos nuevos que no existan en la base de datos.

        Returns:
            Set de expediente_id existentes
        """
        query = "SELECT expediente_id FROM proyectos"
        results = self.db.fetch_all(query, dictionary=False)
        existing_ids = {row[0] for row in results if row[0] is not None}
        logger.debug(f"Found {len(existing_ids)} existing expediente_ids")
        return existing_ids

    def insert_proyectos_bulk(self, proyectos: list[dict[str, Any]]) -> tuple[int, int]:
        """
        Insertar múltiples proyectos en bulk, solo los que no existan.

        Implementa estrategia append-only: filtra proyectos que ya existen en la BD
        y solo inserta los nuevos.

        Args:
            proyectos: Lista de diccionarios con datos de proyectos parseados

        Returns:
            Tupla (num_insertados, num_duplicados)

        Raises:
            MySQLError: Si falla la inserción
        """
        if not proyectos:
            logger.warning("No hay proyectos para insertar")
            return 0, 0

        # Primero deduplicar dentro del batch (la API puede devolver duplicados)
        seen_ids = set()
        unique_proyectos = []
        for p in proyectos:
            pid = p.get("expediente_id")
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_proyectos.append(p)

        batch_duplicates = len(proyectos) - len(unique_proyectos)
        if batch_duplicates > 0:
            logger.info(f"Removed {batch_duplicates} duplicates within batch")

        # Obtener IDs existentes
        existing_ids = self.get_existing_expediente_ids()

        # Filtrar solo proyectos nuevos
        new_proyectos = [
            p for p in unique_proyectos if p.get("expediente_id") not in existing_ids
        ]
        num_duplicated = len(unique_proyectos) - len(new_proyectos)

        if num_duplicated > 0:
            logger.info(
                f"Skipping {num_duplicated} duplicate proyectos (already in database)"
            )

        if not new_proyectos:
            logger.info("No new proyectos to insert (all were duplicates)")
            return 0, num_duplicated

        # Preparar query de inserción
        query = """
            INSERT INTO proyectos (
                expediente_id, expediente_nombre, expediente_url_ppal, expediente_url_ficha,
                workflow_descripcion, region_nombre, comuna_nombre,
                tipo_proyecto, descripcion_tipologia, razon_ingreso, titular,
                inversion_mm, inversion_mm_format,
                fecha_presentacion, fecha_presentacion_format,
                fecha_plazo, fecha_plazo_format,
                estado_proyecto, encargado, actividad_actual, etapa,
                link_mapa_show, link_mapa_url, link_mapa_image,
                acciones, dias_legales, suspendido, ver_actividad
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        # Preparar parámetros
        params_list = []
        for p in new_proyectos:
            params_list.append(
                (
                    p.get("expediente_id"),
                    p.get("expediente_nombre"),
                    p.get("expediente_url_ppal"),
                    p.get("expediente_url_ficha"),
                    p.get("workflow_descripcion"),
                    p.get("region_nombre"),
                    p.get("comuna_nombre"),
                    p.get("tipo_proyecto"),
                    p.get("descripcion_tipologia"),
                    p.get("razon_ingreso"),
                    p.get("titular"),
                    p.get("inversion_mm"),
                    p.get("inversion_mm_format"),
                    p.get("fecha_presentacion"),
                    p.get("fecha_presentacion_format"),
                    p.get("fecha_plazo"),
                    p.get("fecha_plazo_format"),
                    p.get("estado_proyecto"),
                    p.get("encargado"),
                    p.get("actividad_actual"),
                    p.get("etapa"),
                    p.get("link_mapa_show"),
                    p.get("link_mapa_url"),
                    p.get("link_mapa_image"),
                    p.get("acciones"),
                    p.get("dias_legales"),
                    p.get("suspendido"),
                    p.get("ver_actividad"),
                )
            )

        # Ejecutar inserción en bulk
        self.db.execute_many(query, params_list, commit=True)
        logger.info(f"Inserted {len(params_list)} new proyectos")
        return len(params_list), num_duplicated

    def get_proyecto_by_id(self, expediente_id: int) -> dict | None:
        """
        Obtener un proyecto por su expediente_id.

        Args:
            expediente_id: ID del expediente a buscar

        Returns:
            Diccionario con datos del proyecto, o None si no existe
        """
        query = "SELECT * FROM proyectos WHERE expediente_id = %s"
        result = self.db.fetch_one(query, params=(expediente_id,), dictionary=True)
        return result

    def get_estadisticas(self) -> dict[str, Any]:
        """
        Obtener estadísticas generales de la base de datos.

        Returns:
            Diccionario con estadísticas
        """
        stats = {}

        # Total de proyectos
        result = self.db.fetch_one(
            "SELECT COUNT(*) as total FROM proyectos", dictionary=True
        )
        stats["total_proyectos"] = result["total"] if result else 0

        # Total por tipo de evaluación
        result = self.db.fetch_all(
            """
            SELECT workflow_descripcion, COUNT(*) as total
            FROM proyectos
            GROUP BY workflow_descripcion
            """,
            dictionary=True,
        )
        stats["por_tipo"] = {r["workflow_descripcion"]: r["total"] for r in result}

        # Total por región (top 10)
        result = self.db.fetch_all(
            """
            SELECT region_nombre, COUNT(*) as total
            FROM proyectos
            GROUP BY region_nombre
            ORDER BY total DESC
            LIMIT 10
            """,
            dictionary=True,
        )
        stats["top_regiones"] = {r["region_nombre"]: r["total"] for r in result}

        # Total de extracciones en raw_data
        result = self.db.fetch_one(
            "SELECT COUNT(*) as total FROM raw_data", dictionary=True
        )
        stats["total_raw_extractions"] = result["total"] if result else 0

        return stats


def get_proyectos_repository(db_manager: DatabaseManager) -> ProyectosRepository:
    """
    Factory function para crear una instancia de ProyectosRepository.

    Args:
        db_manager: Gestor de base de datos

    Returns:
        Instancia de ProyectosRepository
    """
    return ProyectosRepository(db_manager)
