#!/usr/bin/env python3
"""
Orquestador principal de extracción COMPLETA de datos del CEN.

Este script ejecuta SIEMPRE la extracción completa en 4 pasos:
1. Interesados (stakeholders)
2. Solicitudes (proyectos) + Metadata de documentos
3. Descarga masiva de formularios SAC (PDFs/XLSX)
4. Parseo masivo de formularios SAC descargados

NO contiene lógica de negocio, solo orquesta los extractors.

Uso:
    # Ejecución local
    DB_HOST=localhost CEN_YEARS=2025 uv run python -m src.main

    # Ejecución en producción (single command)
    python -m src.main

    # Con logs
    python -m src.main 2>&1 | tee cen_extraction.log
"""

import logging
import sys

from src.batch_download_sac import SACBatchDownloader
from src.batch_parse_sac import SACBatchParser
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
    2. Solicitudes (proyectos eléctricos por año) + Metadata de documentos
    3. Descarga masiva de formularios SAC (PDFs/XLSX)
    4. Parseo masivo de formularios SAC descargados

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

        # PASO 3: Descarga masiva de formularios SAC (SIEMPRE)
        logger.info("\n" + "=" * 70)
        logger.info("PASO 3: DESCARGA MASIVA DE FORMULARIOS SAC")
        logger.info("=" * 70)

        batch_downloader = SACBatchDownloader()
        download_stats = batch_downloader.run_batch_download()

        if download_stats["fallidos"] > 0:
            logger.warning(
                f"⚠️ Descarga completada con {download_stats['fallidos']} errores de {download_stats['total']}"
            )
            # No marcamos exit_code=1 si la mayoría fue exitosa
            if download_stats["fallidos"] > download_stats["exitosos"]:
                exit_code = 1

        # PASO 4: Parseo masivo de formularios SAC (SIEMPRE)
        logger.info("\n" + "=" * 70)
        logger.info("PASO 4: PARSEO MASIVO DE FORMULARIOS SAC")
        logger.info("=" * 70)

        batch_parser = SACBatchParser()
        parse_stats = batch_parser.run_batch_parsing()

        if parse_stats["fallidos"] > 0:
            logger.warning(
                f"⚠️ Parseo completado con {parse_stats['fallidos']} errores de {parse_stats['total']}"
            )
            # No marcamos exit_code=1 si la mayoría fue exitosa
            if parse_stats["fallidos"] > parse_stats["exitosos"]:
                exit_code = 1

        # Resumen final
        logger.info("\n" + "=" * 70)
        logger.info("📊 RESUMEN FINAL DE EJECUCIÓN")
        logger.info("=" * 70)
        logger.info("")
        logger.info("PASO 3 - Descarga de formularios:")
        logger.info(f"  Total documentos:     {download_stats['total']}")
        logger.info(f"  ✅ Descargados:       {download_stats['exitosos']}")
        logger.info(f"  ❌ Fallidos:          {download_stats['fallidos']}")
        logger.info(f"  📁 Ya descargados:    {download_stats.get('ya_descargados', 0)}")
        logger.info("")
        logger.info("PASO 4 - Parseo de formularios:")
        logger.info(f"  Total documentos:     {parse_stats['total']}")
        logger.info(f"  ✅ Parseados:         {parse_stats['exitosos']}")
        logger.info(f"  ❌ Fallidos:          {parse_stats['fallidos']}")
        logger.info("")

        if exit_code == 0:
            logger.info("✅ EXTRACCIÓN Y PROCESAMIENTO COMPLETO EXITOSO")
        else:
            logger.warning("⚠️ PROCESO COMPLETADO CON ERRORES")

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
