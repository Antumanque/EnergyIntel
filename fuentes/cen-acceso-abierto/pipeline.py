#!/usr/bin/env python3
"""
🚀 CEN Acceso Abierto - Pipeline Completo Automatizado

Entry point único que ejecuta el pipeline completo end-to-end:
1. Extracción de solicitudes (incremental, solo nuevas)
2. Extracción de documentos (incremental, solo de solicitudes nuevas)
3. Descarga de documentos (solo pendientes)
4. Parsing de formularios (SAC, SUCTD, FEHACIENTE) - solo pendientes

CARACTERÍSTICAS:
- ✅ Idempotente: Se puede ejecutar múltiples veces sin duplicar datos
- ✅ Incremental: Solo procesa datos nuevos
- ✅ Append-only: Nunca actualiza ni borra, solo inserta
- ✅ Detección automática: Si no hay datos, carga desde 0
- ✅ Estadísticas completas: Reporte detallado al final

EJEMPLO DE USO:
    # Ejecutar todo el pipeline
    python pipeline.py

    # Solo extracción (solicitudes + documentos)
    python pipeline.py --solo-fetch

    # Solo descarga
    python pipeline.py --solo-download

    # Solo parsing
    python pipeline.py --solo-parse

    # Limitar documentos a procesar
    python pipeline.py --limit 100

    # Procesar solo un tipo de formulario
    python pipeline.py --tipos SAC

    # Modo dry-run (ver qué se haría sin ejecutar)
    python pipeline.py --dry-run

Fecha: 2025-10-28
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orquestador del pipeline completo."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "solicitudes_nuevas": 0,
            "documentos_nuevos": 0,
            "documentos_descargados": 0,
            "formularios_parseados": {
                "SAC": 0,
                "SUCTD": 0,
                "FEHACIENTE": 0
            }
        }

    def print_header(self, text: str):
        """Imprime header visual."""
        print("\n" + "=" * 100)
        print(f"  {text}")
        print("=" * 100 + "\n")

    def print_section(self, text: str):
        """Imprime sección."""
        print("\n" + "-" * 100)
        print(f">>> {text}")
        print("-" * 100)

    # =========================================================================
    # PASO 1: EXTRACCIÓN DE SOLICITUDES Y DOCUMENTOS
    # =========================================================================

    def step_1_fetch_solicitudes(self) -> int:
        """
        Extrae solicitudes de la API del CEN (incremental).

        Returns:
            Número de solicitudes nuevas extraídas
        """
        self.print_section("PASO 1: Extracción de Solicitudes")

        if self.dry_run:
            logger.info("🔍 [DRY RUN] Se extraerían solicitudes de la API...")
            return 0

        try:
            from src.extractors.solicitudes import SolicitudesExtractor
            from src.settings import get_settings

            settings = get_settings()
            extractor = SolicitudesExtractor()

            # Extraer solicitudes por año
            total_nuevas = 0
            for year in settings.cen_years_list:
                logger.info(f"📅 Procesando año {year}...")
                nuevas = extractor.extract_solicitudes_by_year(year)
                total_nuevas += nuevas
                logger.info(f"  ✅ {nuevas} solicitudes nuevas de {year}")

            logger.info(f"\n✅ Total solicitudes nuevas: {total_nuevas}")
            self.stats["solicitudes_nuevas"] = total_nuevas
            return total_nuevas

        except Exception as e:
            logger.error(f"❌ Error en extracción de solicitudes: {e}", exc_info=True)
            raise

    def step_2_fetch_documentos(self) -> int:
        """
        Extrae documentos de cada solicitud (incremental).

        Returns:
            Número de documentos nuevos extraídos
        """
        self.print_section("PASO 2: Extracción de Documentos")

        if self.dry_run:
            logger.info("🔍 [DRY RUN] Se extraerían documentos de solicitudes...")
            return 0

        try:
            from src.extractors.solicitudes import SolicitudesExtractor

            extractor = SolicitudesExtractor()
            total_nuevos = extractor.extract_documentos_all_solicitudes()

            logger.info(f"\n✅ Total documentos nuevos: {total_nuevos}")
            self.stats["documentos_nuevos"] = total_nuevos
            return total_nuevos

        except Exception as e:
            logger.error(f"❌ Error en extracción de documentos: {e}", exc_info=True)
            raise

    # =========================================================================
    # PASO 2: DESCARGA DE DOCUMENTOS
    # =========================================================================

    def step_3_download_documents(self, limit: int = None) -> Dict[str, int]:
        """
        Descarga documentos pendientes (SAC, SUCTD, FEHACIENTE).

        Args:
            limit: Límite de documentos a descargar por tipo

        Returns:
            Dict con conteos por tipo
        """
        self.print_section("PASO 3: Descarga de Documentos")

        if self.dry_run:
            logger.info("🔍 [DRY RUN] Se descargarían documentos pendientes...")
            return {"SAC": 0, "SUCTD": 0, "FEHACIENTE": 0}

        tipos_documento = {
            "SAC": "Formulario SAC",
            "SUCTD": "Formulario SUCTD",
            "FEHACIENTE": "Formulario_proyecto_fehaciente"
        }

        downloads_count = {}

        try:
            from src.batch_download_sac import SACBatchDownloader
            from src.batch_download_suctd import SUCTDBatchDownloader
            from src.batch_download_fehaciente import FehacienteBatchDownloader

            downloaders = {
                "SAC": SACBatchDownloader(),
                "SUCTD": SUCTDBatchDownloader(),
                "FEHACIENTE": FehacienteBatchDownloader()
            }

            for tipo, downloader in downloaders.items():
                logger.info(f"\n📥 Descargando documentos {tipo}...")
                result = downloader.run_batch_download(limit=limit)
                downloads_count[tipo] = result.get('descargados', 0)
                logger.info(f"  ✅ {downloads_count[tipo]} documentos {tipo} descargados")

            total = sum(downloads_count.values())
            logger.info(f"\n✅ Total documentos descargados: {total}")
            self.stats["documentos_descargados"] = total

            return downloads_count

        except Exception as e:
            logger.error(f"❌ Error en descarga de documentos: {e}", exc_info=True)
            raise

    # =========================================================================
    # PASO 3: PARSING DE FORMULARIOS
    # =========================================================================

    def step_4_parse_formularios(self, tipos: List[str] = None, limit: int = None) -> Dict[str, int]:
        """
        Parsea formularios pendientes (SAC, SUCTD, FEHACIENTE).

        Args:
            tipos: Lista de tipos a parsear (default: todos)
            limit: Límite de documentos a parsear por tipo

        Returns:
            Dict con conteos por tipo
        """
        self.print_section("PASO 4: Parsing de Formularios")

        if tipos is None:
            tipos = ["SAC", "SUCTD", "FEHACIENTE"]

        if self.dry_run:
            logger.info(f"🔍 [DRY RUN] Se parsearían formularios: {', '.join(tipos)}")
            return {t: 0 for t in tipos}

        parse_count = {}

        try:
            from src.batch_parse_sac import SACBatchParser
            from src.batch_parse_suctd import SUCTDBatchParser
            from src.batch_parse_fehaciente import FehacienteBatchParser

            parsers = {
                "SAC": SACBatchParser(),
                "SUCTD": SUCTDBatchParser(),
                "FEHACIENTE": FehacienteBatchParser()
            }

            for tipo in tipos:
                if tipo not in parsers:
                    logger.warning(f"⚠️  Tipo desconocido: {tipo}, saltando...")
                    continue

                logger.info(f"\n📄 Parseando formularios {tipo}...")
                parser = parsers[tipo]
                result = parser.run_batch_parsing(limit=limit)
                parse_count[tipo] = result.get('exitosos', 0)
                logger.info(f"  ✅ {parse_count[tipo]} formularios {tipo} parseados exitosamente")

            total = sum(parse_count.values())
            logger.info(f"\n✅ Total formularios parseados: {total}")
            self.stats["formularios_parseados"].update(parse_count)

            return parse_count

        except Exception as e:
            logger.error(f"❌ Error en parsing de formularios: {e}", exc_info=True)
            raise

    # =========================================================================
    # REPORTES
    # =========================================================================

    def print_final_report(self, elapsed_seconds: float):
        """Imprime reporte final consolidado."""
        self.print_header("📊 REPORTE FINAL DEL PIPELINE")

        print(f"⏱️  Tiempo total: {elapsed_seconds:.1f} segundos ({elapsed_seconds/60:.1f} minutos)\n")

        # Extracción
        print("1️⃣  EXTRACCIÓN:")
        print(f"   • Solicitudes nuevas:       {self.stats['solicitudes_nuevas']}")
        print(f"   • Documentos nuevos:        {self.stats['documentos_nuevos']}")
        print()

        # Descarga
        print("2️⃣  DESCARGA:")
        print(f"   • Documentos descargados:   {self.stats['documentos_descargados']}")
        print()

        # Parsing
        print("3️⃣  PARSING:")
        for tipo, count in self.stats['formularios_parseados'].items():
            print(f"   • {tipo:12s} parseados:  {count}")
        print()

        total_parseados = sum(self.stats['formularios_parseados'].values())
        print(f"✅ Total formularios parseados: {total_parseados}")
        print("=" * 100)

    def run_full_pipeline(self, **kwargs):
        """Ejecuta el pipeline completo."""
        start_time = datetime.now()

        self.print_header("🚀 PIPELINE COMPLETO CEN ACCESO ABIERTO")
        logger.info(f"📅 Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🔧 Modo: {'DRY RUN' if self.dry_run else 'EJECUCIÓN REAL'}")
        logger.info("")

        try:
            # Paso 1: Extracción de solicitudes
            if not kwargs.get('skip_fetch'):
                self.step_1_fetch_solicitudes()
                self.step_2_fetch_documentos()

            # Paso 2: Descarga de documentos
            if not kwargs.get('skip_download'):
                self.step_3_download_documents(limit=kwargs.get('limit'))

            # Paso 3: Parsing de formularios
            if not kwargs.get('skip_parse'):
                self.step_4_parse_formularios(
                    tipos=kwargs.get('tipos'),
                    limit=kwargs.get('limit')
                )

            # Reporte final
            elapsed = (datetime.now() - start_time).total_seconds()
            self.print_final_report(elapsed)

            return 0  # Éxito

        except KeyboardInterrupt:
            logger.warning("\n⚠️  Pipeline interrumpido por el usuario")
            return 130

        except Exception as e:
            logger.error(f"\n❌ Error fatal en pipeline: {e}", exc_info=True)
            return 1


def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description='Pipeline completo CEN Acceso Abierto',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Ejecutar todo el pipeline
  python pipeline.py

  # Solo extracción (solicitudes + documentos)
  python pipeline.py --solo-fetch

  # Solo descarga
  python pipeline.py --solo-download

  # Solo parsing
  python pipeline.py --solo-parse

  # Procesar solo SAC con límite de 100 docs
  python pipeline.py --tipos SAC --limit 100

  # Dry run (ver qué se haría sin ejecutar)
  python pipeline.py --dry-run
        """
    )

    parser.add_argument(
        '--solo-fetch',
        action='store_true',
        help='Solo extraer solicitudes y documentos (skip download y parsing)'
    )

    parser.add_argument(
        '--solo-download',
        action='store_true',
        help='Solo descargar documentos (skip fetch y parsing)'
    )

    parser.add_argument(
        '--solo-parse',
        action='store_true',
        help='Solo parsear formularios (skip fetch y download)'
    )

    parser.add_argument(
        '--tipos',
        nargs='+',
        choices=['SAC', 'SUCTD', 'FEHACIENTE'],
        help='Tipos de formularios a procesar (default: todos)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Límite de documentos a procesar por tipo (para testing)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Modo dry-run: mostrar qué se haría sin ejecutar'
    )

    args = parser.parse_args()

    # Crear orchestrator
    orchestrator = PipelineOrchestrator(dry_run=args.dry_run)

    # Ejecutar pipeline
    exit_code = orchestrator.run_full_pipeline(
        skip_fetch=args.solo_download or args.solo_parse,
        skip_download=args.solo_fetch or args.solo_parse,
        skip_parse=args.solo_fetch or args.solo_download,
        tipos=args.tipos,
        limit=args.limit
    )

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
