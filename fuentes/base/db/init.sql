-- Database initialization script for API Data Ingestion Template
-- This script runs automatically when the MariaDB container first starts
-- It creates the necessary database schema for storing raw API data

-- Ensure we're using the correct database
USE api_ingestion;

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
-- GRANT SELECT, INSERT, UPDATE ON api_ingestion.* TO 'api_user'@'%';

-- Log completion
SELECT 'Database initialization completed successfully' AS message;
