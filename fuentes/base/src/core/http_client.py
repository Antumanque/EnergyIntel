"""
Cliente HTTP para fetching de datos desde REST APIs.

Este módulo provee una interfaz simple y robusta para hacer requests HTTP
con manejo apropiado de errores, retries, y timeout management.
"""

import logging
import time
from typing import Any

import httpx

from src.settings import Settings

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    Cliente HTTP para fetchear datos desde REST APIs.

    Esta clase maneja requests HTTP con timeouts configurables, retries,
    y manejo apropiado de errores.
    """

    def __init__(self, settings: Settings):
        """
        Inicializar el cliente HTTP con settings.

        Args:
            settings: Settings de aplicación con configuración HTTP
        """
        self.settings = settings
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    def fetch_url(
        self, url: str, method: str = "GET", **kwargs
    ) -> tuple[int, Any | None, str | None]:
        """
        Fetch data desde una URL con retry logic.

        Este método intenta fetchear data desde la URL dada, reintentando en
        fallos con exponential backoff.

        Args:
            url: La URL a fetchear
            method: Método HTTP (GET, POST, etc.)
            **kwargs: Argumentos adicionales para httpx (headers, json, data, etc.)

        Returns:
            Tupla de (status_code, data, error_message)
            - status_code: HTTP status code (0 si request falló completamente)
            - data: Response data (JSON si es posible, texto sino)
            - error_message: Mensaje de error si request falló, None sino

        Example:
            status, data, error = client.fetch_url("https://api.example.com/data")
            if error is None:
                print(f"Success! Got data: {data}")
            else:
                print(f"Failed with error: {error}")
        """
        last_error = None
        attempt = 0

        # Set default headers if not provided
        if "headers" not in kwargs:
            kwargs["headers"] = {
                "User-Agent": "FuentesBase/1.0",
                "Accept": "application/json, text/plain, */*",
            }

        while attempt <= self.max_retries:
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries + 1})")

                # Make the HTTP request
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(
                        method=method,
                        url=url,
                        follow_redirects=True,
                        **kwargs,
                    )

                # Try to parse as JSON, fall back to text
                try:
                    data = response.json()
                except Exception:
                    data = response.text

                # Check if response was successful
                if response.is_success:
                    logger.info(
                        f"Successfully fetched {url} (status: {response.status_code})"
                    )
                    return response.status_code, data, None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
                    logger.warning(f"Request to {url} failed: {error_msg}")

                    # For 4xx errors, don't retry (client errors)
                    if 400 <= response.status_code < 500:
                        return response.status_code, data, error_msg

                    # For 5xx errors, retry
                    last_error = error_msg

            except httpx.TimeoutException as e:
                last_error = f"Request timeout after {self.timeout} seconds"
                logger.warning(f"Timeout fetching {url}: {e}")

            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
                logger.warning(f"Request error fetching {url}: {e}")

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error fetching {url}: {e}", exc_info=True)

            # Increment attempt counter
            attempt += 1

            # If we have more attempts, wait before retrying (exponential backoff)
            if attempt <= self.max_retries:
                wait_time = 2**attempt  # 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        # All retries exhausted
        logger.error(f"Failed to fetch {url} after {self.max_retries + 1} attempts")
        return 0, None, last_error

    async def fetch_url_async(
        self, url: str, method: str = "GET", **kwargs
    ) -> tuple[int, Any | None, str | None]:
        """
        Versión async de fetch_url para requests concurrentes.

        Este método está diseñado para uso futuro cuando se necesite fetchear
        múltiples URLs concurrentemente.

        Args:
            url: La URL a fetchear
            method: Método HTTP (GET, POST, etc.)
            **kwargs: Argumentos adicionales para httpx

        Returns:
            Tupla de (status_code, data, error_message)
        """
        import asyncio

        last_error = None
        attempt = 0

        # Set default headers if not provided
        if "headers" not in kwargs:
            kwargs["headers"] = {
                "User-Agent": "FuentesBase/1.0",
                "Accept": "application/json, text/plain, */*",
            }

        while attempt <= self.max_retries:
            try:
                logger.info(
                    f"Fetching {url} async (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        follow_redirects=True,
                        **kwargs,
                    )

                try:
                    data = response.json()
                except Exception:
                    data = response.text

                if response.is_success:
                    logger.info(
                        f"Successfully fetched {url} (status: {response.status_code})"
                    )
                    return response.status_code, data, None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
                    logger.warning(f"Request to {url} failed: {error_msg}")

                    if 400 <= response.status_code < 500:
                        return response.status_code, data, error_msg

                    last_error = error_msg

            except httpx.TimeoutException as e:
                last_error = f"Request timeout after {self.timeout} seconds"
                logger.warning(f"Timeout fetching {url}: {e}")

            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
                logger.warning(f"Request error fetching {url}: {e}")

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error fetching {url}: {e}", exc_info=True)

            attempt += 1

            if attempt <= self.max_retries:
                wait_time = 2**attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        logger.error(f"Failed to fetch {url} after {self.max_retries + 1} attempts")
        return 0, None, last_error


def get_http_client(settings: Settings) -> HTTPClient:
    """
    Factory function para crear una instancia de HTTPClient.

    Args:
        settings: Settings de aplicación

    Returns:
        Instancia configurada de HTTPClient
    """
    return HTTPClient(settings)
