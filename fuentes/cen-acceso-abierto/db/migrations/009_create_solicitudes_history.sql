-- ============================================================================
-- Migración 009: Crear tabla de historial de cambios
-- ============================================================================
-- Registra cada INSERT y UPDATE de solicitudes para auditoría y análisis.
--
-- Casos de uso:
--   - Ver qué solicitudes cambiaron de estado en un período
--   - Auditar cuándo se detectó una solicitud por primera vez
--   - Analizar patrones de cambio (ej: solicitudes que cambian frecuentemente)
-- ============================================================================

CREATE TABLE IF NOT EXISTS solicitudes_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Referencia a la solicitud
    solicitud_id INT NOT NULL,

    -- Tipo de operación
    operation ENUM('INSERT', 'UPDATE') NOT NULL,

    -- Cuándo ocurrió el cambio
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Pipeline run que detectó el cambio (NULL si fue manual)
    pipeline_run_id INT NULL,

    -- Campos que cambiaron (solo para UPDATE)
    -- Formato: [{"field": "estado_solicitud", "old": "En Evaluación", "new": "Aprobada"}, ...]
    changed_fields JSON NULL,

    -- Snapshot de campos clave al momento del cambio
    proyecto VARCHAR(500) NULL,
    razon_social VARCHAR(255) NULL,
    tipo_solicitud VARCHAR(100) NULL,
    estado_solicitud VARCHAR(100) NULL,
    etapa VARCHAR(100) NULL,
    tipo_tecnologia_nombre VARCHAR(100) NULL,
    potencia_nominal DECIMAL(10,2) NULL,
    region VARCHAR(100) NULL,
    fecha_estimada_conexion DATE NULL,

    -- Índices para queries comunes
    INDEX idx_history_solicitud (solicitud_id),
    INDEX idx_history_operation (operation),
    INDEX idx_history_changed_at (changed_at),
    INDEX idx_history_pipeline_run (pipeline_run_id),
    INDEX idx_history_estado (estado_solicitud),
    INDEX idx_history_etapa (etapa),

    -- FK al pipeline run
    CONSTRAINT fk_solicitudes_history_pipeline_run
        FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Historial de cambios detectados en solicitudes';

-- ============================================================================
-- Vista: Cambios recientes (últimos 7 días)
-- ============================================================================
CREATE OR REPLACE VIEW solicitudes_cambios_recientes AS
SELECT
    h.id,
    h.solicitud_id,
    h.operation,
    h.changed_at,
    h.proyecto,
    h.razon_social,
    h.tipo_solicitud,
    h.estado_solicitud,
    h.etapa,
    h.potencia_nominal,
    h.region,
    h.changed_fields,
    pr.started_at as pipeline_started_at
FROM solicitudes_history h
LEFT JOIN pipeline_runs pr ON h.pipeline_run_id = pr.id
WHERE h.changed_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY h.changed_at DESC;

-- ============================================================================
-- Vista: Resumen de cambios por día
-- ============================================================================
CREATE OR REPLACE VIEW solicitudes_cambios_por_dia AS
SELECT
    DATE(changed_at) as fecha,
    operation,
    COUNT(*) as cantidad,
    COUNT(DISTINCT solicitud_id) as solicitudes_unicas
FROM solicitudes_history
GROUP BY DATE(changed_at), operation
ORDER BY fecha DESC, operation;

-- ============================================================================
-- Vista: Cambios de estado (transiciones)
-- ============================================================================
CREATE OR REPLACE VIEW solicitudes_transiciones_estado AS
SELECT
    h.solicitud_id,
    h.proyecto,
    h.razon_social,
    h.changed_at,
    JSON_UNQUOTE(JSON_EXTRACT(cf.change_item, '$.old')) as estado_anterior,
    JSON_UNQUOTE(JSON_EXTRACT(cf.change_item, '$.new')) as estado_nuevo,
    h.potencia_nominal,
    h.region
FROM solicitudes_history h
CROSS JOIN JSON_TABLE(
    h.changed_fields,
    '$[*]' COLUMNS (change_item JSON PATH '$')
) cf
WHERE h.operation = 'UPDATE'
  AND JSON_UNQUOTE(JSON_EXTRACT(cf.change_item, '$.field')) = 'estado_solicitud'
ORDER BY h.changed_at DESC;
