"""
Parser para contenido HTML.

Este módulo provee funcionalidad para parsear y extraer datos desde HTML.
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class HTMLParser(BaseParser):
    """
    Parser para contenido HTML usando BeautifulSoup.

    Este parser extrae información estructurada desde HTML.
    Para casos de uso específicos, hereda de esta clase y personaliza.
    """

    def __init__(self, parser: str = "lxml"):
        """
        Inicializar el parser HTML.

        Args:
            parser: Parser de BeautifulSoup a usar ('lxml', 'html.parser', etc.)
        """
        super().__init__()
        self.parser = parser

    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear contenido HTML.

        Args:
            data: String HTML o dict con key 'html'

        Returns:
            Diccionario con resultado del parseo
        """
        try:
            # Extract HTML string
            if isinstance(data, dict) and "html" in data:
                html_content = data["html"]
            elif isinstance(data, str):
                html_content = data
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            # Parse HTML
            soup = BeautifulSoup(html_content, self.parser)

            # Extract basic structured information
            parsed_data = {
                "title": soup.title.string if soup.title else None,
                "meta": self._extract_meta(soup),
                "headings": self._extract_headings(soup),
                "links": self._extract_links(soup),
                "images": self._extract_images(soup),
                "text": soup.get_text(separator="\n", strip=True),
            }

            return {
                "parsing_successful": True,
                "parsed_data": parsed_data,
                "error_message": None,
                "metadata": {
                    "parser_type": "html",
                    "num_links": len(parsed_data["links"]),
                    "num_images": len(parsed_data["images"]),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}", exc_info=True)
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": f"HTML parsing error: {str(e)}",
                "metadata": {"parser_type": "html"},
            }

    def _extract_meta(self, soup: BeautifulSoup) -> dict:
        """Extraer meta tags."""
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if name and content:
                meta[name] = content
        return meta

    def _extract_headings(self, soup: BeautifulSoup) -> dict:
        """Extraer headings (h1-h6)."""
        headings = {}
        for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            tags = [h.get_text(strip=True) for h in soup.find_all(level)]
            if tags:
                headings[level] = tags
        return headings

    def _extract_links(self, soup: BeautifulSoup) -> list[dict]:
        """Extraer links."""
        links = []
        for link in soup.find_all("a", href=True):
            links.append({
                "text": link.get_text(strip=True),
                "href": link.get("href"),
            })
        return links

    def _extract_images(self, soup: BeautifulSoup) -> list[dict]:
        """Extraer imágenes."""
        images = []
        for img in soup.find_all("img", src=True):
            images.append({
                "src": img.get("src"),
                "alt": img.get("alt", ""),
            })
        return images
