"""
Extractor para proyectos del SEA (Sistema de Evaluación de Impacto Ambiental).

Este módulo maneja la extracción de datos de proyectos desde la API de búsqueda
del SEA con soporte para paginación automática y extracción paralela.
"""

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from src.core.http_client import HTTPClient, format_duration
from src.schemas.proyecto import validate_api_response, validate_proyecto
from src.settings import Settings

logger = logging.getLogger(__name__)

# Configuración de concurrencia
DEFAULT_CONCURRENCY = 10

# Estadísticas de validación (global para la sesión)
_validation_stats = {"valid": 0, "invalid": 0, "errors": []}


def reset_validation_stats():
    """Resetear estadísticas de validación."""
    global _validation_stats
    _validation_stats = {"valid": 0, "invalid": 0, "errors": []}


def get_validation_stats() -> dict:
    """Obtener estadísticas de validación."""
    return _validation_stats.copy()


def log_validation_summary():
    """Loguear resumen de validación."""
    stats = get_validation_stats()
    total = stats["valid"] + stats["invalid"]
    if total > 0:
        pct = (stats["valid"] / total) * 100
        if stats["invalid"] == 0:
            logger.info(f"✓ Validación Pydantic: {stats['valid']}/{total} respuestas válidas (100%)")
        else:
            logger.warning(
                f"⚠ Validación Pydantic: {stats['valid']}/{total} respuestas válidas ({pct:.1f}%)"
            )
            if stats["errors"]:
                for err in stats["errors"][:5]:
                    logger.warning(f"  - {err}")


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


