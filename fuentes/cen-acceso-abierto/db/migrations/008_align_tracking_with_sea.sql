-- =============================================================================
-- Migración 008: Alinear tracking de CEN con estándar SEA
-- =============================================================================
-- Estandariza el tracking de cambios entre proyectos:
--   - fetched_at: cuándo se insertó por primera vez (nunca cambia)
--   - updated_at: cuándo detectamos cambios reales (NULL si nunca, manual)
--   - last_pipeline_run_id: qué pipeline modificó el registro
-- =============================================================================

-- 1. Renombrar created_at → fetched_at en solicitudes
ALTER TABLE solicitudes
CHANGE COLUMN created_at fetched_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
    COMMENT 'Fecha de primera extracción de la API (nunca cambia)';

-- 2. Modificar updated_at para que NO sea auto-update
--    Primero guardamos los valores actuales, luego recreamos la columna
ALTER TABLE solicitudes
MODIFY COLUMN updated_at DATETIME NULL DEFAULT NULL
    COMMENT 'Fecha de última actualización con cambios reales (NULL si nunca se actualizó)';

-- 3. Agregar last_pipeline_run_id a solicitudes
ALTER TABLE solicitudes
ADD COLUMN last_pipeline_run_id INT NULL
    COMMENT 'ID del último pipeline_run que modificó este registro',
ADD INDEX idx_last_pipeline_run_id (last_pipeline_run_id),
ADD CONSTRAINT fk_solicitudes_pipeline_run
    FOREIGN KEY (last_pipeline_run_id) REFERENCES pipeline_runs(id)
    ON DELETE SET NULL;

-- 4. Hacer lo mismo para documentos
ALTER TABLE documentos
CHANGE COLUMN created_at fetched_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
    COMMENT 'Fecha de primera extracción de la API (nunca cambia)';

ALTER TABLE documentos
MODIFY COLUMN updated_at DATETIME NULL DEFAULT NULL
    COMMENT 'Fecha de última actualización con cambios reales (NULL si nunca se actualizó)';

ALTER TABLE documentos
ADD COLUMN last_pipeline_run_id INT NULL
    COMMENT 'ID del último pipeline_run que modificó este registro',
ADD INDEX idx_doc_last_pipeline_run_id (last_pipeline_run_id),
ADD CONSTRAINT fk_documentos_pipeline_run
    FOREIGN KEY (last_pipeline_run_id) REFERENCES pipeline_runs(id)
    ON DELETE SET NULL;

-- 5. Inicializar last_pipeline_run_id con el último run completado (si existe)
UPDATE solicitudes s
SET s.last_pipeline_run_id = (
    SELECT MAX(id) FROM pipeline_runs WHERE status = 'completed'
)
WHERE s.last_pipeline_run_id IS NULL
  AND EXISTS (SELECT 1 FROM pipeline_runs WHERE status = 'completed');

UPDATE documentos d
SET d.last_pipeline_run_id = (
    SELECT MAX(id) FROM pipeline_runs WHERE status = 'completed'
)
WHERE d.last_pipeline_run_id IS NULL
  AND EXISTS (SELECT 1 FROM pipeline_runs WHERE status = 'completed');

-- =============================================================================
-- Vistas útiles para tracking de cambios entre runs
-- =============================================================================

-- Vista: solicitudes del último pipeline run
CREATE OR REPLACE VIEW solicitudes_ultimo_run AS
SELECT s.*
FROM solicitudes s
WHERE s.last_pipeline_run_id = (
    SELECT MAX(id) FROM pipeline_runs WHERE status = 'completed'
);

-- Vista: solicitudes con delta status
CREATE OR REPLACE VIEW solicitudes_delta AS
SELECT
    s.*,
    CASE
        WHEN s.updated_at IS NULL THEN 'nuevo'
        WHEN s.updated_at > s.fetched_at THEN 'actualizado'
        ELSE 'sin_cambios'
    END AS delta_status
FROM solicitudes s;

-- =============================================================================
-- Fin de migración
-- =============================================================================
