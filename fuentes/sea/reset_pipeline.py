"""
Reset Pipeline - Limpia etapas del pipeline para empezar de nuevo.

Este script permite limpiar selectivamente etapas del pipeline,
útil para iterar y mejorar parsers sin perder los datos de etapas anteriores.

Uso:
    # Limpiar solo Etapa 3 (mantener proyectos y documentos)
    python reset_pipeline.py --stage 3
    
    # Limpiar Etapa 2 y 3 (mantener solo proyectos)
    python reset_pipeline.py --stage 2
    
    # Limpiar TODO el pipeline
    python reset_pipeline.py --all
    
    # Modo dry-run (ver qué se va a borrar sin borrar)
    python reset_pipeline.py --stage 3 --dry-run
"""
import argparse
import logging
from src.core.database import get_database_manager
from src.settings import get_settings

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def reset_stage_3(db, dry_run=False):
    """Limpiar Etapa 3: Links a PDF resumen ejecutivo."""
    logger.info("\n🗑️  LIMPIANDO ETAPA 3: LINKS A PDF RESUMEN EJECUTIVO")
    logger.info("=" * 80)
    
    # Contar registros
    count = db.fetch_one("SELECT COUNT(*) as total FROM resumen_ejecutivo_links", dictionary=True)
    logger.info(f"Registros a borrar: {count['total']}")
    
    if dry_run:
        logger.info("🔍 DRY-RUN: No se borrará nada")
        return
    
    # Confirmar
    logger.info("\n⚠️  ADVERTENCIA: Esta acción no se puede deshacer")
    confirm = input("¿Continuar? (escribe 'si' para confirmar): ")
    
    if confirm.lower() != 'si':
        logger.info("❌ Cancelado por el usuario")
        return
    
    # Limpiar
    db.execute_query("DELETE FROM resumen_ejecutivo_links", commit=True)
    logger.info("✓ Etapa 3 limpiada correctamente\n")

def reset_stage_2(db, dry_run=False):
    """Limpiar Etapa 2: Documentos del expediente (y automáticamente Etapa 3)."""
    logger.info("\n🗑️  LIMPIANDO ETAPA 2: DOCUMENTOS DEL EXPEDIENTE")
    logger.info("=" * 80)
    
    # Contar registros
    count_docs = db.fetch_one("SELECT COUNT(*) as total FROM expediente_documentos", dictionary=True)
    count_links = db.fetch_one("SELECT COUNT(*) as total FROM resumen_ejecutivo_links", dictionary=True)
    
    logger.info(f"Documentos a borrar:    {count_docs['total']}")
    logger.info(f"Links a borrar (E3):    {count_links['total']}")
    logger.info(f"Total de registros:     {count_docs['total'] + count_links['total']}")
    
    if dry_run:
        logger.info("\n🔍 DRY-RUN: No se borrará nada")
        return
    
    # Confirmar
    logger.info("\n⚠️  ADVERTENCIA: Esta acción borrará Etapas 2 y 3 (no se puede deshacer)")
    confirm = input("¿Continuar? (escribe 'si' para confirmar): ")
    
    if confirm.lower() != 'si':
        logger.info("❌ Cancelado por el usuario")
        return
    
    # Limpiar (en orden: primero FK, luego tabla referenciada)
    logger.info("\nBorrando Etapa 3...")
    db.execute_query("DELETE FROM resumen_ejecutivo_links", commit=True)
    logger.info("✓ Etapa 3 borrada")

    logger.info("Borrando Etapa 2...")
    db.execute_query("DELETE FROM expediente_documentos", commit=True)
    logger.info("✓ Etapa 2 borrada\n")

def reset_all(db, dry_run=False):
    """Limpiar TODO el pipeline."""
    logger.info("\n🗑️  LIMPIANDO TODO EL PIPELINE")
    logger.info("=" * 80)
    
    # Contar registros
    count_proyectos = db.fetch_one("SELECT COUNT(*) as total FROM proyectos", dictionary=True)
    count_raw = db.fetch_one("SELECT COUNT(*) as total FROM raw_data", dictionary=True)
    count_docs = db.fetch_one("SELECT COUNT(*) as total FROM expediente_documentos", dictionary=True)
    count_links = db.fetch_one("SELECT COUNT(*) as total FROM resumen_ejecutivo_links", dictionary=True)
    
    logger.info(f"Proyectos (E1):         {count_proyectos['total']}")
    logger.info(f"Raw data (E1):          {count_raw['total']}")
    logger.info(f"Documentos (E2):        {count_docs['total']}")
    logger.info(f"Links (E3):             {count_links['total']}")
    total = count_proyectos['total'] + count_raw['total'] + count_docs['total'] + count_links['total']
    logger.info(f"Total de registros:     {total}")
    
    if dry_run:
        logger.info("\n🔍 DRY-RUN: No se borrará nada")
        return
    
    # Confirmar
    logger.info("\n⚠️  ADVERTENCIA: Esta acción borrará TODO el pipeline (no se puede deshacer)")
    logger.info("⚠️  Tendrás que volver a extraer los 29,887 proyectos desde la API")
    confirm = input("¿Continuar? (escribe 'SI ESTOY SEGURO' para confirmar): ")
    
    if confirm != 'SI ESTOY SEGURO':
        logger.info("❌ Cancelado por el usuario")
        return
    
    # Limpiar (en orden inverso de dependencias)
    logger.info("\nBorrando Etapa 3...")
    db.execute_query("DELETE FROM resumen_ejecutivo_links", commit=True)
    logger.info("✓ Etapa 3 borrada")

    logger.info("Borrando Etapa 2...")
    db.execute_query("DELETE FROM expediente_documentos", commit=True)
    logger.info("✓ Etapa 2 borrada")

    logger.info("Borrando Etapa 1...")
    db.execute_query("DELETE FROM proyectos", commit=True)
    logger.info("✓ Proyectos borrados")

    db.execute_query("DELETE FROM raw_data", commit=True)
    logger.info("✓ Raw data borrado\n")

def main():
    parser = argparse.ArgumentParser(description="Reset pipeline SEA")
    parser.add_argument("--stage", type=int, choices=[2, 3], help="Etapa a limpiar (2 o 3)")
    parser.add_argument("--all", action="store_true", help="Limpiar TODO el pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Ver qué se va a borrar sin borrar")
    args = parser.parse_args()
    
    if not args.stage and not args.all:
        parser.error("Debes especificar --stage o --all")
    
    if args.stage and args.all:
        parser.error("No puedes usar --stage y --all al mismo tiempo")
    
    settings = get_settings()
    db = get_database_manager(settings)
    
    if args.all:
        reset_all(db, args.dry_run)
    elif args.stage == 3:
        reset_stage_3(db, args.dry_run)
    elif args.stage == 2:
        reset_stage_2(db, args.dry_run)
    
    db.close_connection()
    
    if not args.dry_run:
        logger.info("✓ Limpieza completada")
        logger.info("\nPara procesar de nuevo, ejecuta:")
        if args.stage == 3:
            logger.info("  python batch_processor.py --batch-size 1000 --stage 3")
        elif args.stage == 2:
            logger.info("  python batch_processor.py --batch-size 1000 --stage 2")
        elif args.all:
            logger.info("  python -m src.main  # Para extraer proyectos (Etapa 1)")

if __name__ == "__main__":
    main()
