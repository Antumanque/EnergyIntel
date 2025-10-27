"""
Extractor para web scraping dinámico (JavaScript).

Este módulo provee funcionalidad para scraping de páginas con JavaScript
usando Playwright (Chrome headless).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from src.extractors.base import BaseExtractor
from src.settings import Settings

logger = logging.getLogger(__name__)


class WebDynamicExtractor(BaseExtractor):
    """
    Extractor para web scraping dinámico con JavaScript.

    Este extractor usa Playwright para cargar páginas completas (incluyendo JavaScript)
    y extraer contenido después de que la página esté completamente renderizada.
    """

    def __init__(
        self,
        settings: Settings,
        urls: list[str] | None = None,
        wait_selector: str | None = None,
        wait_timeout: int | None = None,
    ):
        """
        Inicializar el extractor de web scraping dinámico.

        Args:
            settings: Settings de aplicación
            urls: Lista opcional de URLs a extraer (usa settings.web_urls si None)
            wait_selector: Selector CSS opcional para esperar antes de extraer
            wait_timeout: Timeout opcional en ms (usa settings.playwright_timeout si None)
        """
        super().__init__(settings)
        self.urls = urls or settings.web_urls
        self.wait_selector = wait_selector
        self.wait_timeout = wait_timeout or settings.playwright_timeout

    def extract(self) -> list[dict[str, Any]]:
        """
        Extraer datos desde las URLs web configuradas usando Playwright.

        Returns:
            Lista de diccionarios con los datos extraídos
        """
        if not self.urls:
            logger.warning("No web URLs configured for extraction")
            return []

        logger.info(f"Starting web dynamic extraction for {len(self.urls)} URL(s)")

        self.results = []

        # Start Playwright and process URLs
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.settings.playwright_headless,
                slow_mo=self.settings.playwright_slow_mo,
            )

            try:
                for url in self.urls:
                    result = self._extract_single_url(browser, url)
                    self.results.append(result)
            finally:
                browser.close()

        self.log_summary()
        return self.results

    def _extract_single_url(self, browser: Browser, url: str) -> dict[str, Any]:
        """
        Extraer datos desde una sola URL web usando Playwright.

        Args:
            browser: Instancia de browser de Playwright
            url: URL a extraer

        Returns:
            Diccionario con el resultado de la extracción
        """
        logger.info(f"Extracting from: {url}")

        page = browser.new_page()
        error_message = None
        data = None
        status_code = 0

        try:
            # Navigate to the page
            response = page.goto(url, wait_until="networkidle", timeout=self.wait_timeout)

            if response:
                status_code = response.status

            # Wait for specific selector if provided
            if self.wait_selector:
                try:
                    page.wait_for_selector(self.wait_selector, timeout=self.wait_timeout)
                    logger.info(f"Found selector '{self.wait_selector}' on {url}")
                except PlaywrightTimeout:
                    logger.warning(
                        f"Selector '{self.wait_selector}' not found on {url} "
                        f"within {self.wait_timeout}ms"
                    )

            # Extract page content
            data = {
                "html": page.content(),
                "text": page.inner_text("body"),
                "title": page.title(),
                "url": page.url,  # Final URL after redirects
            }

            logger.info(f"Successfully extracted from {url}")

        except PlaywrightTimeout as e:
            error_message = f"Playwright timeout: {str(e)}"
            logger.error(f"Timeout extracting {url}: {e}")

        except Exception as e:
            error_message = f"Extraction error: {str(e)}"
            logger.error(f"Error extracting {url}: {e}", exc_info=True)

        finally:
            page.close()

        result = {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        return result
