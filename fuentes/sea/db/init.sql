-- =============================================================================
-- SEA (Sistema de Evaluación de Impacto Ambiental) - SCHEMA INICIAL
-- =============================================================================
-- Este schema define las tablas para almacenar datos de proyectos de
-- evaluación de impacto ambiental en Chile desde el SEA.
--
-- Estrategia: Append-only (nunca UPDATE/DELETE registros históricos)
-- =============================================================================

-- Tabla principal para datos crudos de todas las extracciones de la API
CREATE TABLE IF NOT EXISTS raw_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_url VARCHAR(2000) NOT NULL COMMENT 'URL de la API con parámetros',
    source_type ENUM('api_rest', 'web_static', 'web_dynamic', 'file_download', 'other') DEFAULT 'api_rest' COMMENT 'Tipo de fuente',
    status_code INT NOT NULL COMMENT 'HTTP status code',
    data JSON COMMENT 'Response completo de la API en formato JSON',
    error_message TEXT COMMENT 'Mensaje de error si la extracción falló',
    extracted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp de extracción',

    INDEX idx_source_url (source_url(255)),
    INDEX idx_source_type (source_type),
    INDEX idx_status_code (status_code),
    INDEX idx_extracted_at (extracted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tabla append-only para almacenar todas las respuestas de la API del SEA';

-- Tabla principal para proyectos del SEA
CREATE TABLE IF NOT EXISTS proyectos (
    -- ID principal
    expediente_id BIGINT PRIMARY KEY COMMENT 'ID único del expediente del SEA',

    -- Información básica del proyecto
    expediente_nombre VARCHAR(500) COMMENT 'Nombre del proyecto',
    expediente_url_ppal TEXT COMMENT 'URL del expediente principal',
    expediente_url_ficha TEXT COMMENT 'URL de la ficha del expediente',

    -- Tipo de evaluación
    workflow_descripcion VARCHAR(50) COMMENT 'Tipo de evaluación: DIA o EIA',

    -- Ubicación
    region_nombre VARCHAR(100) COMMENT 'Región del proyecto',
    comuna_nombre VARCHAR(100) COMMENT 'Comuna del proyecto',

    -- Tipología del proyecto
    tipo_proyecto VARCHAR(50) COMMENT 'Código del tipo de proyecto',
    descripcion_tipologia TEXT COMMENT 'Descripción completa de la tipología',
    razon_ingreso VARCHAR(255) COMMENT 'Razón de ingreso al sistema',

    -- Titular
    titular VARCHAR(255) COMMENT 'Empresa/persona titular del proyecto',

    -- Inversión
    inversion_mm DECIMAL(20,4) COMMENT 'Inversión en formato numérico (millones de USD)',
    inversion_mm_format VARCHAR(50) COMMENT 'Inversión formateada para display',

    -- Fechas
    fecha_presentacion BIGINT COMMENT 'Timestamp Unix de presentación',
    fecha_presentacion_format VARCHAR(50) COMMENT 'Fecha de presentación formateada DD/MM/YYYY',
    fecha_plazo BIGINT COMMENT 'Timestamp Unix de plazo',
    fecha_plazo_format VARCHAR(50) COMMENT 'Fecha de plazo formateada DD/MM/YYYY',

    -- Estado y actividad
    estado_proyecto VARCHAR(100) COMMENT 'Estado actual del proyecto',
    encargado VARCHAR(255) COMMENT 'Persona encargada del proyecto',
    actividad_actual VARCHAR(255) COMMENT 'Actividad actual del proyecto',
    etapa VARCHAR(100) COMMENT 'Etapa actual del proceso',

    -- Geolocalización
    link_mapa_show BOOLEAN COMMENT 'Si tiene información de mapa disponible',
    link_mapa_url TEXT COMMENT 'URL del mapa del proyecto',
    link_mapa_image VARCHAR(100) COMMENT 'Imagen del mapa',

    -- Otros campos
    acciones TEXT COMMENT 'Acciones disponibles para el proyecto',
    dias_legales INT COMMENT 'Días legales transcurridos',
    suspendido VARCHAR(50) COMMENT 'Estado de suspensión: Activo/Suspendido',
    ver_actividad TEXT COMMENT 'Campo para ver actividad',

    -- Metadata de extracción
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha en que fue extraído de la API',

    -- Índices para búsquedas eficientes
    INDEX idx_workflow (workflow_descripcion),
    INDEX idx_region (region_nombre),
    INDEX idx_comuna (comuna_nombre),
    INDEX idx_titular (titular),
    INDEX idx_estado (estado_proyecto),
    INDEX idx_tipo_proyecto (tipo_proyecto),
    INDEX idx_fecha_presentacion (fecha_presentacion),
    INDEX idx_fetched_at (fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Proyectos del SEA extraídos de la API de búsqueda';

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

-- Vista: proyectos_por_region
-- Estadísticas de proyectos por región
CREATE OR REPLACE VIEW proyectos_por_region AS
SELECT
    region_nombre,
    workflow_descripcion,
    COUNT(*) as total_proyectos,
    SUM(inversion_mm) as inversion_total_mm,
    COUNT(CASE WHEN estado_proyecto LIKE '%Aprobad%' THEN 1 END) as aprobados,
    COUNT(CASE WHEN estado_proyecto LIKE '%Rechazad%' THEN 1 END) as rechazados,
    COUNT(CASE WHEN estado_proyecto LIKE '%En Calificación%' THEN 1 END) as en_calificacion
FROM proyectos
GROUP BY region_nombre, workflow_descripcion
ORDER BY total_proyectos DESC;

-- Vista: proyectos_por_tipo
-- Estadísticas de proyectos por tipo de evaluación
CREATE OR REPLACE VIEW proyectos_por_tipo AS
SELECT
    workflow_descripcion,
    COUNT(*) as total_proyectos,
    SUM(inversion_mm) as inversion_total_mm,
    AVG(inversion_mm) as inversion_promedio_mm,
    COUNT(CASE WHEN estado_proyecto LIKE '%Aprobad%' THEN 1 END) as aprobados,
    COUNT(CASE WHEN estado_proyecto LIKE '%Rechazad%' THEN 1 END) as rechazados
FROM proyectos
GROUP BY workflow_descripcion;

-- Vista: proyectos_recientes
-- Proyectos presentados en los últimos 30 días
CREATE OR REPLACE VIEW proyectos_recientes AS
SELECT *
FROM proyectos
WHERE fecha_presentacion >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
ORDER BY fecha_presentacion DESC;

-- Vista: estadisticas_generales
-- Dashboard de estadísticas generales
CREATE OR REPLACE VIEW estadisticas_generales AS
SELECT
    'Total de proyectos' AS metrica,
    COUNT(*) AS valor
FROM proyectos
UNION ALL
SELECT
    'Total proyectos DIA',
    COUNT(*)
FROM proyectos
WHERE workflow_descripcion = 'DIA'
UNION ALL
SELECT
    'Total proyectos EIA',
    COUNT(*)
FROM proyectos
WHERE workflow_descripcion = 'EIA'
UNION ALL
SELECT
    'Inversión total (millones USD)',
    ROUND(SUM(inversion_mm), 2)
FROM proyectos
UNION ALL
SELECT
    'Proyectos aprobados',
    COUNT(*)
FROM proyectos
WHERE estado_proyecto LIKE '%Aprobad%'
UNION ALL
SELECT
    'Proyectos en calificación',
    COUNT(*)
FROM proyectos
WHERE estado_proyecto LIKE '%En Calificación%'
UNION ALL
SELECT
    'Proyectos con geolocalización',
    COUNT(*)
FROM proyectos
WHERE link_mapa_show = TRUE;

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
