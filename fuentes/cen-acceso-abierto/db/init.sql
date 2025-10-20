-- Database initialization script for CEN Acceso Abierto
-- This script runs automatically when the MariaDB container first starts
-- It creates the base tables for storing raw API data and stakeholder information

-- Ensure we're using the correct database
USE cen_acceso_abierto;

-- Create the raw_api_data table if it doesn't exist
CREATE TABLE IF NOT EXISTS raw_api_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_url VARCHAR(512) NOT NULL COMMENT 'The URL that was fetched',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When the data was fetched',
    status_code INT COMMENT 'HTTP status code from the response',
    data JSON COMMENT 'The raw response data stored as JSON',
    error_message TEXT COMMENT 'Error message if the request failed',

    -- Indexes for common queries
    INDEX idx_source_url (source_url),
    INDEX idx_fetched_at (fetched_at),
    INDEX idx_status_code (status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores raw API response data from CEN and other public sources';

-- Create the interesados table (stakeholders for each solicitud)
-- NOTA: Sin UNIQUE constraint - cargamos datos tal cual vienen del API
-- El análisis de duplicados y normalización final se hará posteriormente
CREATE TABLE IF NOT EXISTS interesados (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    solicitud_id INT NOT NULL,
    razon_social VARCHAR(255),
    nombre_fantasia VARCHAR(255),
    raw_data_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_razon_social (razon_social),
    INDEX idx_nombre_fantasia (nombre_fantasia),
    INDEX idx_solicitud_razon (solicitud_id, razon_social),
    FOREIGN KEY (raw_data_id) REFERENCES raw_api_data(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores stakeholder information (interesados) from CEN /interesados endpoint';

-- Optional: Create a view for successful fetches only
CREATE OR REPLACE VIEW successful_fetches AS
SELECT
    id,
    source_url,
    fetched_at,
    status_code,
    data
FROM raw_api_data
WHERE status_code >= 200 AND status_code < 300
ORDER BY fetched_at DESC;

-- Optional: Create a view for the latest fetch per URL
CREATE OR REPLACE VIEW latest_fetches AS
SELECT
    r1.id,
    r1.source_url,
    r1.fetched_at,
    r1.status_code,
    r1.data,
    r1.error_message
FROM raw_api_data r1
INNER JOIN (
    SELECT source_url, MAX(fetched_at) as max_fetched_at
    FROM raw_api_data
    GROUP BY source_url
) r2 ON r1.source_url = r2.source_url AND r1.fetched_at = r2.max_fetched_at
ORDER BY r1.fetched_at DESC;

-- Grant necessary permissions (in case the application user needs them)
-- Note: These are already handled by Docker environment variables, but included for completeness
-- GRANT SELECT, INSERT, UPDATE ON cen_acceso_abierto.* TO 'cen_user'@'%';

-- Log completion
SELECT 'Database initialization completed: raw_api_data, interesados tables created' AS message;
