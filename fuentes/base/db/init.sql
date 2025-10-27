-- =============================================================================
-- FUENTES BASE - SCHEMA INICIAL
-- =============================================================================
-- Este schema define las tablas core para almacenar datos extraídos desde
-- múltiples tipos de fuentes (APIs, web scraping, archivos).
--
-- Estrategia: Append-only (nunca UPDATE/DELETE registros históricos)
-- =============================================================================

-- Tabla principal para almacenar datos crudos de todas las extracciones
CREATE TABLE IF NOT EXISTS raw_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_url VARCHAR(2000) NOT NULL COMMENT 'URL o identificador de la fuente',
    source_type ENUM('api_rest', 'web_static', 'web_dynamic', 'file_download', 'other') DEFAULT 'other' COMMENT 'Tipo de fuente',
    status_code INT NOT NULL COMMENT 'HTTP status code o código custom',
    data JSON COMMENT 'Datos extraídos en formato JSON',
    error_message TEXT COMMENT 'Mensaje de error si la extracción falló',
    extracted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp de extracción',

    INDEX idx_source_url (source_url(255)),
    INDEX idx_source_type (source_type),
    INDEX idx_status_code (status_code),
    INDEX idx_extracted_at (extracted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tabla append-only para almacenar todos los datos crudos extraídos';

-- Vista para extracciones exitosas únicamente
CREATE OR REPLACE VIEW successful_extractions AS
SELECT *
FROM raw_data
WHERE status_code >= 200 AND status_code < 300
  AND error_message IS NULL;

-- Vista para última extracción por URL
CREATE OR REPLACE VIEW latest_extractions AS
SELECT rd.*
FROM raw_data rd
INNER JOIN (
    SELECT source_url, MAX(id) as max_id
    FROM raw_data
    GROUP BY source_url
) latest ON rd.id = latest.max_id;

-- Vista para estadísticas de extracción
CREATE OR REPLACE VIEW extraction_statistics AS
SELECT
    source_type,
    COUNT(*) as total_extractions,
    SUM(CASE WHEN status_code >= 200 AND status_code < 300 AND error_message IS NULL THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN status_code < 200 OR status_code >= 300 OR error_message IS NOT NULL THEN 1 ELSE 0 END) as failed,
    MIN(extracted_at) as first_extraction,
    MAX(extracted_at) as last_extraction
FROM raw_data
GROUP BY source_type;

-- Tabla para tracking de parseo de datos
CREATE TABLE IF NOT EXISTS parsed_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    raw_data_id INT NOT NULL COMMENT 'FK a raw_data',
    parser_type ENUM('json', 'pdf', 'xlsx', 'csv', 'html', 'other') NOT NULL COMMENT 'Tipo de parser usado',
    parsing_successful BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Si el parseo fue exitoso',
    parsed_content JSON COMMENT 'Contenido parseado en formato JSON',
    error_message TEXT COMMENT 'Mensaje de error si el parseo falló',
    parsed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp de parseo',
    metadata JSON COMMENT 'Metadata adicional del parseo',

    FOREIGN KEY (raw_data_id) REFERENCES raw_data(id) ON DELETE CASCADE,
    INDEX idx_raw_data_id (raw_data_id),
    INDEX idx_parser_type (parser_type),
    INDEX idx_parsing_successful (parsing_successful),
    INDEX idx_parsed_at (parsed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tabla para trackear resultados de parseo de datos';

-- Vista para parseos exitosos
CREATE OR REPLACE VIEW successful_parsings AS
SELECT *
FROM parsed_data
WHERE parsing_successful = TRUE;

-- Vista para parseos con errores
CREATE OR REPLACE VIEW failed_parsings AS
SELECT
    pd.*,
    rd.source_url,
    rd.source_type
FROM parsed_data pd
JOIN raw_data rd ON pd.raw_data_id = rd.id
WHERE pd.parsing_successful = FALSE;

-- Tabla para gestión de migraciones
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE COMMENT 'Nombre del archivo de migración',
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp de aplicación',

    INDEX idx_migration_name (migration_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tabla para tracking de migraciones aplicadas';

-- =============================================================================
-- DATOS INICIALES
-- =============================================================================

-- Insert initial migration record
INSERT INTO schema_migrations (migration_name) VALUES ('000_init_schema.sql')
ON DUPLICATE KEY UPDATE migration_name=migration_name;

-- =============================================================================
-- FIN DEL SCHEMA INICIAL
-- =============================================================================
