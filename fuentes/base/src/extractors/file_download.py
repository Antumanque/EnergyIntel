"""
Extractor para descarga de archivos.

Este módulo provee funcionalidad para descargar archivos (PDF, XLSX, CSV, etc.)
desde URLs o servicios de almacenamiento.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.extractors.base import BaseExtractor
from src.settings import Settings

logger = logging.getLogger(__name__)


class FileDownloadExtractor(BaseExtractor):
    """
    Extractor para descarga de archivos.

    Este extractor descarga archivos desde URLs y los guarda localmente,
    retornando la ruta del archivo descargado.
    """

    def __init__(
        self,
        settings: Settings,
        urls: list[str] | None = None,
        download_dir: str | None = None,
        file_names: list[str] | None = None,
    ):
        """
        Inicializar el extractor de descarga de archivos.

        Args:
            settings: Settings de aplicación
            urls: Lista opcional de URLs de archivos a descargar (usa settings.file_urls si None)
            download_dir: Directorio opcional para guardar archivos (usa settings.download_dir si None)
            file_names: Lista opcional de nombres de archivo custom (debe coincidir con len(urls))
        """
        super().__init__(settings)
        self.urls = urls or settings.file_urls
        self.download_dir = Path(download_dir or settings.download_dir)
        self.file_names = file_names or []

        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def extract(self) -> list[dict[str, Any]]:
        """
        Descargar archivos desde las URLs configuradas.

        Returns:
            Lista de diccionarios con los datos de descarga
        """
        if not self.urls:
            logger.warning("No file URLs configured for download")
            return []

        logger.info(f"Starting file download for {len(self.urls)} file(s)")

        self.results = []

        for i, url in enumerate(self.urls):
            # Use custom file name if provided, else extract from URL
            file_name = (
                self.file_names[i] if i < len(self.file_names) else self._get_filename_from_url(url)
            )

            result = self._download_single_file(url, file_name)
            self.results.append(result)

        self.log_summary()
        return self.results

    def _download_single_file(self, url: str, file_name: str) -> dict[str, Any]:
        """
        Descargar un solo archivo.

        Args:
            url: URL del archivo
            file_name: Nombre para guardar el archivo

        Returns:
            Diccionario con el resultado de la descarga
        """
        logger.info(f"Downloading: {url} -> {file_name}")

        file_path = self.download_dir / file_name
        error_message = None
        status_code = 0
        data = None

        try:
            # Download the file
            with httpx.Client(timeout=self.settings.request_timeout) as client:
                response = client.get(url, follow_redirects=True)
                status_code = response.status_code

                if response.is_success:
                    # Save file to disk
                    with open(file_path, "wb") as f:
                        f.write(response.content)

                    # Store metadata as data
                    data = {
                        "file_path": str(file_path),
                        "file_name": file_name,
                        "file_size_bytes": len(response.content),
                        "content_type": response.headers.get("content-type"),
                    }

                    logger.info(
                        f"Successfully downloaded {file_name} "
                        f"({len(response.content)} bytes)"
                    )
                else:
                    error_message = (
                        f"HTTP {response.status_code}: {response.reason_phrase}"
                    )
                    logger.error(f"Failed to download {url}: {error_message}")

        except httpx.TimeoutException as e:
            error_message = f"Download timeout after {self.settings.request_timeout} seconds"
            logger.error(f"Timeout downloading {url}: {e}")

        except httpx.RequestError as e:
            error_message = f"Request error: {str(e)}"
            logger.error(f"Request error downloading {url}: {e}")

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error downloading {url}: {e}", exc_info=True)

        result = {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        return result

    def _get_filename_from_url(self, url: str) -> str:
        """
        Extraer nombre de archivo desde una URL.

        Args:
            url: URL del archivo

        Returns:
            Nombre del archivo
        """
        # Get the last part of the URL path
        path = url.split("?")[0]  # Remove query params
        file_name = path.split("/")[-1]

        # If empty or looks like a directory, generate a name
        if not file_name or "." not in file_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"downloaded_file_{timestamp}"

        return file_name
