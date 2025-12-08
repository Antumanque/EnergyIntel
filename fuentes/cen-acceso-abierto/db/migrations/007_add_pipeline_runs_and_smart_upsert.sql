-- ============================================================================
-- Migración 007: Pipeline runs tracking + UPSERT inteligente
-- ============================================================================
-- 1. Tabla pipeline_runs: tracking de cada ejecución del pipeline
-- 2. Columnas para detectar cambios reales en solicitudes/documentos
-- ============================================================================

-- Tabla: pipeline_runs
-- Registra cada ejecución del pipeline con estadísticas
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',

    -- Estadísticas de solicitudes
    solicitudes_en_api INT DEFAULT 0 COMMENT 'Total solicitudes en la API',
    solicitudes_nuevas INT DEFAULT 0 COMMENT 'Solicitudes insertadas',
    solicitudes_actualizadas INT DEFAULT 0 COMMENT 'Solicitudes con cambios',
    solicitudes_sin_cambios INT DEFAULT 0 COMMENT 'Solicitudes sin cambios',

    -- Estadísticas de documentos
    documentos_nuevos INT DEFAULT 0 COMMENT 'Documentos insertados',
    documentos_actualizados INT DEFAULT 0 COMMENT 'Documentos con cambios',

    -- Estadísticas de descarga y parsing
    documentos_descargados INT DEFAULT 0,
    formularios_parseados_sac INT DEFAULT 0,
    formularios_parseados_suctd INT DEFAULT 0,
    formularios_parseados_fehaciente INT DEFAULT 0,

    -- Metadata
    error_message TEXT NULL COMMENT 'Mensaje de error si falló',
    duration_seconds INT NULL COMMENT 'Duración total en segundos',

    INDEX idx_started_at (started_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracking de ejecuciones del pipeline';

-- ============================================================================
-- Agregar columna para trackear el último pipeline_run que modificó el registro
-- ============================================================================

ALTER TABLE solicitudes
ADD COLUMN last_pipeline_run_id INT NULL COMMENT 'ID del pipeline_run que modificó este registro',
ADD INDEX idx_last_pipeline_run (last_pipeline_run_id);

ALTER TABLE documentos
ADD COLUMN last_pipeline_run_id INT NULL COMMENT 'ID del pipeline_run que modificó este registro',
ADD INDEX idx_last_pipeline_run (last_pipeline_run_id);
