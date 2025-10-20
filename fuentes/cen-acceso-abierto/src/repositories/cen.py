"""
Gestión de base de datos para solicitudes y documentos del CEN.

Este módulo extiende database.py con operaciones específicas para las tablas
solicitudes y documentos.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import Error

from src.settings import get_settings

logger = logging.getLogger(__name__)


def parse_iso_datetime(iso_string: Optional[str]) -> Optional[str]:
    """
    Convierte fecha ISO 8601 a formato MySQL DATETIME.

    Args:
        iso_string: Fecha en formato ISO (ej: '2025-10-15T17:22:32.000Z')

    Returns:
        Fecha en formato MySQL (ej: '2025-10-15 17:22:32') o None
    """
    if not iso_string or iso_string == 'null':
        return None

    try:
        # Parsear ISO 8601 y convertir a formato MySQL
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return None


def parse_iso_date(iso_string: Optional[str]) -> Optional[str]:
    """
    Convierte fecha ISO 8601 a formato MySQL DATE (solo fecha, sin hora).

    Args:
        iso_string: Fecha en formato ISO (ej: '2029-03-31T00:00:00.000Z')

    Returns:
        Fecha en formato MySQL (ej: '2029-03-31') o None
    """
    if not iso_string or iso_string == 'null':
        return None

    try:
        # Parsear ISO 8601 y extraer solo la fecha
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        return None


class CENDatabaseManager:
    """
    Gestor de base de datos para solicitudes y documentos del CEN.

    Maneja la conexión, creación de tablas y operaciones CRUD para
    las tablas solicitudes y documentos.
    """

    def __init__(self, db_config: Dict[str, Any]):
        """
        Inicializa el gestor de base de datos.

        Args:
            db_config: Diccionario con configuración de conexión a la BD
        """
        self.config = db_config

    @contextmanager
    def connection(self):
        """
        Context manager para conexiones a la base de datos.

        Asegura que las conexiones se cierren apropiadamente.
        """
        conn = None
        try:
            conn = mysql.connector.connect(**self.config)
            yield conn
        except Error as e:
            logger.error(f"Error de conexión a la base de datos: {e}", exc_info=True)
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def test_connection(self) -> bool:
        """
        Verifica que se pueda conectar a la base de datos.

        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                logger.info("✅ Conexión a la base de datos exitosa")
                return True
        except Error as e:
            logger.error(f"❌ Error al conectar a la base de datos: {e}")
            return False

    def create_tables(self) -> None:
        """
        Crea las tablas solicitudes y documentos si no existen.

        Lee el schema desde db/schema_solicitudes.sql y lo ejecuta.
        """
        try:
            # Leer el archivo SQL
            with open("db/schema_solicitudes.sql", "r", encoding="utf-8") as f:
                schema_sql = f.read()

            with self.connection() as conn:
                cursor = conn.cursor()

                # Ejecutar cada statement del schema
                # Separar por punto y coma, pero ignorar líneas vacías y comentarios
                statements = []
                current_statement = []

                for line in schema_sql.split("\n"):
                    # Ignorar comentarios y líneas vacías
                    stripped = line.strip()
                    if not stripped or stripped.startswith("--"):
                        continue

                    current_statement.append(line)

                    # Si la línea termina con ; es el fin del statement
                    if stripped.endswith(";"):
                        statements.append("\n".join(current_statement))
                        current_statement = []

                # Ejecutar cada statement
                for statement in statements:
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                        except Error as e:
                            # Ignorar errores de "table already exists" para CREATE TABLE
                            if "already exists" not in str(e).lower():
                                logger.warning(f"Advertencia al ejecutar statement: {e}")

                conn.commit()
                logger.info("✅ Tablas creadas/verificadas exitosamente")

        except FileNotFoundError:
            logger.error("❌ No se encontró el archivo db/schema_solicitudes.sql")
            raise
        except Error as e:
            logger.error(f"❌ Error al crear tablas: {e}", exc_info=True)
            raise

    def get_existing_solicitud_ids(self) -> set[int]:
        """
        Obtiene los IDs de solicitudes que ya existen en la base de datos.

        Returns:
            Set de IDs de solicitudes existentes
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM solicitudes")
                existing_ids = {row[0] for row in cursor.fetchall()}
                logger.info(f"📊 {len(existing_ids)} solicitudes existentes en la BD")
                return existing_ids
        except Error as e:
            logger.error(f"Error al obtener IDs de solicitudes existentes: {e}")
            return set()

    def insert_solicitudes_bulk(self, solicitudes: List[Dict[str, Any]]) -> int:
        """
        Inserta múltiples solicitudes en la base de datos (solo las nuevas).

        Implementa estrategia append-only: solo inserta registros nuevos,
        nunca actualiza ni elimina registros existentes.

        Args:
            solicitudes: Lista de diccionarios con datos de solicitudes

        Returns:
            Número de solicitudes insertadas
        """
        if not solicitudes:
            logger.info("No hay solicitudes para insertar")
            return 0

        # Obtener IDs existentes
        existing_ids = self.get_existing_solicitud_ids()

        # Filtrar solo las solicitudes NUEVAS
        new_solicitudes = [s for s in solicitudes if s.get("id") not in existing_ids]

        if not new_solicitudes:
            logger.info(f"✅ Todas las {len(solicitudes)} solicitudes ya existen (skipped)")
            return 0

        logger.info(
            f"📥 Insertando {len(new_solicitudes)} solicitudes nuevas "
            f"(skipped {len(solicitudes) - len(new_solicitudes)} duplicadas)"
        )

        # Normalizar fechas ISO a formato MySQL
        for solicitud in new_solicitudes:
            solicitud['create_date'] = parse_iso_datetime(solicitud.get('create_date'))
            solicitud['update_date'] = parse_iso_datetime(solicitud.get('update_date'))
            solicitud['deleted_at'] = parse_iso_datetime(solicitud.get('deleted_at'))
            solicitud['cancelled_at'] = parse_iso_datetime(solicitud.get('cancelled_at'))
            solicitud['fecha_estimada_conexion'] = parse_iso_date(solicitud.get('fecha_estimada_conexion'))

        # SQL de inserción
        insert_sql = """
        INSERT INTO solicitudes (
            id, tipo_solicitud_id, tipo_solicitud, estado_solicitud_id, estado_solicitud,
            create_date, update_date, proyecto_id, proyecto, rut_empresa, razon_social,
            tipo_tecnologia_nombre, potencia_nominal,
            comuna_id, comuna, provincia_id, provincia, region_id, region, lat, lng,
            nombre_se, nivel_tension, seccion_barra_conexion, pano_conexion, fecha_estimada_conexion,
            calificacion_id, calificacion_nombre, etapa_id, etapa, nup, cup,
            deleted_at, cancelled_at, fetched_at
        ) VALUES (
            %(id)s, %(tipo_solicitud_id)s, %(tipo_solicitud)s, %(estado_solicitud_id)s, %(estado_solicitud)s,
            %(create_date)s, %(update_date)s, %(proyecto_id)s, %(proyecto)s, %(rut_empresa)s, %(razon_social)s,
            %(tipo_tecnologia_nombre)s, %(potencia_nominal)s,
            %(comuna_id)s, %(comuna)s, %(provincia_id)s, %(provincia)s, %(region_id)s, %(region)s, %(lat)s, %(lng)s,
            %(nombre_se)s, %(nivel_tension)s, %(seccion_barra_conexion)s, %(pano_conexion)s, %(fecha_estimada_conexion)s,
            %(calificacion_id)s, %(calificacion_nombre)s, %(etapa_id)s, %(etapa)s, %(nup)s, %(cup)s,
            %(deleted_at)s, %(cancelled_at)s, NOW()
        )
        """

        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(insert_sql, new_solicitudes)
                conn.commit()
                inserted_count = cursor.rowcount
                logger.info(f"✅ {inserted_count} solicitudes insertadas exitosamente")
                return inserted_count
        except Error as e:
            logger.error(f"❌ Error al insertar solicitudes: {e}", exc_info=True)
            raise

    def get_existing_documento_ids(self) -> set[int]:
        """
        Obtiene los IDs de documentos que ya existen en la base de datos.

        Returns:
            Set de IDs de documentos existentes
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM documentos")
                existing_ids = {row[0] for row in cursor.fetchall()}
                logger.info(f"📊 {len(existing_ids)} documentos existentes en la BD")
                return existing_ids
        except Error as e:
            logger.error(f"Error al obtener IDs de documentos existentes: {e}")
            return set()

    def insert_documentos_bulk(self, documentos: List[Dict[str, Any]]) -> int:
        """
        Inserta múltiples documentos en la base de datos (solo los nuevos).

        Implementa estrategia append-only: solo inserta registros nuevos,
        nunca actualiza ni elimina registros existentes.

        Args:
            documentos: Lista de diccionarios con datos de documentos

        Returns:
            Número de documentos insertados
        """
        if not documentos:
            logger.info("No hay documentos para insertar")
            return 0

        # Obtener IDs existentes
        existing_ids = self.get_existing_documento_ids()

        # Filtrar solo los documentos NUEVOS
        new_documentos = [d for d in documentos if d.get("id") not in existing_ids]

        if not new_documentos:
            logger.info(f"✅ Todos los {len(documentos)} documentos ya existen (skipped)")
            return 0

        logger.info(
            f"📥 Insertando {len(new_documentos)} documentos nuevos "
            f"(skipped {len(documentos) - len(new_documentos)} duplicados)"
        )

        # Normalizar fechas ISO a formato MySQL
        for documento in new_documentos:
            documento['create_date'] = parse_iso_datetime(documento.get('create_date'))
            documento['update_date'] = parse_iso_datetime(documento.get('update_date'))

        # SQL de inserción
        insert_sql = """
        INSERT INTO documentos (
            id, solicitud_id, nombre, ruta_s3, tipo_documento_id, tipo_documento,
            empresa_id, razon_social, create_date, update_date,
            estado_solicitud_id, etapa_id, etapa, version_id, visible, deleted,
            fetched_at
        ) VALUES (
            %(id)s, %(solicitud_id)s, %(nombre)s, %(ruta_s3)s, %(tipo_documento_id)s, %(tipo_documento)s,
            %(empresa_id)s, %(razon_social)s, %(create_date)s, %(update_date)s,
            %(estado_solicitud_id)s, %(etapa_id)s, %(etapa)s, %(version_id)s, %(visible)s, %(deleted)s,
            NOW()
        )
        """

        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(insert_sql, new_documentos)
                conn.commit()
                inserted_count = cursor.rowcount
                logger.info(f"✅ {inserted_count} documentos insertados exitosamente")
                return inserted_count
        except Error as e:
            logger.error(f"❌ Error al insertar documentos: {e}", exc_info=True)
            raise

    def get_solicitudes_sin_documentos(self) -> List[int]:
        """
        Obtiene IDs de solicitudes que aún no tienen documentos extraídos.

        Returns:
            Lista de IDs de solicitudes sin documentos
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.id
                    FROM solicitudes s
                    LEFT JOIN documentos d ON s.id = d.solicitud_id
                    WHERE d.id IS NULL
                """)
                solicitud_ids = [row[0] for row in cursor.fetchall()]
                logger.info(f"📊 {len(solicitud_ids)} solicitudes sin documentos extraídos")
                return solicitud_ids
        except Error as e:
            logger.error(f"Error al obtener solicitudes sin documentos: {e}")
            return []

    def insert_raw_api_response(
        self, source_url: str, status_code: int,
        data: Optional[Any] = None, error_message: Optional[str] = None
    ) -> None:
        """
        Guarda la respuesta raw de la API en raw_api_data.

        Este método preserva el JSON original para audit trail y re-procesamiento.

        Args:
            source_url: URL que fue consultada
            status_code: Código HTTP de la respuesta
            data: Datos JSON de la respuesta (None si hubo error)
            error_message: Mensaje de error (None si fue exitoso)
        """
        import json

        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                # Convertir data a JSON string si no es None
                data_json = json.dumps(data) if data is not None else None

                insert_sql = """
                INSERT INTO raw_api_data (source_url, status_code, data, error_message, fetched_at)
                VALUES (%s, %s, %s, %s, NOW())
                """

                cursor.execute(insert_sql, (source_url, status_code, data_json, error_message))
                conn.commit()
                logger.debug(f"✅ Raw API response saved: {source_url} (status: {status_code})")

        except Error as e:
            logger.error(f"❌ Error al guardar raw API response: {e}", exc_info=True)
            # No propagamos el error para no romper el flujo principal

    def get_stats(self) -> Dict[str, int]:
        """
        Obtiene estadísticas de la base de datos.

        Returns:
            Diccionario con estadísticas
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                # Total solicitudes
                cursor.execute("SELECT COUNT(*) FROM solicitudes")
                total_solicitudes = cursor.fetchone()[0]

                # Total documentos
                cursor.execute("SELECT COUNT(*) FROM documentos")
                total_documentos = cursor.fetchone()[0]

                # Documentos SUCTD
                cursor.execute("""
                    SELECT COUNT(*) FROM documentos
                    WHERE tipo_documento = 'Formulario SUCTD' AND deleted = 0
                """)
                docs_suctd = cursor.fetchone()[0]

                # Documentos SAC
                cursor.execute("""
                    SELECT COUNT(*) FROM documentos
                    WHERE tipo_documento = 'Formulario SAC' AND deleted = 0
                """)
                docs_sac = cursor.fetchone()[0]

                # Documentos Fehaciente
                cursor.execute("""
                    SELECT COUNT(*) FROM documentos
                    WHERE tipo_documento = 'Formulario_proyecto_fehaciente' AND deleted = 0
                """)
                docs_fehaciente = cursor.fetchone()[0]

                # Total raw API responses
                cursor.execute("SELECT COUNT(*) FROM raw_api_data")
                total_raw_responses = cursor.fetchone()[0]

                return {
                    "total_solicitudes": total_solicitudes,
                    "total_documentos": total_documentos,
                    "docs_suctd": docs_suctd,
                    "docs_sac": docs_sac,
                    "docs_fehaciente": docs_fehaciente,
                    "total_raw_responses": total_raw_responses,
                }
        except Error as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}


def get_cen_db_manager() -> CENDatabaseManager:
    """
    Factory function para crear instancia del gestor de BD del CEN.

    Returns:
        Instancia de CENDatabaseManager con configuración cargada
    """
    settings = get_settings()
    return CENDatabaseManager(settings.get_db_config())
