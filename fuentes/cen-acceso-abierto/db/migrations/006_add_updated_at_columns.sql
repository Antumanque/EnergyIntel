-- ============================================================================
-- Migración 006: Agregar columna updated_at para tracking de cambios locales
-- ============================================================================
-- Esta columna permite detectar qué registros fueron modificados desde la
-- última ejecución del pipeline.
--
-- Diferencia con otros campos:
--   - fetched_at: cuándo se insertó el registro por primera vez
--   - update_date: cuándo el CEN actualizó el registro (viene de la API)
--   - updated_at: cuándo se modificó el registro en nuestra BD (INSERT o UPDATE)
-- ============================================================================

-- Agregar updated_at a solicitudes
ALTER TABLE solicitudes
ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
COMMENT 'Última modificación en nuestra BD (auto-update)';

-- Agregar índice para queries por fecha de cambio
ALTER TABLE solicitudes ADD INDEX idx_updated_at (updated_at);

-- Agregar updated_at a documentos
ALTER TABLE documentos
ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
COMMENT 'Última modificación en nuestra BD (auto-update)';

-- Agregar índice para queries por fecha de cambio
ALTER TABLE documentos ADD INDEX idx_updated_at (updated_at);

-- ============================================================================
-- Inicializar updated_at para registros existentes con fetched_at
-- ============================================================================
UPDATE solicitudes SET updated_at = fetched_at WHERE updated_at IS NULL;
UPDATE documentos SET updated_at = fetched_at WHERE updated_at IS NULL;
