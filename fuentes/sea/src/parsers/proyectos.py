"""
Parser para proyectos del SEA.

Este módulo transforma los datos JSON de la API del SEA en un formato
estructurado listo para insertar en la base de datos.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProyectosParser:
    """
    Parser para transformar datos de proyectos del SEA.

    Convierte el formato JSON de la API en diccionarios limpios
    con los campos necesarios para la base de datos.
    """

    def parse_proyectos_from_response(self, response_data: dict | str) -> list[dict[str, Any]]:
        """
        Parsear proyectos desde una respuesta de la API.

        Args:
            response_data: Respuesta JSON de la API (dict o string)

        Returns:
            Lista de diccionarios con proyectos parseados

        Raises:
            ValueError: Si el formato de la respuesta es inválido
        """
        try:
            # Si es string, parsear como JSON
            if isinstance(response_data, str):
                response_data = json.loads(response_data)

            # Verificar que la respuesta sea válida
            if not isinstance(response_data, dict):
                raise ValueError("Response data debe ser un diccionario")

            if not response_data.get("status"):
                logger.warning("API response status is False")
                return []

            if "data" not in response_data:
                logger.warning("No 'data' field in response")
                return []

            # Parsear cada proyecto
            proyectos = []
            for proyecto_raw in response_data["data"]:
                try:
                    proyecto = self.parse_proyecto(proyecto_raw)
                    proyectos.append(proyecto)
                except Exception as e:
                    logger.error(
                        f"Error parseando proyecto {proyecto_raw.get('EXPEDIENTE_ID')}: {e}"
                    )
                    continue

            logger.info(f"Parseados {len(proyectos)} proyectos exitosamente")
            return proyectos

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parseando respuesta: {e}")
            return []

    def parse_proyecto(self, proyecto_raw: dict) -> dict[str, Any]:
        """
        Parsear un proyecto individual.

        Args:
            proyecto_raw: Diccionario con datos crudos del proyecto

        Returns:
            Diccionario con campos parseados y normalizados
        """
        # Parsear link_mapa que viene como objeto JSON
        link_mapa = proyecto_raw.get("LINK_MAPA", {})
        if isinstance(link_mapa, str):
            try:
                link_mapa = json.loads(link_mapa)
            except json.JSONDecodeError:
                link_mapa = {}

        # Construir diccionario con campos normalizados
        return {
            "expediente_id": self._parse_int(proyecto_raw.get("EXPEDIENTE_ID")),
            "expediente_nombre": self._parse_str(proyecto_raw.get("EXPEDIENTE_NOMBRE")),
            "expediente_url_ppal": self._parse_str(proyecto_raw.get("EXPEDIENTE_URL_PPAL")),
            "expediente_url_ficha": self._parse_str(proyecto_raw.get("EXPEDIENTE_URL_FICHA")),
            "workflow_descripcion": self._parse_str(proyecto_raw.get("WORKFLOW_DESCRIPCION")),
            "region_nombre": self._parse_str(proyecto_raw.get("REGION_NOMBRE")),
            "comuna_nombre": self._parse_str(proyecto_raw.get("COMUNA_NOMBRE")),
            "tipo_proyecto": self._parse_str(proyecto_raw.get("TIPO_PROYECTO")),
            "descripcion_tipologia": self._parse_str(proyecto_raw.get("DESCRIPCION_TIPOLOGIA")),
            "razon_ingreso": self._parse_str(proyecto_raw.get("RAZON_INGRESO")),
            "titular": self._parse_str(proyecto_raw.get("TITULAR")),
            "inversion_mm": self._parse_decimal(proyecto_raw.get("INVERSION_MM")),
            "inversion_mm_format": self._parse_str(proyecto_raw.get("INVERSION_MM_FORMAT")),
            "fecha_presentacion": self._parse_int(proyecto_raw.get("FECHA_PRESENTACION")),
            "fecha_presentacion_format": self._parse_str(
                proyecto_raw.get("FECHA_PRESENTACION_FORMAT")
            ),
            "fecha_plazo": self._parse_int(proyecto_raw.get("FECHA_PLAZO")),
            "fecha_plazo_format": self._parse_str(proyecto_raw.get("FECHA_PLAZO_FORMAT")),
            "estado_proyecto": self._parse_str(proyecto_raw.get("ESTADO_PROYECTO")),
            "encargado": self._parse_str(proyecto_raw.get("ENCARGADO")),
            "actividad_actual": self._parse_str(proyecto_raw.get("ACTIVIDAD_ACTUAL")),
            "etapa": self._parse_str(proyecto_raw.get("ETAPA")),
            "link_mapa_show": link_mapa.get("SHOW") if isinstance(link_mapa, dict) else None,
            "link_mapa_url": link_mapa.get("URL") if isinstance(link_mapa, dict) else None,
            "link_mapa_image": link_mapa.get("IMAGE") if isinstance(link_mapa, dict) else None,
            "acciones": self._parse_str(proyecto_raw.get("ACCIONES")),
            "dias_legales": self._parse_int(proyecto_raw.get("DIAS_LEGALES")),
            "suspendido": self._parse_str(proyecto_raw.get("SUSPENDIDO")),
            "ver_actividad": self._parse_str(proyecto_raw.get("VER_ACTIVIDAD")),
        }

    @staticmethod
    def _parse_str(value: Any) -> str | None:
        """
        Parsear valor como string, retornando None si está vacío.

        Args:
            value: Valor a parsear

        Returns:
            String o None
        """
        if value is None or value == "":
            return None
        return str(value).strip()

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        """
        Parsear valor como integer, retornando None si no es válido.

        Args:
            value: Valor a parsear

        Returns:
            Integer o None
        """
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_decimal(value: Any) -> float | None:
        """
        Parsear valor como decimal, retornando None si no es válido.

        Args:
            value: Valor a parsear

        Returns:
            Float o None
        """
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def get_proyectos_parser() -> ProyectosParser:
    """
    Factory function para crear una instancia de ProyectosParser.

    Returns:
        Instancia de ProyectosParser
    """
    return ProyectosParser()