class AsyncProyectosExtractor:
    """
    Extractor asíncrono para proyectos del SEA con requests paralelos.

    Usa asyncio + httpx para hacer múltiples requests en paralelo,
    reduciendo significativamente el tiempo de extracción.
    """

    def __init__(self, settings: Settings, concurrency: int = DEFAULT_CONCURRENCY):
        """
        Inicializar el extractor asíncrono.

        Args:
            settings: Configuración de la aplicación
            concurrency: Número máximo de requests paralelos
        """
        self.settings = settings
        self.api_url = settings.sea_api_base_url
        self.concurrency = concurrency
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    async def _fetch_page_async(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        offset: int
    ) -> dict[str, Any]:
        """
        Fetch una página de forma asíncrona con semáforo de concurrencia.
        """
        async with semaphore:
            params = self.settings.build_api_params(offset=offset)
            source_url = f"{self.api_url}?offset={offset}&limit={self.settings.sea_limit}"

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "SEA-SEIA-Extractor/1.0",
            }

            last_error = None
            for attempt in range(self.max_retries + 1):
                try:
                    fetch_start = time.perf_counter()
                    response = await client.post(
                        self.api_url,
                        data=params,
                        headers=headers,
                    )
                    fetch_elapsed = time.perf_counter() - fetch_start

                    if response.is_success:
                        # Decodificar con ISO-8859-1 (Latin-1)
                        text_content = response.content.decode('ISO-8859-1')
                        data = json.loads(text_content)

                        # Validar respuesta de la API
                        is_valid, validated_response, validation_error = validate_api_response(data)
                        if not is_valid:
                            logger.warning(f"Página {offset}: Schema inválido - {validation_error}")
                            _validation_stats["invalid"] += 1
                            if len(_validation_stats["errors"]) < 10:
                                _validation_stats["errors"].append(f"Página {offset}: {validation_error}")
                        else:
                            _validation_stats["valid"] += 1
                            # Validar algunos proyectos como sample
                            proyectos = data.get("data", [])
                            for p in proyectos[:3]:  # Validar primeros 3 como muestra
                                p_valid, _, p_error = validate_proyecto(p)
                                if not p_valid:
                                    logger.debug(f"Proyecto inválido en página {offset}: {p_error}")

                        # Contar proyectos para log
                        num_proyectos = len(data.get("data", []))
                        logger.info(
                            f"Página {offset}: {num_proyectos} proyectos "
                            f"(took {format_duration(fetch_elapsed)})"
                        )

                        return {
                            "offset": offset,
                            "source_url": source_url,
                            "source_type": "api_rest",
                            "status_code": response.status_code,
                            "data": data,
                            "error_message": None,
                            "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                            "schema_valid": is_valid,
                        }
                    else:
                        last_error = f"HTTP {response.status_code}"
                        if 400 <= response.status_code < 500:
                            break  # No retry en errores 4xx

                except httpx.TimeoutException:
                    last_error = f"Timeout after {self.timeout}s"
                    logger.warning(f"Página {offset}: timeout (attempt {attempt + 1})")
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Página {offset}: error {e} (attempt {attempt + 1})")

                # Esperar antes de retry
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))

            # Falló después de todos los intentos
            logger.error(f"Página {offset}: falló después de {self.max_retries + 1} intentos")
            return {
                "offset": offset,
                "source_url": source_url,
                "source_type": "api_rest",
                "status_code": 0,
                "data": None,
                "error_message": last_error,
                "extracted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            }

    async def _fetch_first_page(self, client: httpx.AsyncClient) -> tuple[dict[str, Any], int, int]:
        """
        Fetch la primera página para obtener total de registros.

        Returns:
            Tupla (result, total_records, max_pages)
        """
        semaphore = asyncio.Semaphore(1)
        result = await self._fetch_page_async(client, semaphore, offset=1)

        total_records = 0
        max_pages = 0

        if result["status_code"] == 200 and result["data"]:
            records_total_raw = result["data"].get("recordsTotal")
            if records_total_raw:
                total_records = int(records_total_raw) if isinstance(records_total_raw, str) else records_total_raw
                max_pages = math.ceil(total_records / self.settings.sea_limit)
                logger.info(
                    f"Total de proyectos en la API: {total_records:,} "
                    f"(máximo {max_pages} páginas con limit={self.settings.sea_limit})"
                )

        return result, total_records, max_pages

    async def extract_all_parallel(
        self,
        max_pages: int | None = None
    ) -> tuple[list[dict[str, Any]], int, int]:
        """
        Extraer todas las páginas en paralelo.

        Args:
            max_pages: Límite de páginas (None = todas)

        Returns:
            Tupla (results, total_records, total_proyectos)
        """
        all_results = []
        total_proyectos = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Paso 1: Primera página para obtener total
            logger.info("Obteniendo primera página para calcular total...")
            first_result, total_records, calculated_max_pages = await self._fetch_first_page(client)
            all_results.append(first_result)

            if first_result["status_code"] != 200:
                logger.error("Error en primera página, abortando")
                return all_results, 0, 0

            # Contar proyectos de primera página
            if first_result["data"]:
                total_proyectos += len(first_result["data"].get("data", []))

            # Determinar cuántas páginas extraer
            pages_to_fetch = calculated_max_pages
            if max_pages:
                pages_to_fetch = min(max_pages, calculated_max_pages)

            if pages_to_fetch <= 1:
                return all_results, total_records, total_proyectos

            # Paso 2: Resto de páginas en paralelo por batches
            remaining_pages = list(range(2, pages_to_fetch + 1))
            semaphore = asyncio.Semaphore(self.concurrency)

            logger.info(
                f"Extrayendo páginas 2-{pages_to_fetch} en paralelo "
                f"(concurrencia: {self.concurrency})..."
            )

            # Procesar en batches para mostrar progreso
            batch_size = self.concurrency
            for batch_start in range(0, len(remaining_pages), batch_size):
                batch_pages = remaining_pages[batch_start:batch_start + batch_size]
                batch_num = (batch_start // batch_size) + 1
                total_batches = math.ceil(len(remaining_pages) / batch_size)

                batch_start_time = time.perf_counter()
                logger.info(
                    f"BATCH {batch_num}/{total_batches}: "
                    f"páginas {batch_pages[0]}-{batch_pages[-1]}..."
                )

                # Lanzar requests del batch en paralelo
                tasks = [
                    self._fetch_page_async(client, semaphore, offset)
                    for offset in batch_pages
                ]
                batch_results = await asyncio.gather(*tasks)

                batch_elapsed = time.perf_counter() - batch_start_time

                # Acumular resultados
                all_results.extend(batch_results)

                # Contar proyectos del batch
                batch_proyectos = 0
                batch_errors = 0
                for result in batch_results:
                    if result["status_code"] == 200 and result["data"]:
                        batch_proyectos += len(result["data"].get("data", []))
                    else:
                        batch_errors += 1

                total_proyectos += batch_proyectos

                logger.info(
                    f"BATCH {batch_num}/{total_batches} completado: "
                    f"{batch_proyectos} proyectos, {batch_errors} errores "
                    f"(took {format_duration(batch_elapsed)}, "
                    f"total: {total_proyectos:,}/{total_records:,})"
                )

        # Ordenar resultados por offset
        all_results.sort(key=lambda x: x.get("offset", 0))

        logger.info(
            f"Extracción paralela completada: {len(all_results)} páginas, "
            f"{total_proyectos:,} proyectos"
        )

        # Loguear resumen de validación
        log_validation_summary()

        return all_results, total_records, total_proyectos

    def extract_all_sync(self, max_pages: int | None = None) -> tuple[list[dict[str, Any]], int, int]:
        """
        Wrapper síncrono para extract_all_parallel.
        """
        reset_validation_stats()  # Reset stats antes de nueva extracción
        return asyncio.run(self.extract_all_parallel(max_pages))


def get_async_proyectos_extractor(
    settings: Settings,
    concurrency: int = DEFAULT_CONCURRENCY
) -> AsyncProyectosExtractor:
    """
    Factory function para crear un extractor asíncrono.

    Args:
        settings: Settings de aplicación
        concurrency: Número de requests paralelos (default: 10)

    Returns:
        Instancia de AsyncProyectosExtractor
    """
    return AsyncProyectosExtractor(settings, concurrency)
