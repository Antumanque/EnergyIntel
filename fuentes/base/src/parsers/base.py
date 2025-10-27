"""
Clase base abstracta para parsers de datos.

Este módulo define la interfaz que todos los parsers deben implementar.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    Clase base abstracta para parsers de datos.

    Todos los parsers concretos (JSON, PDF, XLSX, CSV, HTML, etc.)
    deben heredar de esta clase e implementar el método parse().
    """

    def __init__(self):
        """Inicializar el parser."""
        pass

    @abstractmethod
    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear datos desde el formato crudo.

        Este método debe ser implementado por cada parser concreto.

        Args:
            data: Datos crudos a parsear (puede ser str, bytes, dict, Path, etc.)

        Returns:
            Diccionario con los datos parseados. Debe incluir:
            - parsing_successful: bool indicando si el parseo fue exitoso
            - parsed_data: dict con los datos parseados (si fue exitoso)
            - error_message: str con mensaje de error (si falló)
            - metadata: dict con metadata adicional (opcional)

        Example:
            {
                "parsing_successful": True,
                "parsed_data": {
                    "field1": "value1",
                    "field2": "value2"
                },
                "error_message": None,
                "metadata": {
                    "parser_type": "pdf",
                    "num_pages": 5
                }
            }
        """
        pass

    def validate_result(self, result: dict[str, Any]) -> bool:
        """
        Validar que un resultado de parseo tenga los campos requeridos.

        Args:
            result: Diccionario de resultado a validar

        Returns:
            True si es válido, False sino
        """
        required_fields = ["parsing_successful", "error_message"]
        has_required = all(field in result for field in required_fields)

        # Si fue exitoso, debe tener parsed_data
        if result.get("parsing_successful"):
            has_required = has_required and "parsed_data" in result

        return has_required

    def parse_safe(self, data: Any) -> dict[str, Any]:
        """
        Parsear datos con manejo de errores incorporado.

        Esta es una versión wrapper de parse() que captura excepciones
        y retorna un resultado estandarizado incluso si el parseo falla.

        Args:
            data: Datos crudos a parsear

        Returns:
            Diccionario con resultado del parseo (siempre con formato válido)
        """
        try:
            result = self.parse(data)

            if not self.validate_result(result):
                logger.warning(
                    f"Parser {self.__class__.__name__} returned invalid result format"
                )
                return {
                    "parsing_successful": False,
                    "parsed_data": None,
                    "error_message": "Invalid result format from parser",
                    "metadata": {},
                }

            return result

        except Exception as e:
            logger.error(
                f"Error in parser {self.__class__.__name__}: {e}",
                exc_info=True,
            )
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"Parser exception: {str(e)}",
                "metadata": {},
            }
