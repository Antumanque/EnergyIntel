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
            # Preparar data JSON - asegurar que sea string JSON válido
            data_json = None
            if result.get("data") is not None:
                if isinstance(result["data"], dict):
                    # Convertir a JSON string sin ensure_ascii=False para evitar problemas
                    data_json = json.dumps(result["data"])
                elif isinstance(result["data"], str):
                    # Si ya es string, usarlo tal cual
                    data_json = result["data"]
                else:
                    # Si es bytes, decodificar primero
                    data_json = result["data"].decode('utf-8') if isinstance(result["data"], bytes) else str(result["data"])

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

    # Campos que se comparan para detectar cambios
    COMPARE_FIELDS = [
        "expediente_nombre", "workflow_descripcion", "region_nombre", "comuna_nombre",
        "tipo_proyecto", "descripcion_tipologia", "razon_ingreso", "titular",
        "inversion_mm", "estado_proyecto", "encargado", "actividad_actual", "etapa",
        "fecha_plazo", "dias_legales", "suspendido"
    ]

    def upsert_proyectos_bulk(
        self,
        proyectos: list[dict[str, Any]],
        pipeline_run_id: int | None = None
    ) -> dict[str, int]:
        """
        Insertar o actualizar múltiples proyectos en bulk (UPSERT).

        Implementa estrategia upsert:
        - Proyectos nuevos: se insertan con created_at = NOW()
        - Proyectos existentes con cambios: se actualizan con updated_at = NOW()
        - Proyectos existentes sin cambios: no se modifican

        Args:
            proyectos: Lista de diccionarios con datos de proyectos parseados
            pipeline_run_id: ID del pipeline run actual (para historial)

        Returns:
            Dict con estadísticas: {nuevos, actualizados, sin_cambios, total}

        Raises:
            MySQLError: Si falla la operación
        """
        if not proyectos:
            logger.warning("No hay proyectos para procesar")
            return {"nuevos": 0, "actualizados": 0, "sin_cambios": 0, "total": 0}

        # Deduplicar proyectos dentro del batch (quedarse con el último)
        proyectos_dict = {p.get("expediente_id"): p for p in proyectos if p.get("expediente_id")}
        proyectos_unicos = list(proyectos_dict.values())

        stats = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0, "total": len(proyectos_unicos)}

        if len(proyectos) != len(proyectos_unicos):
            logger.debug(f"Deduplicados {len(proyectos) - len(proyectos_unicos)} proyectos repetidos en batch")

        # Obtener proyectos existentes para comparar
        expediente_ids = list(proyectos_dict.keys())
        existing = self._get_proyectos_by_ids(expediente_ids)

        # Clasificar proyectos
        classified = self._classify_proyectos(proyectos_unicos, existing)
        nuevos = classified["nuevos"]
        actualizados = classified["actualizados"]
        stats["sin_cambios"] = len(classified["sin_cambios"])

        # Insertar nuevos
        if nuevos:
            self._insert_proyectos_new(nuevos)
            self._record_history(nuevos, "INSERT", pipeline_run_id)
            stats["nuevos"] = len(nuevos)
            logger.info(f"Insertados {len(nuevos)} proyectos nuevos")

        # Actualizar existentes con cambios
        if actualizados:
            self._update_proyectos_changed(actualizados)
            self._record_history(actualizados, "UPDATE", pipeline_run_id)
            stats["actualizados"] = len(actualizados)
            logger.info(f"Actualizados {len(actualizados)} proyectos con cambios")

        if stats["sin_cambios"] > 0:
            logger.info(f"Sin cambios: {stats['sin_cambios']} proyectos")

        return stats

    def _classify_proyectos(
        self,
        proyectos: list[dict[str, Any]],
        existing: dict[int, dict]
    ) -> dict[str, list]:
        """
        Clasifica proyectos en nuevos, actualizados, y sin cambios.

        Returns:
            Dict con listas: {"nuevos": [...], "actualizados": [...], "sin_cambios": [...]}
        """
        nuevos = []
        actualizados = []
        sin_cambios = []

        for p in proyectos:
            exp_id = p.get("expediente_id")
            if exp_id not in existing:
                nuevos.append(p)
            else:
                old = existing[exp_id]
                has_changes = False
                changed_fields = []

                for field in self.COMPARE_FIELDS:
                    old_val = old.get(field)
                    new_val = p.get(field)
                    if old_val != new_val:
                        has_changes = True
                        changed_fields.append({
                            "field": field,
                            "old": old_val,
                            "new": new_val
                        })

                if has_changes:
                    p["_changed_fields"] = changed_fields
                    actualizados.append(p)
                else:
                    sin_cambios.append(p)

        return {"nuevos": nuevos, "actualizados": actualizados, "sin_cambios": sin_cambios}

    def preview_proyectos_bulk(
        self,
        proyectos: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Previsualiza que proyectos serian insertados/actualizados sin escribir a la BD.

        Args:
            proyectos: Lista de diccionarios con datos de proyectos

        Returns:
            Dict con listas detalladas:
            {
                "nuevos": [lista de proyectos nuevos],
                "actualizados": [lista de proyectos con cambios, incluye _changed_fields],
                "sin_cambios": [lista de proyectos sin cambios],
                "counts": {"nuevos": N, "actualizados": N, "sin_cambios": N}
            }
        """
        if not proyectos:
            return {
                "nuevos": [], "actualizados": [], "sin_cambios": [],
                "counts": {"nuevos": 0, "actualizados": 0, "sin_cambios": 0}
            }

        logger.info(f"[PREVIEW] Analizando {len(proyectos)} proyectos...")

        # Deduplicar
        proyectos_dict = {p.get("expediente_id"): p for p in proyectos if p.get("expediente_id")}
        proyectos_unicos = list(proyectos_dict.values())

        # Obtener existentes
        expediente_ids = list(proyectos_dict.keys())
        existing = self._get_proyectos_by_ids(expediente_ids)

        # Clasificar
        classified = self._classify_proyectos(proyectos_unicos, existing)

        logger.info(
            f"[PREVIEW] Proyectos: {len(classified['nuevos'])} nuevos, "
            f"{len(classified['actualizados'])} actualizados, "
            f"{len(classified['sin_cambios'])} sin cambios"
        )

        return {
            **classified,
            "counts": {
                "nuevos": len(classified["nuevos"]),
                "actualizados": len(classified["actualizados"]),
                "sin_cambios": len(classified["sin_cambios"]),
                "total": len(proyectos_unicos)
            }
        }

    def _get_proyectos_by_ids(self, expediente_ids: list[int]) -> dict[int, dict]:
        """Obtener proyectos existentes por IDs (en batches para evitar límites de MySQL)."""
        if not expediente_ids:
            return {}

        # Procesar en batches de 1000 para evitar límites de MySQL
        BATCH_SIZE = 1000
        all_results = {}

        for i in range(0, len(expediente_ids), BATCH_SIZE):
            batch_ids = expediente_ids[i:i + BATCH_SIZE]
            placeholders = ",".join(["%s"] * len(batch_ids))
            query = f"SELECT * FROM proyectos WHERE expediente_id IN ({placeholders})"
            results = self.db.fetch_all(query, params=tuple(batch_ids), dictionary=True)
            for r in results:
                all_results[r["expediente_id"]] = r

        return all_results

    def _insert_proyectos_new(
        self,
        proyectos: list[dict[str, Any]]
    ) -> None:
        """Insertar proyectos nuevos."""
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
                acciones, dias_legales, suspendido, ver_actividad,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
        """
        params_list = [self._proyecto_to_params(p) for p in proyectos]
        self.db.execute_many(query, params_list, commit=True)

    def _update_proyectos_changed(
        self,
        proyectos: list[dict[str, Any]]
    ) -> None:
        """Actualizar proyectos que tienen cambios."""
        query = """
            UPDATE proyectos SET
                expediente_nombre = %s, expediente_url_ppal = %s, expediente_url_ficha = %s,
                workflow_descripcion = %s, region_nombre = %s, comuna_nombre = %s,
                tipo_proyecto = %s, descripcion_tipologia = %s, razon_ingreso = %s, titular = %s,
                inversion_mm = %s, inversion_mm_format = %s,
                fecha_presentacion = %s, fecha_presentacion_format = %s,
                fecha_plazo = %s, fecha_plazo_format = %s,
                estado_proyecto = %s, encargado = %s, actividad_actual = %s, etapa = %s,
                link_mapa_show = %s, link_mapa_url = %s, link_mapa_image = %s,
                acciones = %s, dias_legales = %s, suspendido = %s, ver_actividad = %s,
                updated_at = NOW()
            WHERE expediente_id = %s
        """
        params_list = []
        for p in proyectos:
            base_params = self._proyecto_to_params_for_update(p)
            params = base_params + (p.get("expediente_id"),)
            params_list.append(params)
        self.db.execute_many(query, params_list, commit=True)

    def _record_history(
        self,
        proyectos: list[dict[str, Any]],
        operation: str,
        pipeline_run_id: int | None = None
    ) -> None:
        """
        Registrar cambios en la tabla de historial.

        Args:
            proyectos: Lista de proyectos insertados o actualizados
            operation: 'INSERT' o 'UPDATE'
            pipeline_run_id: ID del pipeline run actual
        """
        if not proyectos:
            return

        # Verificar si la tabla existe (para compatibilidad con BDs sin migrar)
        try:
            self.db.fetch_one("SELECT 1 FROM proyectos_history LIMIT 1")
        except Exception:
            logger.debug("Tabla proyectos_history no existe, omitiendo registro de historial")
            return

        query = """
            INSERT INTO proyectos_history (
                expediente_id, operation, pipeline_run_id, changed_fields,
                expediente_nombre, workflow_descripcion, region_nombre,
                tipo_proyecto, titular, estado_proyecto, actividad_actual,
                etapa, inversion_mm
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        params_list = []
        for p in proyectos:
            # Convertir changed_fields a JSON string
            changed_fields = p.get("_changed_fields")
            changed_fields_json = json.dumps(changed_fields) if changed_fields else None

            params = (
                p.get("expediente_id"),
                operation,
                pipeline_run_id,
                changed_fields_json,
                p.get("expediente_nombre"),
                p.get("workflow_descripcion"),
                p.get("region_nombre"),
                p.get("tipo_proyecto"),
                p.get("titular"),
                p.get("estado_proyecto"),
                p.get("actividad_actual"),
                p.get("etapa"),
                p.get("inversion_mm"),
            )
            params_list.append(params)

        try:
            self.db.execute_many(query, params_list, commit=True)
            logger.debug(f"Registrados {len(params_list)} cambios en historial ({operation})")
        except Exception as e:
            logger.warning(f"Error registrando historial: {e}")

    def _proyecto_to_params_for_update(self, p: dict[str, Any]) -> tuple:
        """Convertir proyecto a tupla de parámetros para UPDATE (sin expediente_id)."""
        return (
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

    def _proyecto_to_params(self, p: dict[str, Any]) -> tuple:
        """Convertir proyecto a tupla de parámetros (sin expediente_id al final)."""
        return (
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

    def insert_proyectos_bulk(self, proyectos: list[dict[str, Any]]) -> tuple[int, int]:
        """
        Insertar múltiples proyectos en bulk (legacy, usa upsert internamente).

        DEPRECADO: Usar upsert_proyectos_bulk() para obtener estadísticas detalladas.

        Args:
            proyectos: Lista de diccionarios con datos de proyectos parseados

        Returns:
            Tupla (num_insertados, num_duplicados)
        """
        stats = self.upsert_proyectos_bulk(proyectos)
        return stats["nuevos"], stats["actualizados"] + stats["sin_cambios"]

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

    # =========================================================================
    # Pipeline Runs - Tracking de ejecuciones
    # =========================================================================

    def start_pipeline_run(self) -> int:
        """
        Registrar inicio de una nueva ejecución del pipeline.

        Returns:
            ID del pipeline_run creado
        """
        query = """
            INSERT INTO pipeline_runs (started_at, status)
            VALUES (NOW(), 'running')
        """
        run_id = self.db.insert_and_get_id(query, ())
        logger.info(f"Pipeline run iniciado con ID: {run_id}")
        return run_id

    def finish_pipeline_run(
        self,
        run_id: int,
        status: str,
        stats: dict[str, int],
        error_message: str | None = None
    ) -> None:
        """
        Registrar fin de una ejecución del pipeline.

        Args:
            run_id: ID del pipeline_run
            status: 'completed' o 'failed'
            stats: Diccionario con estadísticas {nuevos, actualizados, sin_cambios, total}
            error_message: Mensaje de error si falló
        """
        query = """
            UPDATE pipeline_runs SET
                finished_at = NOW(),
                status = %s,
                proyectos_nuevos = %s,
                proyectos_actualizados = %s,
                proyectos_sin_cambios = %s,
                total_procesados = %s,
                error_message = %s
            WHERE id = %s
        """
        params = (
            status,
            stats.get("nuevos", 0),
            stats.get("actualizados", 0),
            stats.get("sin_cambios", 0),
            stats.get("total", 0),
            error_message,
            run_id
        )
        self.db.execute_query(query, params, commit=True)
        logger.info(f"Pipeline run {run_id} finalizado con status: {status}")

    def get_last_successful_run(self) -> dict | None:
        """
        Obtener la última ejecución exitosa del pipeline.

        Returns:
            Dict con datos de la última corrida exitosa, o None
        """
        query = """
            SELECT * FROM pipeline_runs
            WHERE status = 'completed'
            ORDER BY started_at DESC
            LIMIT 1
        """
        return self.db.fetch_one(query, dictionary=True)

    def get_delta_since_last_run(self) -> dict[str, Any]:
        """
        Obtener estadísticas del delta desde la última corrida exitosa.

        Returns:
            Dict con {nuevos, actualizados, ultima_corrida, proyectos_nuevos, proyectos_actualizados}
        """
        last_run = self.get_last_successful_run()

        if not last_run:
            # Primera corrida - todo es nuevo
            total = self.db.fetch_one("SELECT COUNT(*) as total FROM proyectos", dictionary=True)
            return {
                "ultima_corrida": None,
                "nuevos": total["total"] if total else 0,
                "actualizados": 0,
                "proyectos_nuevos": [],
                "proyectos_actualizados": []
            }

        last_run_time = last_run["started_at"]

        # Proyectos nuevos (created_at >= ultima corrida)
        nuevos_query = """
            SELECT expediente_id, expediente_nombre, workflow_descripcion,
                   region_nombre, titular, estado_proyecto, created_at
            FROM proyectos
            WHERE created_at >= %s
            ORDER BY created_at DESC
        """
        nuevos = self.db.fetch_all(nuevos_query, params=(last_run_time,), dictionary=True)

        # Proyectos actualizados (updated_at >= ultima corrida)
        actualizados_query = """
            SELECT expediente_id, expediente_nombre, workflow_descripcion,
                   region_nombre, titular, estado_proyecto, updated_at
            FROM proyectos
            WHERE updated_at >= %s
            ORDER BY updated_at DESC
        """
        actualizados = self.db.fetch_all(actualizados_query, params=(last_run_time,), dictionary=True)

        return {
            "ultima_corrida": last_run_time,
            "nuevos": len(nuevos),
            "actualizados": len(actualizados),
            "proyectos_nuevos": nuevos,
            "proyectos_actualizados": actualizados
        }

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
