#!/usr/bin/env python3
"""
Script de descarga masiva de formularios SUCTD (PDF y XLSX).

Este script:
1. Obtiene lista de documentos SUCTD NO descargados
2. Descarga cada documento usando presigned URLs
3. Actualiza estado en base de datos
4. Genera estadísticas de éxito/error

Uso:
    python -m src.batch_download_suctd [--limit N] [--dry-run]

Ejemplos:
    # Descargar primeros 10 documentos (prueba)
    python -m src.batch_download_suctd --limit 10

    # Descargar todos los documentos SUCTD
    python -m src.batch_download_suctd

    # Ver qué se descargaría sin ejecutar
    python -m src.batch_download_suctd --dry-run --limit 20

Fecha: 2025-10-20
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.downloaders.documents import DocumentDownloader
from src.repositories.cen import get_cen_db_manager
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SUCTDBatchDownloader:
    """Descargador masivo de formularios SUCTD."""

    def __init__(self):
        """Inicializa el descargador masivo."""
        self.db = get_cen_db_manager()
        self.settings = get_settings()
        self.downloader = DocumentDownloader(
            settings=self.settings,
            downloads_dir="downloads",
            timeout=60,
            max_retries=3
        )

        # Estadísticas
        self.stats = {
            "total": 0,
            "exitosos": 0,
            "fallidos": 0,
            "ya_descargados": 0,
            "errores": [],
            "por_formato": {"PDF": 0, "XLSX": 0, "XLS": 0, "OTRO": 0}
        }

    def get_pending_downloads(self, limit: int = None) -> List[Dict]:
        """
        Obtiene lista de documentos SUCTD NO descargados.

        Args:
            limit: Máximo número de documentos a retornar (None = todos)

        Returns:
            Lista de diccionarios con info de documentos
        """
        # Obtener años configurados (si no hay config, usar año actual)
        years = self.settings.cen_years_list if self.settings.cen_years_list else [datetime.now().year]
        year_filter = f"AND YEAR(d.create_date) IN ({','.join(map(str, years))})"

        query = f"""
        SELECT
            d.id,
            d.solicitud_id,
            d.nombre,
            d.ruta_s3,
            d.downloaded,
            CASE
                WHEN d.nombre LIKE '%.pdf' THEN 'PDF'
                WHEN d.nombre LIKE '%.xlsx' THEN 'XLSX'
                WHEN d.nombre LIKE '%.xls' THEN 'XLS'
                ELSE 'OTRO'
            END AS formato_archivo
        FROM documentos d
        WHERE d.tipo_documento = 'Formulario SUCTD'
          AND d.visible = 1
          AND d.deleted = 0
          AND (d.downloaded = 0 OR d.downloaded IS NULL)
          {year_filter}
        ORDER BY d.id ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        with self.db.connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            docs = cursor.fetchall()

        logger.info(f"📋 Encontrados {len(docs)} documentos SUCTD pendientes de descargar")

        return docs

    def download_document(self, doc: Dict) -> bool:
        """
        Descarga un documento individual.

        Args:
            doc: Diccionario con info del documento

        Returns:
            True si fue exitoso, False en caso contrario
        """
        documento_id = doc["id"]
        solicitud_id = doc["solicitud_id"]
        nombre = doc["nombre"]
        ruta_s3 = doc["ruta_s3"]
        formato_archivo = doc["formato_archivo"]

        logger.info(f"📥 Descargando doc {documento_id} ({formato_archivo}): {nombre[:50]}...")

        try:
            # Descargar el archivo
            success, local_path, error_msg = self.downloader.download_document(
                ruta_s3=ruta_s3,
                solicitud_id=solicitud_id,
                documento_id=documento_id,
                filename=nombre
            )

            if success:
                # Actualizar BD: marcar como descargado
                with self.db.connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE documentos
                        SET downloaded = 1,
                            downloaded_at = NOW(),
                            local_path = %s
                        WHERE id = %s
                    """, (local_path, documento_id))
                    conn.commit()

                logger.info(f"✅ Doc {documento_id} descargado: {local_path}")
                return True
            else:
                # Actualizar BD: marcar error de descarga
                with self.db.connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE documentos
                        SET download_error = %s
                        WHERE id = %s
                    """, (error_msg, documento_id))
                    conn.commit()

                logger.error(f"❌ Doc {documento_id} falló: {error_msg}")
                self.stats["errores"].append({
                    "documento_id": documento_id,
                    "nombre": nombre,
                    "formato": formato_archivo,
                    "error": error_msg
                })
                return False

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Doc {documento_id}: Excepción - {error_msg}", exc_info=True)
            self.stats["errores"].append({
                "documento_id": documento_id,
                "nombre": nombre,
                "formato": formato_archivo,
                "error": error_msg
            })
            return False

    def run_batch_download(self, limit: int = None, dry_run: bool = False) -> Dict:
        """
        Ejecuta descarga masiva de documentos.

        Args:
            limit: Máximo número de documentos a descargar (None = todos)
            dry_run: Si True, solo muestra qué se descargaría sin ejecutar

        Returns:
            Diccionario con estadísticas finales
        """
        logger.info("=" * 70)
        logger.info("🚀 DESCARGA MASIVA DE FORMULARIOS SUCTD")
        logger.info("=" * 70)
        logger.info(f"Modo: {'DRY RUN' if dry_run else 'EJECUCIÓN REAL'}")
        logger.info(f"Límite: {limit if limit else 'Sin límite'}")
        logger.info("")

        # Paso 1: Obtener documentos pendientes
        docs = self.get_pending_downloads(limit=limit)

        if not docs:
            logger.info("✅ No hay documentos pendientes de descargar")
            return self.stats

        self.stats["total"] = len(docs)

        # Mostrar preview
        logger.info("\n📋 Documentos a descargar:")
        logger.info("-" * 70)

        format_counts = {}
        for doc in docs:
            fmt = doc["formato_archivo"]
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        for fmt, count in format_counts.items():
            logger.info(f"  {fmt:4s}: {count:4d} documentos")

        logger.info("\nPrimeros 10:")
        for i, doc in enumerate(docs[:10], 1):
            logger.info(
                f"{i:3d}. ID {doc['id']:5d} | {doc['formato_archivo']:4s} | "
                f"{doc['nombre'][:50]}"
            )

        if len(docs) > 10:
            logger.info(f"     ... y {len(docs) - 10} más")

        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN - No se descargará nada")
            return self.stats

        # Paso 2: Descargar cada documento
        start_time = time.time()

        for i, doc in enumerate(docs, 1):
            logger.info(f"\n[{i}/{len(docs)}] Procesando documento {doc['id']}...")

            success = self.download_document(doc)

            if success:
                self.stats["exitosos"] += 1
                self.stats["por_formato"][doc["formato_archivo"]] += 1
            else:
                self.stats["fallidos"] += 1

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

            # Pequeña pausa para no saturar el servidor
            time.sleep(0.5)

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
        logger.info(f"✅ Descargados exitosos: {self.stats['exitosos']}")
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
        description="Descarga masiva de formularios SUCTD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Descargar primeros 10 documentos (prueba)
  python -m src.batch_download_suctd --limit 10

  # Descargar todos los documentos SUCTD
  python -m src.batch_download_suctd

  # Ver qué se descargaría sin ejecutar
  python -m src.batch_download_suctd --dry-run --limit 50
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo número de documentos a descargar (default: todos)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se descargaría sin ejecutar"
    )

    args = parser.parse_args()

    # Ejecutar descarga masiva
    batch_downloader = SUCTDBatchDownloader()
    stats = batch_downloader.run_batch_download(
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Exit code basado en resultados
    if stats["total"] == 0:
        sys.exit(0)  # No había nada que descargar
    elif stats["fallidos"] == 0:
        sys.exit(0)  # Todo exitoso
    elif stats["exitosos"] > stats["fallidos"]:
        sys.exit(0)  # Mayoría exitosa
    else:
        sys.exit(1)  # Mayoría falló


if __name__ == "__main__":
    main()
