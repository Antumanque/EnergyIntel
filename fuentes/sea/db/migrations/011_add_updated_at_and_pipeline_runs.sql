-- =============================================================================
-- Migración 011: Agregar updated_at para upserts y tabla pipeline_runs
-- =============================================================================
-- Esta migración habilita:
-- 1. Columna updated_at en proyectos para detectar cambios (delta)
-- 2. Tabla pipeline_runs para trackear ejecuciones del pipeline
-- =============================================================================

-- 1. Agregar columna updated_at a proyectos
ALTER TABLE proyectos
ADD COLUMN updated_at TIMESTAMP NULL DEFAULT NULL
    COMMENT 'Fecha de última actualización (NULL si nunca se actualizó)',
ADD INDEX idx_updated_at (updated_at);

-- 2. Tabla para trackear ejecuciones del pipeline
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    started_at DATETIME NOT NULL COMMENT 'Inicio de la ejecución',
    finished_at DATETIME NULL COMMENT 'Fin de la ejecución (NULL si en progreso)',
    status ENUM('running', 'completed', 'failed') DEFAULT 'running' COMMENT 'Estado de la ejecución',

    -- Estadísticas de la corrida
    proyectos_nuevos INT DEFAULT 0 COMMENT 'Proyectos insertados por primera vez',
    proyectos_actualizados INT DEFAULT 0 COMMENT 'Proyectos con cambios detectados',
    proyectos_sin_cambios INT DEFAULT 0 COMMENT 'Proyectos sin cambios',
    total_procesados INT DEFAULT 0 COMMENT 'Total de proyectos procesados',

    -- Información adicional
    error_message TEXT NULL COMMENT 'Mensaje de error si falló',

    INDEX idx_started_at (started_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Historial de ejecuciones del pipeline para tracking incremental';

-- 3. Vista para obtener el delta desde la última corrida exitosa
CREATE OR REPLACE VIEW proyectos_delta AS
SELECT
    p.*,
    CASE
        WHEN p.updated_at IS NULL THEN 'nuevo'
        WHEN p.updated_at > p.fetched_at THEN 'actualizado'
        ELSE 'sin_cambios'
    END AS delta_status
FROM proyectos p
WHERE p.updated_at IS NOT NULL
   OR p.fetched_at >= (
       SELECT COALESCE(MAX(started_at), '1970-01-01')
       FROM pipeline_runs
       WHERE status = 'completed'
   );

-- 4. Vista para resumen de la última corrida
CREATE OR REPLACE VIEW ultima_pipeline_run AS
SELECT *
FROM pipeline_runs
ORDER BY started_at DESC
LIMIT 1;

-- Registrar migración
INSERT INTO schema_migrations (migration_name)
VALUES ('011_add_updated_at_and_pipeline_runs.sql')
ON DUPLICATE KEY UPDATE migration_name = migration_name;
