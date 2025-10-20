"""
Transformador para datos de interesados (partes interesadas).

Este módulo maneja la normalización de datos JSON raw de interesados
en registros individuales de base de datos.
"""

import json
import logging
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)


def transform_interesados(raw_data: Any) -> List[Dict[str, Any]]:
    """
    Transforma datos JSON raw de interesados en registros normalizados.

    Ejemplo:
        >>> raw = '[{"solicitud_id": 219, "razon_social": "Codelco", "nombre_fantasia": "Codelco"}]'
        >>> records = transform_interesados(raw)
        >>> len(records)
        1
        >>> records[0]['solicitud_id']
        219
    """
    # Manejar diferentes tipos de entrada
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return []
    else:
        data = raw_data

    # Asegurar que tenemos una lista
    if not isinstance(data, list):
        logger.warning(f"Expected list, got {type(data)}. Wrapping in list.")
        data = [data]

    records = []
    for idx, item in enumerate(data):
        try:
            record = {
                'solicitud_id': item.get('solicitud_id'),
                'razon_social': item.get('razon_social'),
                'nombre_fantasia': item.get('nombre_fantasia'),
            }

            # Validar campos requeridos
            if record['solicitud_id'] is None:
                logger.warning(f"Record {idx} missing solicitud_id, skipping")
                continue

            records.append(record)

        except Exception as e:
            logger.error(f"Error processing record {idx}: {e}", exc_info=True)
            continue

    logger.info(f"Transformed {len(records)} interesados records from {len(data)} raw items")
    return records


def validate_interesado_record(record: Dict[str, Any]) -> bool:
    """
    Valida que un registro de interesado tenga los campos requeridos.
    """
    required_fields = ['solicitud_id']

    for field in required_fields:
        if field not in record or record[field] is None:
            logger.warning(f"Record missing required field: {field}")
            return False

    return True
