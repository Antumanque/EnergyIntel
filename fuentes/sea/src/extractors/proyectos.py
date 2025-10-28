"""
Extractor para proyectos del SEA (Sistema de Evaluación de Impacto Ambiental).

Este módulo maneja la extracción de datos de proyectos desde la API de búsqueda
del SEA con soporte para paginación automática.
"""

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from src.core.http_client import HTTPClient
from src.settings import Settings

logger = logging.getLogger(__name__)


class ProyectosExtractor:
    """
    Extractor para proyectos del SEA.

    Este extractor obtiene proyectos desde la API de búsqueda del SEA,
    manejando paginación automáticamente hasta obtener todos los proyectos disponibles.
    """

    def __init__(self, settings: Settings, http_client: HTTPClient):
        """
        Inicializar el extractor.

        Args:
            settings: Configuración de la aplicación
            http_client: Cliente HTTP para hacer requests
        """
        self.settings = settings
        self.http_client = http_client
        self.api_url = settings.sea_api_base_url
        self.current_offset = 1
        self.total_records = None
        self.max_pages = None
        self.total_proyectos = 0
        self.is_finished = False

    def extract_all_proyectos(self) -> list[dict[str, Any]]:
        """
        Extraer todos los proyectos disponibles con paginación automática.

        Este método hace múltiples requests a la API, incrementando el offset
        hasta alcanzar el número máximo de páginas calculado desde recordsTotal.

        La API del SEA tiene un bug donde sigue retornando datos después del final
        real, por lo que NO podemos confiar en array vacío. En vez de eso, usamos
        recordsTotal de la primera página para calcular el máximo de páginas.

        Returns:
            Lista de diccionarios con metadata de extracción y datos de proyectos
        """
        all_results = []
        offset = 1
        total_proyectos = 0
        total_records = None  # Total de registros según la API
        max_pages = None  # Máximo de páginas calculado

        logger.info("Iniciando extracción de proyectos del SEA")

        while True:
            logger.info(f"Extrayendo página {offset} (limit={self.settings.sea_limit})")

            # Obtener datos de la página actual
            result = self.extract_page(offset)

            # Agregar a resultados
            all_results.append(result)

            # Verificar si la extracción fue exitosa
            if result["status_code"] == 200 and result["data"] is not None:
                # Intentar parsear la respuesta
                try:
                    if isinstance(result["data"], dict):
                        response_data = result["data"]
                    else:
                        response_data = json.loads(result["data"])

                    # Leer totalRegistros de la API (indica cuántos registros quedan)
                    total_registros_str = response_data.get("totalRegistros", "0")
                    records_total_raw = response_data.get("recordsTotal")

                    # DEBUG: Log de valores
                    logger.debug(
                        f"Página {offset}: totalRegistros={total_registros_str}, "
                        f"recordsTotal={records_total_raw}"
                    )

                    # En el primer request, guardar el total de registros y calcular max_pages
                    if offset == 1 and records_total_raw:
                        # Convertir a int (puede venir como string o int)
                        total_records = int(records_total_raw) if isinstance(records_total_raw, str) else records_total_raw
                        max_pages = math.ceil(total_records / self.settings.sea_limit)
                        logger.info(
                            f"Total de proyectos en la API: {total_records:,} "
                            f"(máximo {max_pages} páginas con limit={self.settings.sea_limit})"
                        )

                    # Verificar si hay proyectos en la respuesta
                    proyectos_en_pagina = response_data.get("data", [])
                    num_proyectos_pagina = len(proyectos_en_pagina)

                    # Fallback: Detener si array vacío (protección adicional)
                    if num_proyectos_pagina == 0:
                        logger.info(
                            f"Última página alcanzada (array vacío). "
                            f"Total extraído: {total_proyectos} proyectos"
                        )
                        break

                    # Hay proyectos en la respuesta - procesar
                    if response_data.get("status") is True and num_proyectos_pagina > 0:
                        num_proyectos = num_proyectos_pagina
                        total_proyectos += num_proyectos

                        progress_info = f"Página {offset}: {num_proyectos} proyectos "
                        progress_info += f"(total acumulado: {total_proyectos}"
                        if total_records:
                            progress_info += f" / {total_records:,}"
                        progress_info += ")"
                        logger.info(progress_info)

                        # Verificar si alcanzamos el máximo de páginas
                        if max_pages and offset >= max_pages:
                            logger.info(
                                f"Máximo de páginas alcanzado ({max_pages}). "
                                f"Total extraído: {total_proyectos} proyectos"
                            )
                            break

                        # Incrementar offset para siguiente página
                        offset += 1
                    else:
                        # No hay proyectos en data
                        logger.info(
                            f"No hay más proyectos disponibles (total: {total_proyectos})"
                        )
                        break

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error parseando respuesta de página {offset}: {e}")
                    break
            else:
                # Error en la extracción
                logger.error(
                    f"Error extrayendo página {offset}: {result.get('error_message')}"
                )
                break

        logger.info(
            f"Extracción completada: {len(all_results)} páginas, {total_proyectos} proyectos totales"
        )
        return all_results

    def extract_batch(self, batch_size: int) -> tuple[list[dict[str, Any]], bool]:
        """
        Extraer un batch de páginas con guardado incremental.

        Este método extrae hasta batch_size páginas y retorna si hay más datos disponibles.
        Mantiene estado interno para continuar desde donde se quedó.

        Args:
            batch_size: Número de páginas a extraer en este batch

        Returns:
            Tupla (batch_results, has_more) donde:
            - batch_results: Lista de resultados de extracción del batch
            - has_more: True si hay más páginas por extraer, False si terminó
        """
        if self.is_finished:
            return [], False

        batch_results = []

        # Extraer hasta batch_size páginas
        for _ in range(batch_size):
            if self.is_finished:
                break

            logger.info(f"Extrayendo página {self.current_offset} (limit={self.settings.sea_limit})")

            # Obtener datos de la página actual
            result = self.extract_page(self.current_offset)
            batch_results.append(result)

            # Verificar si la extracción fue exitosa
            if result["status_code"] == 200 and result["data"] is not None:
                try:
                    if isinstance(result["data"], dict):
                        response_data = result["data"]
                    else:
                        response_data = json.loads(result["data"])

                    # En el primer request, guardar el total de registros y calcular max_pages
                    if self.current_offset == 1:
                        records_total_raw = response_data.get("recordsTotal")
                        if records_total_raw:
                            self.total_records = int(records_total_raw) if isinstance(records_total_raw, str) else records_total_raw
                            self.max_pages = math.ceil(self.total_records / self.settings.sea_limit)
                            logger.info(
                                f"Total de proyectos en la API: {self.total_records:,} "
                                f"(máximo {self.max_pages} páginas con limit={self.settings.sea_limit})"
                            )

                    # Verificar si hay proyectos en la respuesta
                    proyectos_en_pagina = response_data.get("data", [])
                    num_proyectos_pagina = len(proyectos_en_pagina)

                    # Detener SOLO si no hay proyectos en el array
                    if num_proyectos_pagina == 0:
                        logger.info(
                            f"Última página alcanzada (array vacío). "
                            f"Total extraído: {self.total_proyectos} proyectos"
                        )
                        self.is_finished = True
                        break

                    # Hay proyectos - actualizar contadores
                    if response_data.get("status") is True and num_proyectos_pagina > 0:
                        self.total_proyectos += num_proyectos_pagina

                        progress_info = f"Página {self.current_offset}: {num_proyectos_pagina} proyectos "
                        progress_info += f"(total acumulado: {self.total_proyectos}"
                        if self.total_records:
                            progress_info += f" / {self.total_records:,}"
                        progress_info += ")"
                        logger.info(progress_info)

                        # Verificar si alcanzamos el máximo de páginas
                        if self.max_pages and self.current_offset >= self.max_pages:
                            logger.info(
                                f"Máximo de páginas alcanzado ({self.max_pages}). "
                                f"Total extraído: {self.total_proyectos} proyectos"
                            )
                            self.is_finished = True
                            break

                        # Incrementar offset para siguiente página
                        self.current_offset += 1
                    else:
                        logger.info(f"No hay más proyectos disponibles (total: {self.total_proyectos})")
                        self.is_finished = True
                        break

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error parseando respuesta de página {self.current_offset}: {e}")
                    self.is_finished = True
                    break
            else:
                # Error en la extracción
                logger.error(
                    f"Error extrayendo página {self.current_offset}: {result.get('error_message')}"
                )
                self.is_finished = True
                break

        return batch_results, not self.is_finished

    def extract_page(self, offset: int) -> dict[str, Any]:
        """
        Extraer una página de proyectos.

        Args:
            offset: Número de página a extraer (1-based)

        Returns:
            Diccionario con metadata de extracción y datos de la página
        """
        # Construir parámetros de la API
        params = self.settings.build_api_params(offset=offset)

        # Construir URL para logging/tracking
        source_url = f"{self.api_url}?offset={offset}&limit={self.settings.sea_limit}"

        # Hacer request POST con los parámetros
        status_code, data, error_message = self.http_client.fetch_url(
            url=self.api_url,
            method="POST",
            data=params,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "SEA-SEIA-Extractor/1.0",
            },
        )

        # Retornar resultado en formato estandarizado
        return {
            "source_url": source_url,
            "source_type": "api_rest",
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        }


def get_proyectos_extractor(settings: Settings, http_client: HTTPClient) -> ProyectosExtractor:
    """
    Factory function para crear una instancia de ProyectosExtractor.

    Args:
        settings: Settings de aplicación
        http_client: Cliente HTTP

    Returns:
        Instancia configurada de ProyectosExtractor
    """
    return ProyectosExtractor(settings, http_client)
