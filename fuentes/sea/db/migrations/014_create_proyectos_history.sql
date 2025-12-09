-- ============================================================================
-- Migración 014: Crear tabla de historial de cambios
-- ============================================================================
-- Registra cada INSERT y UPDATE de proyectos para auditoría y análisis.
--
-- Casos de uso:
--   - Ver qué proyectos cambiaron de estado en un período
--   - Auditar cuándo se detectó un proyecto por primera vez
--   - Analizar patrones de cambio (ej: proyectos que cambian frecuentemente)
-- ============================================================================

CREATE TABLE IF NOT EXISTS proyectos_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Referencia al proyecto
    expediente_id BIGINT NOT NULL,

    -- Tipo de operación
    operation ENUM('INSERT', 'UPDATE') NOT NULL,

    -- Cuándo ocurrió el cambio
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Pipeline run que detectó el cambio (NULL si fue manual)
    pipeline_run_id INT NULL,

    -- Campos que cambiaron (solo para UPDATE)
    -- Formato: [{"field": "estado_proyecto", "old": "En Evaluación", "new": "Aprobado"}, ...]
    changed_fields JSON NULL,

    -- Snapshot de campos clave al momento del cambio
    expediente_nombre VARCHAR(500) NULL,
    workflow_descripcion VARCHAR(50) NULL,
    region_nombre VARCHAR(100) NULL,
    tipo_proyecto VARCHAR(50) NULL,
    titular VARCHAR(255) NULL,
    estado_proyecto VARCHAR(100) NULL,
    actividad_actual VARCHAR(255) NULL,
    etapa VARCHAR(100) NULL,
    inversion_mm DECIMAL(20,4) NULL,

    -- Índices para queries comunes
    INDEX idx_history_expediente (expediente_id),
    INDEX idx_history_operation (operation),
    INDEX idx_history_changed_at (changed_at),
    INDEX idx_history_pipeline_run (pipeline_run_id),
    INDEX idx_history_estado (estado_proyecto),

    -- FK al proyecto (opcional, el proyecto podría ser eliminado)
    -- No usamos FK estricta para permitir historial de proyectos eliminados

    -- FK al pipeline run
    CONSTRAINT fk_history_pipeline_run
        FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Historial de cambios detectados en proyectos';

-- ============================================================================
-- Vista: Cambios recientes (últimos 7 días)
-- ============================================================================
CREATE OR REPLACE VIEW proyectos_cambios_recientes AS
SELECT
    h.id,
    h.expediente_id,
    h.operation,
    h.changed_at,
    h.expediente_nombre,
    h.workflow_descripcion,
    h.region_nombre,
    h.estado_proyecto,
    h.changed_fields,
    pr.started_at as pipeline_started_at
FROM proyectos_history h
LEFT JOIN pipeline_runs pr ON h.pipeline_run_id = pr.id
WHERE h.changed_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY h.changed_at DESC;

-- ============================================================================
-- Vista: Resumen de cambios por día
-- ============================================================================
CREATE OR REPLACE VIEW proyectos_cambios_por_dia AS
SELECT
    DATE(changed_at) as fecha,
    operation,
    COUNT(*) as cantidad,
    COUNT(DISTINCT expediente_id) as proyectos_unicos
FROM proyectos_history
GROUP BY DATE(changed_at), operation
ORDER BY fecha DESC, operation;
