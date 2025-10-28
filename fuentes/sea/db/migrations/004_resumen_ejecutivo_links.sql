-- Migración 004: Tabla para links a PDFs del Resumen Ejecutivo (Capítulo 20)
-- Esta tabla almacena los links a los PDFs del resumen ejecutivo de cada documento EIA/DIA

CREATE TABLE IF NOT EXISTS resumen_ejecutivo_links (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Relación con documento EIA/DIA
    id_documento BIGINT NOT NULL,

    -- Información del PDF
    pdf_url TEXT NOT NULL COMMENT 'URL completa al PDF del Capítulo 20',
    pdf_filename VARCHAR(500) COMMENT 'Nombre del archivo PDF',
    texto_link TEXT COMMENT 'Texto del link (ej: "Capítulo 20 Resumen Ejecutivo")',

    -- Metadata adicional del documento completo firmado (si existe)
    documento_firmado_url TEXT COMMENT 'URL al documento firmado completo en infofirma',
    documento_firmado_docid VARCHAR(200) COMMENT 'docId del documento firmado',

    -- Metadata de extracción
    extracted_at DATETIME NOT NULL COMMENT 'Cuándo se extrajo este link',
    pdf_downloaded_at DATETIME COMMENT 'Cuándo se descargó el PDF (futuro)',
    pdf_parsed_at DATETIME COMMENT 'Cuándo se parseó el PDF (futuro)',

    -- Status de procesamiento
    status ENUM('pending', 'downloaded', 'parsed', 'error') DEFAULT 'pending',
    error_message TEXT COMMENT 'Mensaje de error si hubo algún problema',

    -- Índices
    INDEX idx_id_documento (id_documento),
    INDEX idx_extracted_at (extracted_at),
    INDEX idx_status (status),

    -- Foreign key
    FOREIGN KEY (id_documento) REFERENCES expediente_documentos(id_documento)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Links a PDFs del Resumen Ejecutivo (Capítulo 20) de cada documento EIA/DIA';

-- Registrar migración
INSERT INTO schema_migrations (migration_name, executed_at)
VALUES ('004_resumen_ejecutivo_links.sql', NOW());
