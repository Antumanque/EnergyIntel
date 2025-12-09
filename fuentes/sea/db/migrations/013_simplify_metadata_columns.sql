-- ============================================================================
-- Migracion 013: Simplificar columnas de metadata
-- ============================================================================
-- Cambios:
--   1. Eliminar last_pipeline_run_id (redundante con tabla pipeline_runs)
--
-- Razon: Consistencia con otros proyectos (cen-acceso-abierto)
--   - created_at: cuando insertamos el registro (ya existe)
--   - updated_at: cuando modificamos el registro localmente (ya existe)
--   - last_pipeline_run_id: eliminado (redundante con pipeline_runs)
-- ============================================================================

-- Eliminar last_pipeline_run_id (FK, indice y columna)
ALTER TABLE proyectos DROP FOREIGN KEY IF EXISTS fk_proyectos_pipeline_run;
ALTER TABLE proyectos DROP INDEX IF EXISTS idx_last_pipeline_run_id;
ALTER TABLE proyectos DROP COLUMN IF EXISTS last_pipeline_run_id;

-- ============================================================================
-- Nota: La tabla pipeline_runs se mantiene para tracking de ejecuciones.
-- Solo eliminamos la FK redundante en cada registro individual.
-- ============================================================================
