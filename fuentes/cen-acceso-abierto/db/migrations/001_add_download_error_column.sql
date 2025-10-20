-- ============================================================================
-- Migración: Agregar columna download_error a tabla documentos
-- ============================================================================
-- Fecha: 2025-10-20
-- Descripción: Agrega columna para rastrear errores durante descarga de archivos
-- ============================================================================

USE cen_acceso_abierto;

-- Agregar columna download_error si no existe
ALTER TABLE documentos
ADD COLUMN IF NOT EXISTS download_error TEXT COMMENT 'Mensaje de error si la descarga falló';

-- Agregar índice para filtrar documentos con errores
ALTER TABLE documentos
ADD INDEX IF NOT EXISTS idx_downloaded (downloaded);

-- Verificar cambios
DESCRIBE documentos;

SELECT 'Migración completada: columna download_error agregada' AS mensaje;
