-- ============================================================================
-- Migración: Agregar columna download_error a tabla documentos
-- ============================================================================
-- Fecha: 2025-10-20
-- Descripción: Agrega columna para rastrear errores durante descarga de archivos
-- ============================================================================

USE cen_acceso_abierto;

-- Solo ejecutar si la tabla documentos existe
SET @table_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'cen_acceso_abierto'
    AND TABLE_NAME = 'documentos'
);

-- Agregar columna download_error si la tabla existe
SET @sql = IF(@table_exists > 0,
    'ALTER TABLE documentos ADD COLUMN IF NOT EXISTS download_error TEXT COMMENT ''Mensaje de error si la descarga falló''',
    'SELECT ''Tabla documentos no existe, saltando migración'' AS mensaje'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Agregar índice para filtrar documentos con errores (si la tabla existe)
SET @sql = IF(@table_exists > 0,
    'ALTER TABLE documentos ADD INDEX IF NOT EXISTS idx_downloaded (downloaded)',
    'SELECT ''Tabla documentos no existe, saltando índice'' AS mensaje'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@table_exists > 0,
    'Migración completada: columna download_error agregada',
    'Migración saltada: tabla documentos no existe') AS mensaje;
