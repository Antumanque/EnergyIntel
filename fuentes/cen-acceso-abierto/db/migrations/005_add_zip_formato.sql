-- ============================================================================
-- Migration 005: Agregar 'ZIP' como formato válido en formularios_parseados
-- ============================================================================
-- Fecha: 2025-10-28
-- Razón: Soporte para archivos .zip que contienen formularios
-- ============================================================================

USE cen_acceso_abierto;

-- Modificar ENUM para incluir ZIP
ALTER TABLE formularios_parseados
    MODIFY COLUMN formato_archivo ENUM('PDF', 'XLSX', 'XLS', 'ZIP') NOT NULL
    COMMENT 'Formato del archivo parseado (ZIP se descomprime automáticamente)';

-- Verificación
SELECT 'Migración 005 completada: ZIP agregado como formato válido' AS resultado;

SELECT
    COLUMN_NAME,
    COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'cen_acceso_abierto'
  AND TABLE_NAME = 'formularios_parseados'
  AND COLUMN_NAME = 'formato_archivo';
