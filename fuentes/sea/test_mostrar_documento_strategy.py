"""
Script de prueba para validar la estrategia de extracción mejorada.

NUEVA ESTRATEGIA:
1. Etapa 3a: Extraer documento_firmado_url desde documento.php
2. Etapa 3b: Extraer PDF link desde MostrarDocumento usando nuevo parser
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.http_client import get_http_client
from src.core.database import get_database_manager
from src.parsers.resumen_ejecutivo import ResumenEjecutivoParser
from src.settings import get_settings
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    settings = get_settings()
    http_client = get_http_client(settings)
    db = get_database_manager(settings)
    parser = ResumenEjecutivoParser()

    # Obtener documentos sin documento_firmado_url
    documentos = db.fetch_all(
        """
        SELECT id_documento
        FROM expediente_documentos
        WHERE id_documento NOT IN (
            SELECT id_documento
            FROM resumen_ejecutivo_links
            WHERE documento_firmado_url IS NOT NULL
        )
        LIMIT 20
        """,
        dictionary=True
    )

    logger.info(f"Encontrados {len(documentos)} documentos sin documento_firmado_url")

    success_count = 0
    error_count = 0

    for doc in documentos:
        id_documento = doc['id_documento']
        logger.info(f"\n{'='*80}")
        logger.info(f"Procesando documento {id_documento}")
        logger.info(f"{'='*80}")

        # ETAPA 3a: Extraer documento_firmado_url desde documento.php
        try:
            url = f"https://seia.sea.gob.cl/documentos/documento.php?idDocumento={id_documento}"
            logger.info(f"Extrayendo de: {url}")

            status_code, html_content, error = http_client.fetch_url(url)

            if error:
                logger.error(f"Error en fetch: {error}")
                error_count += 1
                continue


            # Parsear para encontrar documento_firmado_url
            doc_firmado = parser.parse_documento_firmado_link(html_content)

            if not doc_firmado or not doc_firmado.get('documento_firmado_url'):
                logger.warning(f"No se encontró documento_firmado_url para {id_documento}")
                error_count += 1
                continue

            documento_firmado_url = doc_firmado['documento_firmado_url']
            logger.info(f"✓ documento_firmado_url encontrado: {documento_firmado_url}")

            # ETAPA 3b: Extraer PDF link desde MostrarDocumento
            logger.info(f"Extrayendo PDF desde MostrarDocumento...")

            status_code2, html_mostrar, error2 = http_client.fetch_url(documento_firmado_url)

            if error2:
                logger.error(f"Error en fetch MostrarDocumento: {error2}")
                error_count += 1
                continue

            # Usar el nuevo parser
            result = parser.parse_resumen_ejecutivo_link_from_mostrar_documento(
                html_mostrar,
                id_documento
            )

            if result and result.get('pdf_url'):
                logger.info(f"✓✓ PDF ENCONTRADO: {result['pdf_url']}")
                logger.info(f"   Texto del link: {result['texto_link']}")
                success_count += 1
            else:
                logger.warning(f"✗ No se encontró PDF en MostrarDocumento")
                logger.warning(f"  Razón: {result.get('failure_reason')}")
                error_count += 1

        except Exception as e:
            logger.error(f"Error procesando documento {id_documento}: {e}", exc_info=True)
            error_count += 1

    # Resumen
    logger.info(f"\n{'='*80}")
    logger.info(f"RESUMEN FINAL")
    logger.info(f"{'='*80}")
    logger.info(f"Documentos procesados: {len(documentos)}")
    logger.info(f"Exitosos: {success_count}")
    logger.info(f"Errores: {error_count}")
    logger.info(f"Tasa de éxito: {(success_count/len(documentos)*100):.1f}%" if documentos else "N/A")

    db.close_connection()


if __name__ == "__main__":
    main()
