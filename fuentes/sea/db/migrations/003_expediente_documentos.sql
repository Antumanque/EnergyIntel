-- Migración 003: Tabla para documentos del expediente (EIA/DIA)
-- Esta tabla almacena los documentos principales encontrados en cada expediente

CREATE TABLE IF NOT EXISTS expediente_documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Relación con proyectos
    expediente_id BIGINT NOT NULL,

    -- Datos del documento
    id_documento BIGINT NOT NULL UNIQUE COMMENT 'ID del documento en el sistema SEA',
    folio VARCHAR(100) COMMENT 'Folio del documento (ej: 2025-05-105-3)',
    tipo_documento TEXT COMMENT 'Tipo: "Estudio de impacto ambiental" o "Declaración de impacto ambiental"',
    remitente TEXT COMMENT 'Quien remitió el documento',
    destinatario TEXT COMMENT 'A quién está destinado',
    fecha_generacion DATETIME COMMENT 'Fecha de generación del documento',

    -- URLs
    url_documento TEXT COMMENT 'URL a documento.php?idDocumento=X',
    url_anexos TEXT COMMENT 'URL a elementosFisicos/enviados.php',

    -- Metadata de extracción
    extracted_at DATETIME NOT NULL COMMENT 'Cuándo se extrajo este documento',
    parsed_at DATETIME COMMENT 'Cuándo se parseó el contenido del documento',

    -- Índices
    INDEX idx_expediente_id (expediente_id),
    INDEX idx_id_documento (id_documento),
    INDEX idx_tipo_documento (tipo_documento(100)),
    INDEX idx_extracted_at (extracted_at),

    -- Foreign key
    FOREIGN KEY (expediente_id) REFERENCES proyectos(expediente_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Documentos EIA/DIA encontrados en cada expediente';

-- Registrar migración
INSERT INTO schema_migrations (migration_name, executed_at)
VALUES ('003_expediente_documentos.sql', NOW());
