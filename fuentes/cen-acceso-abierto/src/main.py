#!/usr/bin/env python3
"""
Orquestador principal de extracción de datos del CEN.

Este script NO contiene lógica de negocio, solo orquesta los extractors.
Determina qué extractors ejecutar basándose en la configuración.
"""

import logging
import sys

from src.extractors.interesados import get_interesados_extractor
from src.extractors.solicitudes import get_solicitudes_extractor
from src.settings import get_settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> int:
    """
    Función principal del orquestador.

    Ejecuta los extractors configurados en orden:
    1. Interesados (si hay API_URLs configurados)
    2. Solicitudes y Documentos (si hay CEN_YEARS configurados)

    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO EXTRACCIÓN CEN")
    logger.info("=" * 70)

    try:
        # Cargar configuración
        settings = get_settings()

        exit_code = 0
        extractors_run = 0

        # Extractor 1: Interesados
        if settings.api_urls:
            logger.info("\n" + "=" * 70)
            logger.info("EXTRACTOR 1: INTERESADOS (STAKEHOLDERS)")
            logger.info("=" * 70)

            interesados_extractor = get_interesados_extractor(settings)
            result = interesados_extractor.run()

            if result != 0:
                logger.warning("⚠️ Extractor de interesados terminó con errores")
                exit_code = 1

            extractors_run += 1
        else:
            logger.info("\n⏭️  Saltando extractor de interesados (no hay API_URLs configurados)")

        # Extractor 2: Solicitudes y Documentos
        if settings.cen_years_list:
            logger.info("\n" + "=" * 70)
            logger.info("EXTRACTOR 2: SOLICITUDES Y DOCUMENTOS")
            logger.info("=" * 70)

            solicitudes_extractor = get_solicitudes_extractor(settings)
            result = solicitudes_extractor.run()

            if result != 0:
                logger.warning("⚠️ Extractor de solicitudes terminó con errores")
                exit_code = 1

            extractors_run += 1
        else:
            logger.info("\n⏭️  Saltando extractor de solicitudes (no hay CEN_YEARS configurados)")

        # Resumen final
        logger.info("\n" + "=" * 70)
        logger.info("📊 RESUMEN DE EXTRACCIÓN")
        logger.info("=" * 70)
        logger.info(f"Extractors ejecutados: {extractors_run}")

        if extractors_run == 0:
            logger.warning("⚠️ No se ejecutó ningún extractor")
            logger.warning("Configura API_URLs o CEN_YEARS en tu archivo .env")
            return 1

        if exit_code == 0:
            logger.info("✅ TODOS LOS EXTRACTORS COMPLETADOS EXITOSAMENTE")
        else:
            logger.warning("⚠️ ALGUNOS EXTRACTORS TERMINARON CON ERRORES")

        logger.info("=" * 70)

        return exit_code

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Proceso interrumpido por el usuario")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Error fatal en orquestador: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
