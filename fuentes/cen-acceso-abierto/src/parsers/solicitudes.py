"""
Parser para datos de solicitudes y documentos del CEN.

Este módulo transforma datos JSON raw a diccionarios listos para insertar en BD.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def parse_solicitud(raw_solicitud: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parsea una solicitud raw del JSON a formato para BD.

    La solicitud ya viene en formato adecuado del API, solo necesitamos
    validar y retornarla tal cual.

    Args:
        raw_solicitud: Diccionario con datos de solicitud del API

    Returns:
        Diccionario listo para insertar en tabla solicitudes
    """
    # El API ya retorna el formato correcto, solo pasamos tal cual
    return raw_solicitud


def parse_documento(raw_documento: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parsea un documento raw del JSON a formato para BD.

    Args:
        raw_documento: Diccionario con datos de documento del API

    Returns:
        Diccionario listo para insertar en tabla documentos
    """
    # El API ya retorna el formato correcto, solo pasamos tal cual
    return raw_documento
