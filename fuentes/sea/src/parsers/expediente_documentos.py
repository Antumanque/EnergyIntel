"""
Parser para documentos del expediente.

Este módulo parsea el HTML de la página de documentos del expediente
y extrae información del documento EIA/DIA.
"""

import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ExpedienteDocumentosParser:
    """
    Parser para documentos del expediente.

    Parsea el HTML de xhr_busqueda_expediente.php y extrae información
    del documento principal EIA o DIA.
    """

    def parse_documentos(self, html_content: str, expediente_id: int) -> list[dict[str, Any]]:
        """
        Parsear HTML para extraer documentos EIA/DIA.

        Args:
            html_content: HTML de la respuesta
            expediente_id: ID del expediente

        Returns:
            Lista de documentos encontrados (normalmente 1)
        """
        if not html_content:
            logger.warning(f"HTML vacío para expediente {expediente_id}")
            return []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Buscar tabla de documentos
            table = soup.find('table', id='busqueda_expediente')
            if not table:
                logger.warning(f"No se encontró tabla de documentos para expediente {expediente_id}")
                return []

            # Buscar filas (skip header)
            rows = table.find_all('tr')[1:]
            documentos = []

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue

                # Extraer datos de las celdas
                folio = cells[2].get_text(strip=True)
                tipo_documento = cells[3].get_text(strip=True)
                remitente = cells[4].get_text(strip=True)
                destinatario = cells[5].get_text(strip=True)
                fecha_str = cells[6].get_text(strip=True)

                # Buscar solo "Estudio de Impacto Ambiental" o "Declaración de Impacto Ambiental"
                if not (
                    'estudio de impacto ambiental' in tipo_documento.lower()
                    or 'declaración de impacto ambiental' in tipo_documento.lower()
                ):
                    continue

                # Extraer id_documento del onclick en celda de acciones
                actions_cell = cells[7]
                id_documento = self._extract_id_documento(actions_cell)

                if not id_documento:
                    logger.warning(f"No se pudo extraer id_documento para {tipo_documento} en expediente {expediente_id}")
                    continue

                # Parsear fecha
                fecha_generacion = self._parse_fecha(fecha_str)

                # Construir URLs
                url_documento = f"https://seia.sea.gob.cl/documentos/documento.php?idDocumento={id_documento}"
                url_anexos = f"https://seia.sea.gob.cl/elementosFisicos/enviados.php?id_documento={id_documento}"

                documento = {
                    "expediente_id": expediente_id,
                    "id_documento": id_documento,
                    "folio": folio if folio else None,
                    "tipo_documento": tipo_documento,
                    "remitente": remitente if remitente else None,
                    "destinatario": destinatario if destinatario else None,
                    "fecha_generacion": fecha_generacion,
                    "url_documento": url_documento,
                    "url_anexos": url_anexos,
                }

                documentos.append(documento)
                logger.debug(f"Documento EIA/DIA encontrado: {tipo_documento} (id={id_documento})")

            if not documentos:
                logger.info(f"No se encontraron documentos EIA/DIA para expediente {expediente_id}")

            return documentos

        except Exception as e:
            logger.error(f"Error parseando documentos de expediente {expediente_id}: {e}", exc_info=True)
            return []

    def _extract_id_documento(self, actions_cell) -> int | None:
        """
        Extraer id_documento del onclick en la celda de acciones.

        Args:
            actions_cell: Celda <td> con botones de acción

        Returns:
            ID del documento o None si no se encuentra
        """
        try:
            # Buscar button con onclick que contenga documento.php?idDocumento=
            buttons = actions_cell.find_all('button', onclick=True)
            for button in buttons:
                onclick = button['onclick']
                # Buscar patrón: documento.php?idDocumento=XXXXXXX
                match = re.search(r'idDocumento=(\d+)', onclick)
                if match:
                    return int(match.group(1))

            return None

        except Exception as e:
            logger.error(f"Error extrayendo id_documento: {e}")
            return None

    def _parse_fecha(self, fecha_str: str) -> str | None:
        """
        Parsear fecha de formato "21/07/2025 19:10:08" a MySQL datetime.

        Args:
            fecha_str: String con fecha

        Returns:
            Fecha en formato MySQL o None
        """
        if not fecha_str:
            return None

        try:
            # Formato: "21/07/2025 19:10:08"
            dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"No se pudo parsear fecha '{fecha_str}': {e}")
            return None


def get_expediente_documentos_parser() -> ExpedienteDocumentosParser:
    """
    Factory function para crear una instancia de ExpedienteDocumentosParser.

    Returns:
        Instancia de ExpedienteDocumentosParser
    """
    return ExpedienteDocumentosParser()
