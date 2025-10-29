#!/usr/bin/env python3
"""
Script de parseo masivo de formularios SUCTD (PDF y XLSX).

Este script:
1. Obtiene lista de documentos SUCTD descargados pero NO parseados
2. Parsea cada documento (PDF o XLSX)
3. Guarda resultados en base de datos
4. Genera estadísticas de éxito/error

Uso:
    python -m src.batch_parse_suctd [--limit N] [--dry-run]

Ejemplos:
    # Parsear primeros 10 documentos (prueba)
    python -m src.batch_parse_suctd --limit 10

    # Parsear todos los documentos
    python -m src.batch_parse_suctd

    # Ver qué se parsearía sin ejecutar
    python -m src.batch_parse_suctd --dry-run

Fecha: 2025-10-20
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from src.repositories.cen import get_cen_db_manager
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SUCTDBatchParser:
    """Parseador masivo de formularios SUCTD."""

    def __init__(self, db_manager=None):
        """Inicializa el parseador masivo."""
        self.db = db_manager or get_cen_db_manager()
        self.settings = get_settings()

        # Estadísticas
        self.stats = {
            "total": 0,
            "exitosos": 0,
            "fallidos": 0,
            "errores": [],
            "por_formato": {"PDF": 0, "XLSX": 0, "XLS": 0, "ZIP": 0}
        }

    def get_pending_documents(self, limit: int = None) -> List[Dict]:
        """
        Obtiene lista de documentos SUCTD descargados pero NO parseados.

        Args:
            limit: Máximo número de documentos a retornar (None = todos)

        Returns:
            Lista de diccionarios con info de documentos
        """
        query = """
        SELECT
            d.id,
            d.solicitud_id,
            d.nombre,
            d.local_path,
            d.formato_archivo
        FROM documentos_listos_para_parsear d
        WHERE d.tipo_documento = 'Formulario SUCTD'
          AND d.downloaded = 1
          AND d.id NOT IN (
              SELECT documento_id
              FROM formularios_parseados
              WHERE parsing_exitoso = 1
          )
        ORDER BY d.id ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        with self.db.connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            docs = cursor.fetchall()

        logger.info(f"📋 Encontrados {len(docs)} documentos SUCTD pendientes de parsear")

        return docs

    def parse_document(self, doc: Dict) -> Tuple[bool, str]:
        """
        Parsea un documento individual.

        Args:
            doc: Diccionario con info del documento

        Returns:
            Tupla (success: bool, error_msg: str)
        """
        documento_id = doc["id"]
        solicitud_id = doc["solicitud_id"]
        local_path = doc["local_path"]
        formato_archivo = doc["formato_archivo"]

        # Construir path completo
        downloads_dir = Path("downloads")
        full_path = downloads_dir / local_path

        # Verificar que existe
        if not full_path.exists():
            error_msg = f"Archivo no encontrado: {full_path}"
            logger.error(f"❌ Doc {documento_id}: {error_msg}")
            return False, error_msg

        try:
            # Parsear y guardar
            logger.info(f"📄 Parseando doc {documento_id} ({formato_archivo}): {doc['nombre'][:50]}...")

            success = self.db.parse_and_store_suctd_document(
                documento_id=documento_id,
                solicitud_id=solicitud_id,
                local_path=str(full_path),
                formato_archivo=formato_archivo
            )

            if success:
                logger.info(f"✅ Doc {documento_id} parseado exitosamente")
                return True, None
            else:
                error_msg = "Parsing falló (campos críticos faltantes o error desconocido)"
                logger.warning(f"⚠️  Doc {documento_id}: {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Doc {documento_id}: Error - {error_msg}", exc_info=True)
            return False, error_msg

    def run_batch_parsing(self, limit: int = None, dry_run: bool = False) -> Dict:
        """
        Ejecuta parseo masivo de documentos.

        Args:
            limit: Máximo número de documentos a parsear (None = todos)
            dry_run: Si True, solo muestra qué se parsearía sin ejecutar

        Returns:
            Diccionario con estadísticas finales
        """
        logger.info("=" * 70)
        logger.info("🚀 PARSEO MASIVO DE FORMULARIOS SUCTD")
        logger.info("=" * 70)
        logger.info(f"Modo: {'DRY RUN' if dry_run else 'EJECUCIÓN REAL'}")
        logger.info(f"Límite: {limit if limit else 'Sin límite'}")
        logger.info("")

        # Paso 1: Obtener documentos pendientes
        docs = self.get_pending_documents(limit=limit)

        if not docs:
            logger.info("✅ No hay documentos pendientes de parsear")
            return self.stats

        self.stats["total"] = len(docs)

        # Mostrar preview
        logger.info("\n📋 Documentos a parsear:")
        logger.info("-" * 70)
        for i, doc in enumerate(docs[:10], 1):
            logger.info(
                f"{i:3d}. ID {doc['id']:5d} | {doc['formato_archivo']:4s} | "
                f"{doc['nombre'][:50]}"
            )

        if len(docs) > 10:
            logger.info(f"     ... y {len(docs) - 10} más")

        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN - No se parseará nada")
            return self.stats

        # Paso 2: Parsear cada documento
        start_time = time.time()

        for i, doc in enumerate(docs, 1):
            logger.info(f"\n[{i}/{len(docs)}] Procesando documento {doc['id']}...")

            success, error_msg = self.parse_document(doc)

            if success:
                self.stats["exitosos"] += 1
                self.stats["por_formato"][doc["formato_archivo"]] += 1
            else:
                self.stats["fallidos"] += 1
                self.stats["errores"].append({
                    "documento_id": doc["id"],
                    "nombre": doc["nombre"],
                    "formato": doc["formato_archivo"],
                    "error": error_msg
                })

            # Mostrar progreso cada 50 documentos
            if i % 50 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(docs) - i) / rate if rate > 0 else 0
                logger.info(
                    f"📊 Progreso: {i}/{len(docs)} ({i/len(docs)*100:.1f}%) | "
                    f"Éxito: {self.stats['exitosos']} | "
                    f"Falla: {self.stats['fallidos']} | "
                    f"Tiempo restante: {remaining/60:.1f} min"
                )

        # Paso 3: Reporte final
        elapsed = time.time() - start_time
        self._print_final_report(elapsed)

        return self.stats

    def _print_final_report(self, elapsed_seconds: float):
        """Imprime reporte final de estadísticas."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 REPORTE FINAL")
        logger.info("=" * 70)
        logger.info(f"Total documentos:        {self.stats['total']}")
        logger.info(f"✅ Parseados exitosos:   {self.stats['exitosos']}")
        logger.info(f"❌ Fallidos:             {self.stats['fallidos']}")
        logger.info("")

        if self.stats["total"] > 0:
            tasa_exito = (self.stats["exitosos"] / self.stats["total"]) * 100
            logger.info(f"Tasa de éxito:           {tasa_exito:.2f}%")

        logger.info("")
        logger.info("Por formato:")
        for formato, count in self.stats["por_formato"].items():
            if count > 0:
                logger.info(f"  {formato:4s}: {count:4d}")

        logger.info("")
        logger.info(f"Tiempo total:            {elapsed_seconds:.1f} segundos")

        if self.stats["total"] > 0:
            rate = self.stats["total"] / elapsed_seconds
            logger.info(f"Velocidad:               {rate:.2f} docs/seg")

        # Mostrar errores más comunes
        if self.stats["errores"]:
            logger.info("\n" + "=" * 70)
            logger.info("❌ ERRORES ENCONTRADOS")
            logger.info("=" * 70)

            # Mostrar primeros 10 errores
            for i, error in enumerate(self.stats["errores"][:10], 1):
                logger.info(f"\n{i}. Documento {error['documento_id']} ({error['formato']})")
                logger.info(f"   Archivo: {error['nombre'][:60]}")
                logger.info(f"   Error: {error['error'][:100]}")

            if len(self.stats["errores"]) > 10:
                logger.info(f"\n... y {len(self.stats['errores']) - 10} errores más")

            # Agrupar errores por tipo
            error_types = {}
            for error in self.stats["errores"]:
                error_msg = error["error"][:50] if error["error"] else "Unknown"
                error_types[error_msg] = error_types.get(error_msg, 0) + 1

            logger.info("\n📋 Errores por tipo:")
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                logger.info(f"  {count:3d}x: {error_type}")

        logger.info("\n" + "=" * 70)


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Parseo masivo de formularios SUCTD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Parsear primeros 10 documentos (prueba)
  python -m src.batch_parse_suctd --limit 10

  # Parsear todos los documentos
  python -m src.batch_parse_suctd

  # Ver qué se parsearía sin ejecutar
  python -m src.batch_parse_suctd --dry-run --limit 50
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo número de documentos a parsear (default: todos)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se parsearía sin ejecutar"
    )

    args = parser.parse_args()

    # Ejecutar parseo masivo
    batch_parser = SUCTDBatchParser()
    stats = batch_parser.run_batch_parsing(
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Exit code basado en resultados
    if stats["total"] == 0:
        sys.exit(0)  # No había nada que parsear
    elif stats["fallidos"] == 0:
        sys.exit(0)  # Todo exitoso
    elif stats["exitosos"] > stats["fallidos"]:
        sys.exit(0)  # Mayoría exitosa
    else:
        sys.exit(1)  # Mayoría falló


if __name__ == "__main__":
    main()
