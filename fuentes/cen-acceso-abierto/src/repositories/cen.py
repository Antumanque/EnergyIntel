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

    def get_documentos_pendientes_descarga(
        self,
        tipo_documento: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene documentos que aún no han sido descargados.

        Args:
            tipo_documento: Filtrar por tipo específico (opcional)
            limit: Limitar número de resultados (opcional)

        Returns:
            Lista de documentos pendientes de descarga
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor(dictionary=True)

                query = """
                    SELECT id, solicitud_id, nombre, ruta_s3, tipo_documento
                    FROM documentos
                    WHERE downloaded = 0
                    AND deleted = 0
                    AND visible = 1
                    AND ruta_s3 IS NOT NULL
                    AND ruta_s3 != ''
                """

                params = []
                if tipo_documento:
                    query += " AND tipo_documento = %s"
                    params.append(tipo_documento)

                query += " ORDER BY id"

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                documentos = cursor.fetchall()

                logger.info(f"📊 {len(documentos)} documentos pendientes de descarga")
                return documentos

        except Error as e:
            logger.error(f"Error al obtener documentos pendientes: {e}")
            return []

    def mark_documento_downloaded(
        self,
        documento_id: int,
        local_path: str,
        download_error: Optional[str] = None
    ) -> None:
        """
        Marca un documento como descargado (o con error).

        Args:
            documento_id: ID del documento
            local_path: Ruta local donde se guardó el archivo
            download_error: Mensaje de error si la descarga falló (None si exitoso)
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                if download_error:
                    # Descarga falló - registrar error
                    update_sql = """
                        UPDATE documentos
                        SET downloaded = 0,
                            local_path = NULL,
                            download_error = %s
                        WHERE id = %s
                    """
                    cursor.execute(update_sql, (download_error, documento_id))
                    logger.warning(f"⚠️  Documento {documento_id} - Error: {download_error}")
                else:
                    # Descarga exitosa
                    update_sql = """
                        UPDATE documentos
                        SET downloaded = 1,
                            downloaded_at = NOW(),
                            local_path = %s,
                            download_error = NULL
                        WHERE id = %s
                    """
                    cursor.execute(update_sql, (local_path, documento_id))
                    logger.debug(f"✅ Documento {documento_id} marcado como descargado")

                conn.commit()

        except Error as e:
            logger.error(f"❌ Error al marcar documento como descargado: {e}", exc_info=True)
            raise

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

                # Documentos descargados
                cursor.execute("SELECT COUNT(*) FROM documentos WHERE downloaded = 1")
                docs_descargados = cursor.fetchone()[0]

                # Total raw API responses
                cursor.execute("SELECT COUNT(*) FROM raw_api_data")
                total_raw_responses = cursor.fetchone()[0]

                return {
                    "total_solicitudes": total_solicitudes,
                    "total_documentos": total_documentos,
                    "docs_suctd": docs_suctd,
                    "docs_sac": docs_sac,
                    "docs_fehaciente": docs_fehaciente,
                    "docs_descargados": docs_descargados,
                    "total_raw_responses": total_raw_responses,
                }
        except Error as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}


    def insert_formulario_parseado(
        self,
        documento_id: int,
        tipo_formulario: str,
        formato_archivo: str,
        parsing_exitoso: bool,
        parser_version: str,
        parsing_error: Optional[str] = None,
        pdf_producer: Optional[str] = None,
        pdf_author: Optional[str] = None,
        pdf_title: Optional[str] = None,
        pdf_creation_date: Optional[str] = None
    ) -> Optional[int]:
        """
        Registra un intento de parsing de formulario (exitoso o fallido).

        Este método implementa el tracking granular de cada parsing attempt.
        Si el parsing falla, el error se registra para debugging posterior.

        Args:
            documento_id: ID del documento que se parseó
            tipo_formulario: SAC, SUCTD o FEHACIENTE
            formato_archivo: PDF, XLSX o XLS
            parsing_exitoso: True si el parsing fue exitoso
            parser_version: Versión del parser usado (ej: "1.0.0")
            parsing_error: Mensaje de error si parsing_exitoso=False
            pdf_producer: Producer del PDF (ej: "Microsoft: Print To PDF")
            pdf_author: Author del PDF
            pdf_title: Title del PDF
            pdf_creation_date: CreationDate del PDF en formato MySQL DATETIME

        Returns:
            ID del registro insertado, o None si ya existe
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                # Verificar si ya existe un registro de parsing exitoso
                cursor.execute("""
                    SELECT id FROM formularios_parseados
                    WHERE documento_id = %s AND parsing_exitoso = 1
                """, (documento_id,))

                existing = cursor.fetchone()
                if existing:
                    logger.info(f"✅ Documento {documento_id} ya fue parseado exitosamente (skipped)")
                    return existing[0]

                # Insertar nuevo registro de parsing
                insert_sql = """
                    INSERT INTO formularios_parseados (
                        documento_id, tipo_formulario, formato_archivo,
                        parsing_exitoso, parsing_error, parser_version,
                        pdf_producer, pdf_author, pdf_title, pdf_creation_date,
                        parsed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        parsing_exitoso = VALUES(parsing_exitoso),
                        parsing_error = VALUES(parsing_error),
                        parser_version = VALUES(parser_version),
                        pdf_producer = VALUES(pdf_producer),
                        pdf_author = VALUES(pdf_author),
                        pdf_title = VALUES(pdf_title),
                        pdf_creation_date = VALUES(pdf_creation_date),
                        parsed_at = NOW()
                """

                cursor.execute(insert_sql, (
                    documento_id, tipo_formulario, formato_archivo,
                    parsing_exitoso, parsing_error, parser_version,
                    pdf_producer, pdf_author, pdf_title, pdf_creation_date
                ))
                conn.commit()

                formulario_parseado_id = cursor.lastrowid

                if parsing_exitoso:
                    logger.debug(f"✅ Parsing exitoso registrado: documento {documento_id}")
                else:
                    logger.warning(f"⚠️  Parsing fallido registrado: documento {documento_id} - {parsing_error}")

                return formulario_parseado_id

        except Error as e:
            logger.error(f"❌ Error al registrar parsing: {e}", exc_info=True)
            raise

    def insert_formulario_sac_parsed(
        self,
        formulario_parseado_id: int,
        documento_id: int,
        solicitud_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """
        Inserta datos parseados de un Formulario SAC.

        Este método valida campos mínimos antes de insertar para asegurar
        calidad de datos. Si faltan campos críticos, el insert falla.

        Args:
            formulario_parseado_id: FK a formularios_parseados.id
            documento_id: FK a documentos.id
            solicitud_id: FK a solicitudes.id
            data: Diccionario con campos parseados del formulario

        Returns:
            True si el insert fue exitoso, False en caso contrario

        Raises:
            ValueError: Si faltan campos críticos mínimos
        """
        # Validación: Verificar campos críticos mínimos
        # Estos campos son ESENCIALES para considerar el parsing como válido
        required_fields = ["razon_social", "rut", "nombre_proyecto"]
        missing_fields = [f for f in required_fields if not data.get(f)]

        if missing_fields:
            error_msg = f"Faltan campos críticos: {', '.join(missing_fields)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        try:
            with self.connection() as conn:
                cursor = conn.cursor()

                insert_sql = """
                    INSERT INTO formularios_sac_parsed (
                        formulario_parseado_id, documento_id, solicitud_id,
                        razon_social, rut, giro, domicilio_legal,
                        representante_legal_nombre, representante_legal_email, representante_legal_telefono,
                        coordinador_proyecto_1_nombre, coordinador_proyecto_1_email, coordinador_proyecto_1_telefono,
                        coordinador_proyecto_2_nombre, coordinador_proyecto_2_email, coordinador_proyecto_2_telefono,
                        coordinador_proyecto_3_nombre, coordinador_proyecto_3_email, coordinador_proyecto_3_telefono,
                        nombre_proyecto, tipo_proyecto, tecnologia, potencia_nominal_mw,
                        consumo_propio_mw, factor_potencia,
                        proyecto_coordenadas_utm_huso, proyecto_coordenadas_utm_este, proyecto_coordenadas_utm_norte,
                        proyecto_comuna, proyecto_region,
                        nombre_subestacion, nivel_tension_kv, caracter_conexion,
                        fecha_estimada_construccion, fecha_estimada_interconexion,
                        conexion_coordenadas_utm_huso, conexion_coordenadas_utm_este, conexion_coordenadas_utm_norte,
                        conexion_comuna, conexion_region,
                        created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        NOW()
                    )
                """

                cursor.execute(insert_sql, (
                    formulario_parseado_id, documento_id, solicitud_id,
                    # Antecedentes Generales del Solicitante
                    data.get("razon_social"),
                    data.get("rut"),
                    data.get("giro"),
                    data.get("domicilio_legal"),
                    # Representante Legal
                    data.get("representante_legal_nombre"),
                    data.get("representante_legal_email"),
                    data.get("representante_legal_telefono"),
                    # Coordinadores de Proyecto
                    data.get("coordinador_proyecto_1_nombre"),
                    data.get("coordinador_proyecto_1_email"),
                    data.get("coordinador_proyecto_1_telefono"),
                    data.get("coordinador_proyecto_2_nombre"),
                    data.get("coordinador_proyecto_2_email"),
                    data.get("coordinador_proyecto_2_telefono"),
                    data.get("coordinador_proyecto_3_nombre"),
                    data.get("coordinador_proyecto_3_email"),
                    data.get("coordinador_proyecto_3_telefono"),
                    # Antecedentes del Proyecto
                    data.get("nombre_proyecto"),
                    data.get("tipo_proyecto"),
                    data.get("tecnologia"),
                    data.get("potencia_nominal_mw"),
                    data.get("consumo_propio_mw"),
                    data.get("factor_potencia"),
                    # Ubicación Geográfica del Proyecto
                    data.get("proyecto_coordenadas_utm_huso"),
                    data.get("proyecto_coordenadas_utm_este"),
                    data.get("proyecto_coordenadas_utm_norte"),
                    data.get("proyecto_comuna"),
                    data.get("proyecto_region"),
                    # Antecedentes del Punto de Conexión
                    data.get("nombre_subestacion"),
                    data.get("nivel_tension_kv"),
                    data.get("caracter_conexion"),
                    data.get("fecha_estimada_construccion"),
                    data.get("fecha_estimada_interconexion"),
                    # Ubicación Geográfica del Punto de Conexión
                    data.get("conexion_coordenadas_utm_huso"),
                    data.get("conexion_coordenadas_utm_este"),
                    data.get("conexion_coordenadas_utm_norte"),
                    data.get("conexion_comuna"),
                    data.get("conexion_region"),
                ))

                conn.commit()
                logger.info(f"✅ Formulario SAC parseado insertado: documento {documento_id}")
                return True

        except Error as e:
            logger.error(f"❌ Error al insertar formulario SAC parseado: {e}", exc_info=True)
            return False

    def parse_and_store_sac_document(
        self,
        documento_id: int,
        solicitud_id: int,
        local_path: str,
        formato_archivo: str = "PDF",
        parser_version: str = "1.0.0"
    ) -> bool:
        """
        Parsea un documento SAC (PDF o XLSX) y guarda los datos en una TRANSACCIÓN.

        Este es el método de alto nivel que orquesta todo el proceso:
        1. Parsea el archivo con SACPDFParser o SACXLSXParser (según formato)
        2. Valida campos mínimos
        3. Inserta en formularios_parseados + formularios_sac_parsed en UNA transacción
        4. Si algo falla, hace rollback automático

        Args:
            documento_id: ID del documento a parsear
            solicitud_id: ID de la solicitud asociada
            local_path: Ruta local del archivo (PDF o XLSX)
            formato_archivo: Formato del archivo ("PDF" o "XLSX", default: "PDF")
            parser_version: Versión del parser (default: "1.0.0")

        Returns:
            True si el parsing y storage fue exitoso, False en caso contrario
        """
        from pathlib import Path

        try:
            # Paso 1: Parsear el archivo (PDF o XLSX)
            logger.info(f"📄 Parseando documento {documento_id} ({formato_archivo}): {local_path}")

            # Detectar formato si no se especifica (basado en extensión)
            if formato_archivo == "PDF":
                from src.parsers.pdf_sac import parse_sac_pdf
                parsed_data = parse_sac_pdf(local_path)
            elif formato_archivo in ("XLSX", "XLS"):
                from src.parsers.xlsx_sac import SACXLSXParser
                parser = SACXLSXParser()
                parsed_data = parser.parse(local_path)
            else:
                raise ValueError(f"Formato no soportado: {formato_archivo}")

            # Paso 2: Validar campos mínimos
            required_fields = ["razon_social", "rut", "nombre_proyecto"]
            missing_fields = [f for f in required_fields if not parsed_data.get(f)]

            if missing_fields:
                error_msg = f"Campos críticos faltantes: {', '.join(missing_fields)}"
                logger.warning(f"⚠️  {error_msg}")

                # Registrar parsing FALLIDO
                self.insert_formulario_parseado(
                    documento_id=documento_id,
                    tipo_formulario="SAC",
                    formato_archivo=formato_archivo,
                    parsing_exitoso=False,
                    parser_version=parser_version,
                    parsing_error=error_msg
                )
                return False

            # Paso 3: Insertar en ambas tablas (TRANSACCIÓN)
            with self.connection() as conn:
                cursor = conn.cursor()

                try:
                    # 3.1: Insertar tracking en formularios_parseados (con metadata)
                    cursor.execute("""
                        INSERT INTO formularios_parseados (
                            documento_id, tipo_formulario, formato_archivo,
                            parsing_exitoso, parser_version,
                            pdf_producer, pdf_author, pdf_title, pdf_creation_date,
                            parsed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            parsing_exitoso = VALUES(parsing_exitoso),
                            parser_version = VALUES(parser_version),
                            pdf_producer = VALUES(pdf_producer),
                            pdf_author = VALUES(pdf_author),
                            pdf_title = VALUES(pdf_title),
                            pdf_creation_date = VALUES(pdf_creation_date),
                            parsed_at = NOW()
                    """, (
                        documento_id, "SAC", formato_archivo, True, parser_version,
                        parsed_data.get('pdf_producer'),
                        parsed_data.get('pdf_author'),
                        parsed_data.get('pdf_title'),
                        parsed_data.get('pdf_creation_date')
                    ))

                    formulario_parseado_id = cursor.lastrowid

                    # 3.2: Insertar datos parseados en formularios_sac_parsed
                    cursor.execute("""
                        INSERT INTO formularios_sac_parsed (
                            formulario_parseado_id, documento_id, solicitud_id,
                            razon_social, rut, giro, domicilio_legal,
                            representante_legal_nombre, representante_legal_email, representante_legal_telefono,
                            coordinador_proyecto_1_nombre, coordinador_proyecto_1_email, coordinador_proyecto_1_telefono,
                            coordinador_proyecto_2_nombre, coordinador_proyecto_2_email, coordinador_proyecto_2_telefono,
                            coordinador_proyecto_3_nombre, coordinador_proyecto_3_email, coordinador_proyecto_3_telefono,
                            nombre_proyecto, tipo_proyecto, tecnologia, potencia_nominal_mw,
                            consumo_propio_mw, factor_potencia,
                            proyecto_coordenadas_utm_huso, proyecto_coordenadas_utm_este, proyecto_coordenadas_utm_norte,
                            proyecto_comuna, proyecto_region,
                            nombre_subestacion, nivel_tension_kv, caracter_conexion,
                            fecha_estimada_construccion, fecha_estimada_interconexion,
                            conexion_coordenadas_utm_huso, conexion_coordenadas_utm_este, conexion_coordenadas_utm_norte,
                            conexion_comuna, conexion_region,
                            created_at
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            NOW()
                        )
                    """, (
                        formulario_parseado_id, documento_id, solicitud_id,
                        parsed_data.get("razon_social"),
                        parsed_data.get("rut"),
                        parsed_data.get("giro"),
                        parsed_data.get("domicilio_legal"),
                        parsed_data.get("representante_legal_nombre"),
                        parsed_data.get("representante_legal_email"),
                        parsed_data.get("representante_legal_telefono"),
                        parsed_data.get("coordinador_proyecto_1_nombre"),
                        parsed_data.get("coordinador_proyecto_1_email"),
                        parsed_data.get("coordinador_proyecto_1_telefono"),
                        parsed_data.get("coordinador_proyecto_2_nombre"),
                        parsed_data.get("coordinador_proyecto_2_email"),
                        parsed_data.get("coordinador_proyecto_2_telefono"),
                        parsed_data.get("coordinador_proyecto_3_nombre"),
                        parsed_data.get("coordinador_proyecto_3_email"),
                        parsed_data.get("coordinador_proyecto_3_telefono"),
                        parsed_data.get("nombre_proyecto"),
                        parsed_data.get("tipo_proyecto"),
                        parsed_data.get("tecnologia"),
                        parsed_data.get("potencia_nominal_mw"),
                        parsed_data.get("consumo_propio_mw"),
                        parsed_data.get("factor_potencia"),
                        parsed_data.get("proyecto_coordenadas_utm_huso"),
                        parsed_data.get("proyecto_coordenadas_utm_este"),
                        parsed_data.get("proyecto_coordenadas_utm_norte"),
                        parsed_data.get("proyecto_comuna"),
                        parsed_data.get("proyecto_region"),
                        parsed_data.get("nombre_subestacion"),
                        parsed_data.get("nivel_tension_kv"),
                        parsed_data.get("caracter_conexion"),
                        parsed_data.get("fecha_estimada_construccion"),
                        parsed_data.get("fecha_estimada_interconexion"),
                        parsed_data.get("conexion_coordenadas_utm_huso"),
                        parsed_data.get("conexion_coordenadas_utm_este"),
                        parsed_data.get("conexion_coordenadas_utm_norte"),
                        parsed_data.get("conexion_comuna"),
                        parsed_data.get("conexion_region"),
                    ))

                    # Commit de la transacción
                    conn.commit()
                    logger.info(f"✅ Documento {documento_id} parseado y almacenado exitosamente")
                    return True

                except Error as e:
                    # Rollback automático si algo falla
                    conn.rollback()
                    error_msg = f"Error en transacción: {str(e)}"
                    logger.error(f"❌ {error_msg}", exc_info=True)

                    # Registrar parsing FALLIDO
                    self.insert_formulario_parseado(
                        documento_id=documento_id,
                        tipo_formulario="SAC",
                        formato_archivo="PDF",
                        parsing_exitoso=False,
                        parser_version=parser_version,
                        parsing_error=error_msg
                    )
                    return False

        except Exception as e:
            error_msg = f"Error al parsear PDF: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)

            # Registrar parsing FALLIDO
            self.insert_formulario_parseado(
                documento_id=documento_id,
                tipo_formulario="SAC",
                formato_archivo="PDF",
                parsing_exitoso=False,
                parser_version=parser_version,
                parsing_error=error_msg
            )
            return False


def get_cen_db_manager() -> CENDatabaseManager:
    """
    Factory function para crear instancia del gestor de BD del CEN.

    Returns:
        Instancia de CENDatabaseManager con configuración cargada
    """
    settings = get_settings()
    return CENDatabaseManager(settings.get_db_config())
