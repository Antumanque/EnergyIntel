-- =============================================================================
-- Migración 012: Agregar last_pipeline_run_id para tracking preciso
-- =============================================================================
-- Esta columna permite saber exactamente qué pipeline run modificó cada registro
-- Útil para queries como:
--   SELECT * FROM proyectos WHERE last_pipeline_run_id = (SELECT MAX(id) FROM pipeline_runs);
-- =============================================================================

-- 1. Agregar columna last_pipeline_run_id a proyectos
ALTER TABLE proyectos
ADD COLUMN last_pipeline_run_id INT NULL
    COMMENT 'ID del último pipeline_run que modificó este registro',
ADD INDEX idx_last_pipeline_run_id (last_pipeline_run_id),
ADD CONSTRAINT fk_proyectos_pipeline_run
    FOREIGN KEY (last_pipeline_run_id) REFERENCES pipeline_runs(id)
    ON DELETE SET NULL;

-- 2. Inicializar registros existentes con el último run completado (si existe)
UPDATE proyectos p
SET p.last_pipeline_run_id = (
    SELECT MAX(id) FROM pipeline_runs WHERE status = 'completed'
)
WHERE p.last_pipeline_run_id IS NULL;
