#!/usr/bin/env python3
"""
Orquestador principal de extracción COMPLETA de datos del CEN.

Este script ejecuta SIEMPRE la extracción completa:
1. Interesados (stakeholders)
2. Solicitudes (proyectos)
3. Documentos (adjuntos a solicitudes)

NO contiene lógica de negocio, solo orquesta los extractors.
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

    Ejecuta SIEMPRE la extracción COMPLETA del CEN en este orden:
    1. Interesados (stakeholders de cada solicitud)
    2. Solicitudes (proyectos eléctricos por año)
    3. Documentos (PDFs/XLSX adjuntos a cada solicitud)

    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO EXTRACCIÓN COMPLETA CEN")
    logger.info("=" * 70)

    try:
        # Cargar configuración
        settings = get_settings()
        exit_code = 0

        # PASO 1: Interesados (SIEMPRE)
        logger.info("\n" + "=" * 70)
        logger.info("PASO 1: EXTRACCIÓN DE INTERESADOS (STAKEHOLDERS)")
        logger.info("=" * 70)

        interesados_extractor = get_interesados_extractor(settings)
        result = interesados_extractor.run()

        if result != 0:
            logger.warning("⚠️ Extractor de interesados terminó con errores")
            exit_code = 1

        # PASO 2: Solicitudes y Documentos (SIEMPRE)
        logger.info("\n" + "=" * 70)
        logger.info("PASO 2: EXTRACCIÓN DE SOLICITUDES Y DOCUMENTOS")
        logger.info("=" * 70)

        solicitudes_extractor = get_solicitudes_extractor(settings)
        result = solicitudes_extractor.run()

        if result != 0:
            logger.warning("⚠️ Extractor de solicitudes terminó con errores")
            exit_code = 1

        # Resumen final
        logger.info("\n" + "=" * 70)
        logger.info("📊 RESUMEN FINAL")
        logger.info("=" * 70)

        if exit_code == 0:
            logger.info("✅ EXTRACCIÓN COMPLETA EXITOSA")
        else:
            logger.warning("⚠️ EXTRACCIÓN COMPLETADA CON ERRORES")

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
