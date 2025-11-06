"""
Extractor de texto de PDFs.

Descarga PDFs y extrae el texto usando PyPDF2.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.core.http_client import HTTPClient

logger = logging.getLogger(__name__)


class PDFTextExtractor:
    """
    Extractor de texto de archivos PDF.
    """

    def __init__(self, http_client: HTTPClient):
        """
        Inicializar extractor.

        Args:
            http_client: Cliente HTTP para descargas
        """
        self.http_client = http_client

    def extract_text_from_url(self, pdf_url: str, id_documento: int) -> dict[str, Any]:
        """
        Descargar PDF y extraer texto.

        Args:
            pdf_url: URL del PDF
            id_documento: ID del documento

        Returns:
            Diccionario con texto extraído o error
        """
        try:
            logger.info(f"Descargando PDF: {pdf_url}")

            # Descargar PDF usando httpx directamente para obtener bytes
            import httpx

            response = httpx.get(
                pdf_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30.0,
                follow_redirects=True
            )

            status_code = response.status_code
            pdf_bytes = response.content
            error = None if status_code == 200 else f"HTTP {status_code}"

            if error or status_code != 200:
                return {
                    "id_documento": id_documento,
                    "pdf_url": pdf_url,
                    "status_code": status_code,
                    "error_message": error or f"HTTP {status_code}",
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                }

            if not pdf_bytes or len(pdf_bytes) < 100:
                return {
                    "id_documento": id_documento,
                    "pdf_url": pdf_url,
                    "status_code": status_code,
                    "error_message": "PDF vacío o muy pequeño",
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                }

            # Extraer texto usando pdfplumber
            try:
                import io
                import pdfplumber

                pdf_file = io.BytesIO(pdf_bytes)

                # Extraer texto de todas las páginas
                text_parts = []
                num_pages = 0

                with pdfplumber.open(pdf_file) as pdf:
                    num_pages = len(pdf.pages)

                    for page_num, page in enumerate(pdf.pages, 1):
                        try:
                            text = page.extract_text()
                            if text:
                                text_parts.append(text)
                        except Exception as e:
                            logger.warning(f"Error extrayendo página {page_num} de documento {id_documento}: {e}")
                            continue

                full_text = "\n\n".join(text_parts)

                if not full_text or len(full_text.strip()) < 100:
                    return {
                        "id_documento": id_documento,
                        "pdf_url": pdf_url,
                        "status_code": status_code,
                        "error_message": "No se pudo extraer texto del PDF (puede ser imagen escaneada)",
                        "pdf_bytes": len(pdf_bytes),
                        "num_pages": num_pages,
                        "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    }

                logger.info(f"Texto extraído: {len(full_text)} caracteres, {num_pages} páginas")

                return {
                    "id_documento": id_documento,
                    "pdf_url": pdf_url,
                    "status_code": status_code,
                    "pdf_text": full_text,
                    "pdf_bytes": len(pdf_bytes),
                    "num_pages": num_pages,
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                }

            except Exception as e:
                logger.error(f"Error parseando PDF de documento {id_documento}: {e}")
                return {
                    "id_documento": id_documento,
                    "pdf_url": pdf_url,
                    "status_code": status_code,
                    "error_message": f"Error parseando PDF: {str(e)}",
                    "pdf_bytes": len(pdf_bytes) if pdf_bytes else 0,
                    "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                }

        except Exception as e:
            logger.error(f"Error extrayendo texto de PDF {id_documento}: {e}", exc_info=True)
            return {
                "id_documento": id_documento,
                "pdf_url": pdf_url,
                "status_code": 0,
                "error_message": f"Excepción: {str(e)}",
                "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            }

    def extract_batch(self, documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extraer texto de múltiples PDFs.

        Args:
            documentos: Lista de diccionarios con id_documento y pdf_url

        Returns:
            Lista de resultados
        """
        results = []

        for i, doc in enumerate(documentos, 1):
            id_documento = doc.get("id_documento")
            pdf_url = doc.get("pdf_url")

            if not pdf_url:
                logger.warning(f"Documento {id_documento} no tiene pdf_url")
                continue

            try:
                result = self.extract_text_from_url(pdf_url, id_documento)
                results.append(result)

                if i % 10 == 0:
                    logger.info(f"Procesados {i}/{len(documentos)} PDFs")

            except Exception as e:
                logger.error(f"Error procesando documento {id_documento}: {e}")
                results.append({
                    "id_documento": id_documento,
                    "pdf_url": pdf_url,
                    "error_message": str(e),
                })

        logger.info(f"Extracción completada: {len(results)} PDFs procesados")
        return results


def get_pdf_text_extractor(http_client: HTTPClient) -> PDFTextExtractor:
    """
    Factory function para crear extractor de PDFs.

    Args:
        http_client: Cliente HTTP

    Returns:
        Instancia de PDFTextExtractor
    """
    return PDFTextExtractor(http_client)
