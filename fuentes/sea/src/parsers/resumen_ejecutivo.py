"""
Parser para links de Resumen Ejecutivo.

Este módulo parsea el HTML de la página del documento EIA/DIA
y extrae el link al PDF del Capítulo 20 - Resumen Ejecutivo.
"""

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ResumenEjecutivoParser:
    """
    Parser para links de Resumen Ejecutivo.

    Parsea el HTML de documento.php y extrae el link al PDF
    del Resumen Ejecutivo (Capítulo 20).
    """

    def _extract_debug_snippet(self, soup: BeautifulSoup, max_length: int = 1000) -> str:
        """
        Extraer snippet de debug del HTML para entender por qué falló.

        Args:
            soup: BeautifulSoup objeto
            max_length: Longitud máxima del snippet

        Returns:
            Snippet de HTML con los primeros headings y links
        """
        snippets = []

        # Capturar headings (h3, h4) para ver estructura
        headings = soup.find_all(['h3', 'h4'], limit=10)
        if headings:
            snippets.append("=== HEADINGS ENCONTRADOS ===")
            for h in headings:
                snippets.append(f"{h.name}: {h.get_text(strip=True)[:100]}")

        # Capturar primeros 10 links para ver qué hay
        links = soup.find_all('a', href=True, limit=10)
        if links:
            snippets.append("\n=== PRIMEROS LINKS ===")
            for link in links:
                text = link.get_text(strip=True)[:100]
                href = link['href'][:150]
                snippets.append(f"• {text} -> {href}")

        result = "\n".join(snippets)
        return result[:max_length] if len(result) > max_length else result

    def parse_resumen_ejecutivo_link_from_mostrar_documento(
        self, html_content: str, id_documento: int
    ) -> dict[str, Any] | None:
        """
        Parsear HTML del MostrarDocumento para extraer link al PDF del Resumen Ejecutivo.

        Estrategia mejorada: Buscar con regex "Resumen" en el HTML, verificar que
        esté seguido de "Ejecutivo", y tomar el siguiente link.

        Args:
            html_content: HTML de la respuesta desde MostrarDocumento
            id_documento: ID del documento

        Returns:
            Diccionario con datos del link o None si no se encuentra.
            Si falla, incluye failure_reason y debug_snippet para diagnosticar.
        """
        if not html_content:
            logger.warning(f"HTML vacío para documento {id_documento}")
            return {
                "id_documento": id_documento,
                "failure_reason": "HTML vacío o None",
                "debug_snippet": "N/A - sin contenido",
            }

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # ESTRATEGIA: Buscar heading/bold que contenga "Resumen ejecutivo"
            # y luego tomar el primer link después de ese elemento

            # Buscar heading o bold que contenga "Resumen Ejecutivo"
            resumen_element = soup.find(
                ['h3', 'h4', 'h5', 'b', 'strong'],
                string=re.compile(r'resumen\s+ejecutivo', re.IGNORECASE)
            )

            if resumen_element:
                logger.info(f"Encontrado elemento 'Resumen Ejecutivo' para documento {id_documento}")

                # Buscar el siguiente <a> después del elemento
                next_link = resumen_element.find_next('a', href=True)

                if next_link and next_link.get('href'):
                    href = next_link['href']
                    text = next_link.get_text(strip=True)

                    # Verificar que sea un link a PDF o archivo
                    if href.startswith('http') or href.endswith('.pdf'):
                        pdf_filename = href.split('/')[-1] if '/' in href else None

                        logger.info(f"Link a Resumen Ejecutivo encontrado para documento {id_documento}: {href}")

                        return {
                            "id_documento": id_documento,
                            "pdf_url": href,
                            "pdf_filename": pdf_filename,
                            "texto_link": text,
                        }
                    else:
                        # El siguiente link no es un PDF, seguir buscando
                        logger.warning(f"El siguiente link después de 'Resumen Ejecutivo' no es un PDF: {href}")
                else:
                    logger.warning(f"No se encontró link después del elemento 'Resumen Ejecutivo'")

            # Si llegamos aquí, no encontramos el patrón
            logger.warning(f"No se encontró 'Resumen Ejecutivo' seguido de link PDF en documento {id_documento}")
            return {
                "id_documento": id_documento,
                "failure_reason": "No se encontró elemento 'Resumen Ejecutivo' o link PDF siguiente",
                "debug_snippet": self._extract_debug_snippet(soup),
            }

        except Exception as e:
            logger.error(f"Error parseando resumen ejecutivo de documento {id_documento}: {e}", exc_info=True)
            return {
                "id_documento": id_documento,
                "failure_reason": f"Excepción durante parsing: {str(e)}",
                "debug_snippet": "Error - no se pudo generar snippet",
            }

    def parse_resumen_ejecutivo_link(
        self, html_content: str, id_documento: int
    ) -> dict[str, Any] | None:
        """
        Parsear HTML para extraer link al PDF del Resumen Ejecutivo.

        NOTA: Esta es la versión legacy que parsea documento.php.
        Para MostrarDocumento, usar parse_resumen_ejecutivo_link_from_mostrar_documento()

        Args:
            html_content: HTML de la respuesta
            id_documento: ID del documento

        Returns:
            Diccionario con datos del link o None si no se encuentra.
            Si falla, incluye failure_reason y debug_snippet para diagnosticar.
        """
        if not html_content:
            logger.warning(f"HTML vacío para documento {id_documento}")
            return {
                "id_documento": id_documento,
                "failure_reason": "HTML vacío o None",
                "debug_snippet": "N/A - sin contenido",
            }

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # ESTRATEGIA 1: Buscar sección "Resumen ejecutivo" con heading (EIAs)
            resumen_heading = soup.find(['h3', 'h4'], string=re.compile(
                r'resumen ejecutivo', re.IGNORECASE
            ))

            if resumen_heading:
                # Buscar el siguiente <ul> con el link
                next_sibling = resumen_heading.find_next_sibling()

                if next_sibling and next_sibling.name == 'ul':
                    links = next_sibling.find_all('a', href=True)

                    for link in links:
                        href = link['href']
                        text = link.get_text(strip=True)

                        # Si encontramos el heading "Resumen ejecutivo", tomamos CUALQUIER link a PDF
                        # No verificamos el texto porque puede ser abreviado (ej: "RESUMEN EJ.")
                        if href.endswith('.pdf') or 'archivos' in href.lower():
                            pdf_filename = href.split('/')[-1] if '/' in href else None

                            logger.info(f"Link a Resumen Ejecutivo encontrado (con heading) para documento {id_documento}: {href}")

                            return {
                                "id_documento": id_documento,
                                "pdf_url": href,
                                "pdf_filename": pdf_filename,
                                "texto_link": text,
                            }

                    # Hay heading pero ningún link PDF
                    return {
                        "id_documento": id_documento,
                        "failure_reason": f"Heading 'Resumen Ejecutivo' encontrado pero no hay links a PDF en <ul>. Links en <ul>: {len(links)}",
                        "debug_snippet": self._extract_debug_snippet(soup),
                    }
                else:
                    # Hay heading pero no hay <ul> siguiente
                    return {
                        "id_documento": id_documento,
                        "failure_reason": f"Heading 'Resumen Ejecutivo' encontrado pero no hay <ul> siguiente. Next sibling: {next_sibling.name if next_sibling else 'None'}",
                        "debug_snippet": self._extract_debug_snippet(soup),
                    }

            # ESTRATEGIA 2: Buscar directamente en TODOS los links
            # Buscar patrones de:
            # - EIAs: "Resumen Ejecutivo", "Capítulo 00", "Capítulo 20", "Cap 00", "Cap 20"
            # - DIAs: "Ficha Resumen", "Resumen"
            all_links = soup.find_all('a', href=True)

            for link in all_links:
                href = link['href']
                text = link.get_text(strip=True)
                text_lower = text.lower()

                # Verificar que sea un link a PDF
                if not (href.endswith('.pdf') or 'archivos' in href.lower()):
                    continue

                # Buscar patrones de EIA
                if ('resumen ejecutivo' in text_lower or
                    'capítulo 00' in text_lower or
                    'capitulo 00' in text_lower or
                    'cap 00' in text_lower or
                    'cap. 00' in text_lower or
                    'cap_00' in text_lower or
                    'capítulo 20' in text_lower or
                    'capitulo 20' in text_lower or
                    ('cap' in text_lower and '20' in text_lower) or
                    'cap_20' in text_lower or
                    'capitulo_0' in text_lower):

                    pdf_filename = href.split('/')[-1] if '/' in href else None

                    logger.info(f"Link a Resumen Ejecutivo (EIA) encontrado para documento {id_documento}: {href}")

                    return {
                        "id_documento": id_documento,
                        "pdf_url": href,
                        "pdf_filename": pdf_filename,
                        "texto_link": text,
                    }

                # Buscar patrones de DIA (Ficha Resumen)
                if ('ficha resumen' in text_lower or
                    'ficha_resumen' in text_lower or
                    (('ficha' in text_lower or 'cap' in text_lower or 'capitulo' in text_lower) and 'resumen' in text_lower)):

                    pdf_filename = href.split('/')[-1] if '/' in href else None

                    logger.info(f"Link a Ficha Resumen (DIA) encontrado para documento {id_documento}: {href}")

                    return {
                        "id_documento": id_documento,
                        "pdf_url": href,
                        "pdf_filename": pdf_filename,
                        "texto_link": text,
                    }

            # No se encontró nada
            logger.warning(f"No se encontró link al Resumen Ejecutivo en documento {id_documento}")
            return {
                "id_documento": id_documento,
                "failure_reason": f"No hay heading 'Resumen Ejecutivo' ni links con patrones coincidentes. Total links: {len(all_links)}",
                "debug_snippet": self._extract_debug_snippet(soup),
            }

        except Exception as e:
            logger.error(f"Error parseando resumen ejecutivo de documento {id_documento}: {e}", exc_info=True)
            return {
                "id_documento": id_documento,
                "failure_reason": f"Excepción durante parsing: {str(e)}",
                "debug_snippet": "Error - no se pudo generar snippet",
            }

    def parse_documento_firmado_link(self, html_content: str) -> dict[str, str] | None:
        """
        Parsear HTML para extraer link al documento firmado completo.

        Args:
            html_content: HTML de la respuesta

        Returns:
            Diccionario con URL y docId del documento firmado o None
        """
        if not html_content:
            return None

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Buscar link a infofirma.sea.gob.cl
            links = soup.find_all('a', href=True)

            for link in links:
                href = link['href']
                if 'infofirma.sea.gob.cl' in href and 'MostrarDocumento' in href:
                    # Extraer docId
                    match = re.search(r'docId=([^"\'&\s]+)', href)
                    docid = match.group(1) if match else None

                    return {
                        "documento_firmado_url": href,
                        "documento_firmado_docid": docid,
                    }

            return None

        except Exception as e:
            logger.error(f"Error parseando documento firmado: {e}")
            return None


def get_resumen_ejecutivo_parser() -> ResumenEjecutivoParser:
    """
    Factory function para crear una instancia de ResumenEjecutivoParser.

    Returns:
        Instancia de ResumenEjecutivoParser
    """
    return ResumenEjecutivoParser()
