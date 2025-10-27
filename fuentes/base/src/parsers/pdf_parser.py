"""
Parser para archivos PDF.

Este módulo provee funcionalidad básica para extraer texto y tablas desde PDFs.
"""

import logging
from pathlib import Path
from typing import Any

import pdfplumber

from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """
    Parser para archivos PDF usando pdfplumber.

    Este parser extrae texto y tablas desde archivos PDF.
    Para casos de uso específicos, hereda de esta clase y personaliza.
    """

    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear archivo PDF.

        Args:
            data: Ruta del archivo PDF (str o Path)

        Returns:
            Diccionario con resultado del parseo
        """
        try:
            file_path = Path(data) if not isinstance(data, Path) else data

            if not file_path.exists():
                raise FileNotFoundError(f"PDF file not found: {file_path}")

            with pdfplumber.open(file_path) as pdf:
                # Extract text from all pages
                text_content = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)

                # Extract tables from all pages
                tables = []
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

                parsed_data = {
                    "text": "\n\n".join(text_content),
                    "tables": tables,
                    "num_pages": len(pdf.pages),
                }

                return {
                    "parsing_successful": True,
                    "parsed_data": parsed_data,
                    "error_message": None,
                    "metadata": {
                        "parser_type": "pdf",
                        "num_pages": len(pdf.pages),
                        "num_tables": len(tables),
                    },
                }

        except FileNotFoundError as e:
            logger.error(f"PDF file not found: {e}")
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "pdf"},
            }

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}", exc_info=True)
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"PDF parsing error: {str(e)}",
                "metadata": {"parser_type": "pdf"},
            }
