-- Migración: Agregar tabla de inteligencia de negocio extraída con Claude
-- Fecha: 2025-11-06
-- Descripción: ETAPA 4 - Análisis de PDFs con Claude Haiku 4.5

CREATE TABLE IF NOT EXISTS proyecto_inteligencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_documento BIGINT NOT NULL,

    -- Clasificación principal
    industria VARCHAR(100) NOT NULL COMMENT 'Industria principal: energia, mineria, construccion, etc.',
    es_energia BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'TRUE si es sector energía',

    -- Información de negocio
    sub_industria VARCHAR(200) COMMENT 'Sub-categoría de industria (ej: solar, eólica, hidroeléctrica)',
    oportunidad_negocio TEXT COMMENT 'Análisis de oportunidad de negocio',
    datos_clave JSON COMMENT 'Datos clave extraídos (inversión, capacidad, tecnología, etc.)',

    -- Metadata de extracción
    modelo_usado VARCHAR(50) NOT NULL DEFAULT 'claude-haiku-4-5',
    tokens_input INT COMMENT 'Tokens enviados al modelo',
    tokens_output INT COMMENT 'Tokens generados por el modelo',
    costo_usd DECIMAL(10,6) COMMENT 'Costo de la inferencia en USD',

    -- Tracking
    status ENUM('pending', 'completed', 'error') DEFAULT 'pending',
    error_message TEXT,
    pdf_text_length INT COMMENT 'Longitud del texto extraído del PDF',
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices
    UNIQUE KEY idx_id_documento (id_documento),
    INDEX idx_industria (industria),
    INDEX idx_es_energia (es_energia),
    INDEX idx_status (status),

    -- FK
    FOREIGN KEY (id_documento) REFERENCES resumen_ejecutivo_links(id_documento) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Registrar migración
INSERT INTO schema_migrations (migration_name)
VALUES ('008_add_proyecto_inteligencia.sql')
ON DUPLICATE KEY UPDATE migration_name=migration_name;
