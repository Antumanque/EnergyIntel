"""
HTTP client module for fetching data from REST APIs.

This module provides a simple, robust interface for making HTTP requests
with proper error handling, retries, and timeout management.
"""

import logging
import time
from typing import Any, Optional, Tuple

import httpx

from src.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class APIClient:
    """
    HTTP client for fetching data from REST APIs.

    This class handles HTTP requests with configurable timeouts, retries,
    and proper error handling.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the API client with settings.

        Args:
            settings: Application settings with HTTP configuration
        """
        self.settings = settings
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    def fetch_url(self, url: str) -> Tuple[int, Optional[Any], Optional[str]]:
        """
        Fetch data from a URL with retry logic.

        This method attempts to fetch data from the given URL, retrying on
        failures with exponential backoff.

        Args:
            url: The URL to fetch

        Returns:
            Tuple of (status_code, data, error_message)
            - status_code: HTTP status code (0 if request failed completely)
            - data: Response data (JSON if possible, text otherwise)
            - error_message: Error message if request failed, None otherwise

        Example:
            status, data, error = client.fetch_url("https://api.example.com/data")
            if error is None:
                print(f"Success! Got data: {data}")
            else:
                print(f"Failed with error: {error}")
        """
        last_error = None
        attempt = 0

        while attempt <= self.max_retries:
            try:
                logger.info(
                    f"Fetching {url} (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                # Make the HTTP request
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(
                        url,
                        headers={
                            "User-Agent": "API-Data-Ingestion-Template/1.0",
                            "Accept": "application/json, text/plain, */*",
                        },
                        follow_redirects=True,
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
                    error_msg = (
                        f"HTTP {response.status_code}: {response.reason_phrase}"
                    )
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
        self, url: str
    ) -> Tuple[int, Optional[Any], Optional[str]]:
        """
        Async version of fetch_url for concurrent requests.

        This method is designed for future use when you need to fetch
        multiple URLs concurrently.

        Args:
            url: The URL to fetch

        Returns:
            Tuple of (status_code, data, error_message)
        """
        last_error = None
        attempt = 0

        while attempt <= self.max_retries:
            try:
                logger.info(
                    f"Fetching {url} async (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        headers={
                            "User-Agent": "API-Data-Ingestion-Template/1.0",
                            "Accept": "application/json, text/plain, */*",
                        },
                        follow_redirects=True,
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
                    error_msg = (
                        f"HTTP {response.status_code}: {response.reason_phrase}"
                    )
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
                # In async context, we'd use asyncio.sleep, but for now:
                import asyncio

                await asyncio.sleep(wait_time)

        logger.error(f"Failed to fetch {url} after {self.max_retries + 1} attempts")
        return 0, None, last_error


def get_api_client(settings: Settings) -> APIClient:
    """
    Factory function to create an APIClient instance.

    Args:
        settings: Application settings

    Returns:
        Configured APIClient instance
    """
    return APIClient(settings)
