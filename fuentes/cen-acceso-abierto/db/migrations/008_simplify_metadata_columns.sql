-- ============================================================================
-- Migracion 008: Simplificar columnas de metadata
-- ============================================================================
-- Cambios:
--   1. Renombrar fetched_at -> created_at (convencion estandar)
--   2. Renombrar update_date -> api_update_date (claridad: es timestamp del CEN)
--   3. Eliminar last_pipeline_run_id (redundante con tabla pipeline_runs)
--
-- Razon: Reducir confusion entre timestamps locales vs API
--   - created_at: cuando insertamos el registro (antes fetched_at)
--   - updated_at: cuando modificamos el registro localmente
--   - api_update_date: cuando el CEN modifico el registro (viene de la API)
-- ============================================================================

-- ============================================================================
-- SOLICITUDES
-- ============================================================================

-- 1. Renombrar fetched_at -> created_at
ALTER TABLE solicitudes
CHANGE COLUMN fetched_at created_at DATETIME DEFAULT CURRENT_TIMESTAMP
COMMENT 'Cuando se inserto el registro por primera vez';

-- 2. Renombrar update_date -> api_update_date
ALTER TABLE solicitudes
CHANGE COLUMN update_date api_update_date DATETIME NULL
COMMENT 'Timestamp de modificacion del CEN (viene de la API)';

-- 3. Eliminar last_pipeline_run_id (y su indice)
ALTER TABLE solicitudes DROP INDEX idx_last_pipeline_run;
ALTER TABLE solicitudes DROP COLUMN last_pipeline_run_id;

-- ============================================================================
-- DOCUMENTOS
-- ============================================================================

-- 1. Renombrar fetched_at -> created_at
ALTER TABLE documentos
CHANGE COLUMN fetched_at created_at DATETIME DEFAULT CURRENT_TIMESTAMP
COMMENT 'Cuando se inserto el registro por primera vez';

-- 2. Renombrar update_date -> api_update_date
ALTER TABLE documentos
CHANGE COLUMN update_date api_update_date DATETIME NULL
COMMENT 'Timestamp de modificacion del CEN (viene de la API)';

-- 3. Eliminar last_pipeline_run_id (y su indice)
ALTER TABLE documentos DROP INDEX idx_last_pipeline_run;
ALTER TABLE documentos DROP COLUMN last_pipeline_run_id;

-- ============================================================================
-- Nota: La tabla pipeline_runs se mantiene para tracking de ejecuciones.
-- Solo eliminamos la FK redundante en cada registro individual.
-- ============================================================================
