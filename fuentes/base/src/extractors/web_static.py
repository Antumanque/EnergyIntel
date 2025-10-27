"""
Extractor para web scraping estático (HTML).

Este módulo provee funcionalidad para scraping de páginas HTML server-side rendered
usando BeautifulSoup.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from src.core.http_client import get_http_client
from src.extractors.base import BaseExtractor
from src.settings import Settings

logger = logging.getLogger(__name__)


class WebStaticExtractor(BaseExtractor):
    """
    Extractor para web scraping estático.

    Este extractor fetchea páginas HTML y extrae el contenido completo,
    opcionalmente parseándolo con BeautifulSoup para análisis posterior.
    """

    def __init__(
        self,
        settings: Settings,
        urls: list[str] | None = None,
        parse_html: bool = True,
    ):
        """
        Inicializar el extractor de web scraping estático.

        Args:
            settings: Settings de aplicación
            urls: Lista opcional de URLs a extraer (usa settings.web_urls si None)
            parse_html: Si True, parsea HTML con BeautifulSoup y extrae estructura
        """
        super().__init__(settings)
        self.urls = urls or settings.web_urls
        self.parse_html = parse_html
        self.http_client = get_http_client(settings)

    def extract(self) -> list[dict[str, Any]]:
        """
        Extraer datos desde las URLs web configuradas.

        Returns:
            Lista de diccionarios con los datos extraídos
        """
        if not self.urls:
            logger.warning("No web URLs configured for extraction")
            return []

        logger.info(f"Starting web static extraction for {len(self.urls)} URL(s)")

        self.results = []

        for url in self.urls:
            result = self._extract_single_url(url)
            self.results.append(result)

        self.log_summary()
        return self.results

    def _extract_single_url(self, url: str) -> dict[str, Any]:
        """
        Extraer datos desde una sola URL web.

        Args:
            url: URL a extraer

        Returns:
            Diccionario con el resultado de la extracción
        """
        logger.info(f"Extracting from: {url}")

        # Fetch the HTML
        status_code, html_content, error_message = self.http_client.fetch_url(url)

        # If fetch failed, return error result
        if error_message:
            logger.error(f"Failed to fetch {url}: {error_message}")
            return {
                "source_url": url,
                "status_code": status_code,
                "data": None,
                "error_message": error_message,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

        # Parse HTML if requested
        data = html_content
        if self.parse_html and isinstance(html_content, str):
            try:
                data = self._parse_html_content(html_content)
                logger.info(f"Successfully parsed HTML from {url}")
            except Exception as e:
                logger.warning(f"Failed to parse HTML from {url}: {e}")
                # Keep raw HTML as data if parsing fails
                data = html_content

        result = {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": None,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Successfully extracted from {url}")
        return result

    def _parse_html_content(self, html_content: str) -> dict[str, Any]:
        """
        Parsear contenido HTML con BeautifulSoup y extraer información estructurada.

        Args:
            html_content: HTML crudo como string

        Returns:
            Diccionario con contenido parseado

        Note:
            Esta es una implementación básica. Para casos de uso específicos,
            hereda de esta clase y sobrescribe este método con tu lógica custom.
        """
        soup = BeautifulSoup(html_content, "lxml")

        # Extraer información básica
        parsed_data = {
            "title": soup.title.string if soup.title else None,
            "meta_description": None,
            "headings": {},
            "links": [],
            "raw_html": html_content,
        }

        # Extraer meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            parsed_data["meta_description"] = meta_desc.get("content")

        # Extraer headings (h1, h2, h3)
        for level in ["h1", "h2", "h3"]:
            headings = [h.get_text(strip=True) for h in soup.find_all(level)]
            if headings:
                parsed_data["headings"][level] = headings

        # Extraer links
        for link in soup.find_all("a", href=True):
            parsed_data["links"].append(
                {
                    "text": link.get_text(strip=True),
                    "href": link.get("href"),
                }
            )

        return parsed_data
