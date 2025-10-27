"""
Parser para archivos CSV.

Este módulo provee funcionalidad para leer datos desde archivos CSV.
"""

import csv
import logging
from pathlib import Path
from typing import Any

from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class CSVParser(BaseParser):
    """
    Parser para archivos CSV.

    Este parser lee archivos CSV y extrae los datos como lista de diccionarios.
    """

    def __init__(self, delimiter: str = ",", has_header: bool = True):
        """
        Inicializar el parser CSV.

        Args:
            delimiter: Delimitador de columnas (default: coma)
            has_header: Si True, primera fila es header
        """
        super().__init__()
        self.delimiter = delimiter
        self.has_header = has_header

    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear archivo CSV.

        Args:
            data: Ruta del archivo CSV (str o Path) o contenido como string

        Returns:
            Diccionario con resultado del parseo
        """
        try:
            # Handle file path
            if isinstance(data, (str, Path)):
                file_path = Path(data) if not isinstance(data, Path) else data

                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                else:
                    # Assume data is CSV content as string
                    content = str(data)
            else:
                content = str(data)

            # Parse CSV
            rows = []
            reader = csv.reader(content.splitlines(), delimiter=self.delimiter)

            if self.has_header:
                header = next(reader)
                for row in reader:
                    rows.append(dict(zip(header, row)))
            else:
                for row in reader:
                    rows.append(row)

            parsed_data = {
                "rows": rows,
                "num_rows": len(rows),
            }

            return {
                "parsing_successful": True,
                "parsed_data": parsed_data,
                "error_message": None,
                "metadata": {
                    "parser_type": "csv",
                    "num_rows": len(rows),
                    "has_header": self.has_header,
                },
            }

        except Exception as e:
            logger.error(f"Error parsing CSV: {e}", exc_info=True)
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"CSV parsing error: {str(e)}",
                "metadata": {"parser_type": "csv"},
            }
