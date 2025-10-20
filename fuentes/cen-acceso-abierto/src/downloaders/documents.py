"""
Descargador de documentos desde URLs remotas.

Este módulo maneja la descarga de archivos (PDF, XLSX, etc.) desde URLs remotas
(S3, HTTP, etc.) hacia almacenamiento local, con tracking en base de datos.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
import httpx
from datetime import datetime

from src.settings import Settings

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """
    Gestor de descarga de documentos desde URLs remotas.

    Descarga archivos desde `documentos.ruta_s3` y los guarda localmente en:
    downloads/{solicitud_id}/{filename}

    Actualiza la tabla `documentos` con información de descarga.
    """

    def __init__(
        self,
        settings: Settings,
        downloads_dir: str = "downloads",
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Inicializa el descargador de documentos.

        Args:
            settings: Configuración de la aplicación
            downloads_dir: Directorio base para guardar archivos descargados
            timeout: Timeout para descargas HTTP (segundos)
            max_retries: Número máximo de reintentos por archivo
        """
        self.settings = settings
        self.downloads_dir = Path(downloads_dir)
        self.timeout = timeout
        self.max_retries = max_retries

        # Crear directorio de descargas si no existe
        self.downloads_dir.mkdir(exist_ok=True, parents=True)

        # Cliente HTTP configurado para descargas
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        logger.info(f"📁 DocumentDownloader inicializado: {self.downloads_dir.absolute()}")

    def _get_presigned_url(self, ruta_s3: str, filename: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Obtiene una URL pre-firmada desde el endpoint del CEN.

        El CEN requiere llamar a un endpoint para obtener URLs S3 pre-firmadas
        que expiran después de 30 segundos.

        Args:
            ruta_s3: Ruta del archivo en S3 (ej: empresa-1/proyecto-2819/...)
            filename: Nombre del archivo para descarga

        Returns:
            Tupla (success, presigned_url, error_message)
        """
        presigned_endpoint = "https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/documentos/s3"

        try:
            response = self.client.get(
                presigned_endpoint,
                params={"key": ruta_s3, "download": filename}
            )
            response.raise_for_status()

            data = response.json()
            presigned_url = data.get("url_archivo")

            if not presigned_url:
                return False, None, "Respuesta del servidor no contiene 'url_archivo'"

            logger.debug(f"✅ URL pre-firmada obtenida para: {filename}")
            return True, presigned_url, None

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code} al obtener URL pre-firmada"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg

        except httpx.RequestError as e:
            error_msg = f"Error de conexión al obtener URL pre-firmada: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg

        except Exception as e:
            error_msg = f"Error inesperado al obtener URL pre-firmada: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return False, None, error_msg

    def download_document(
        self,
        ruta_s3: str,
        solicitud_id: int,
        documento_id: int,
        filename: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Descarga un documento individual desde S3 usando URL pre-firmada.

        Primero obtiene una URL pre-firmada del endpoint del CEN, luego
        descarga el archivo desde S3.

        Args:
            ruta_s3: Ruta del archivo en S3 (documentos.ruta_s3)
            solicitud_id: ID de la solicitud (para organizar directorios)
            documento_id: ID del documento en la base de datos
            filename: Nombre del archivo

        Returns:
            Tupla (success, local_path, error_message):
                - success: True si la descarga fue exitosa
                - local_path: Ruta local del archivo descargado (relativa a downloads/)
                - error_message: Mensaje de error si falló
        """

        # Crear directorio para esta solicitud
        solicitud_dir = self.downloads_dir / str(solicitud_id)
        solicitud_dir.mkdir(exist_ok=True, parents=True)

        # Ruta completa del archivo
        file_path = solicitud_dir / filename

        # Verificar si ya existe
        if file_path.exists():
            logger.debug(f"⏭️  Archivo ya existe: {file_path}")
            relative_path = str(file_path.relative_to(self.downloads_dir))
            return True, relative_path, None

        # PASO 1: Obtener URL pre-firmada del CEN
        logger.info(f"🔑 Obteniendo URL pre-firmada para: {filename}")
        success, presigned_url, error = self._get_presigned_url(ruta_s3, filename)

        if not success:
            return False, None, f"No se pudo obtener URL pre-firmada: {error}"

        # PASO 2: Descargar archivo desde S3 usando URL pre-firmada
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"⬇️  Descargando [{attempt}/{self.max_retries}]: {filename}")

                response = self.client.get(presigned_url)
                response.raise_for_status()

                # Guardar contenido a archivo
                file_path.write_bytes(response.content)

                logger.info(f"✅ Descargado: {file_path} ({len(response.content):,} bytes)")

                # Retornar ruta relativa
                relative_path = str(file_path.relative_to(self.downloads_dir))
                return True, relative_path, None

            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP {e.response.status_code} al descargar desde S3"
                logger.error(f"❌ {error_msg}")

                # No reintentar si es 404 o 403
                if e.response.status_code in [404, 403, 401]:
                    return False, None, error_msg

                # Reintentar para otros errores HTTP
                if attempt < self.max_retries:
                    logger.warning(f"🔄 Reintentando descarga (intento {attempt + 1})...")
                    # Obtener nueva URL pre-firmada (la anterior podría haber expirado)
                    success, presigned_url, error = self._get_presigned_url(ruta_s3, filename)
                    if not success:
                        return False, None, f"No se pudo renovar URL pre-firmada: {error}"
                    continue

                return False, None, error_msg

            except httpx.RequestError as e:
                error_msg = f"Error de conexión al descargar desde S3: {str(e)}"
                logger.error(f"❌ {error_msg}")

                if attempt < self.max_retries:
                    logger.warning(f"🔄 Reintentando descarga (intento {attempt + 1})...")
                    # Obtener nueva URL pre-firmada
                    success, presigned_url, error = self._get_presigned_url(ruta_s3, filename)
                    if not success:
                        return False, None, f"No se pudo renovar URL pre-firmada: {error}"
                    continue

                return False, None, error_msg

            except Exception as e:
                error_msg = f"Error inesperado: {str(e)}"
                logger.error(f"❌ {error_msg}", exc_info=True)
                return False, None, error_msg

        # Si llegamos aquí, se agotaron los reintentos
        return False, None, f"Se agotaron {self.max_retries} reintentos"

    def _extract_filename(self, url: str) -> str:
        """
        Extrae el nombre del archivo desde la URL.

        Args:
            url: URL del documento

        Returns:
            Nombre del archivo extraído
        """
        # Obtener la última parte de la URL
        filename = url.split("/")[-1].split("?")[0]

        # Si no tiene extensión, usar .bin por defecto
        if "." not in filename:
            filename += ".bin"

        return filename

    def close(self):
        """Cierra el cliente HTTP."""
        self.client.close()
        logger.debug("🔒 Cliente HTTP cerrado")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
