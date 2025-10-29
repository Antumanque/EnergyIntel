-- ============================================================================
-- Migration 004: Expandir columnas VARCHAR en formularios parseados
-- ============================================================================
-- Fecha: 2025-10-28
-- Razón: Errores "Data too long for column" al parsear formularios
--
-- Errores encontrados:
-- - tipo_proyecto VARCHAR(50) → muy corto para algunos proyectos
-- - rut VARCHAR(20) → muy corto para RUTs con formato extendido
-- - giro VARCHAR(255) → muy corto para algunos casos (SAC)
-- ============================================================================

USE cen_acceso_abierto;

-- ============================================================================
-- SUCTD: Expandir columnas
-- ============================================================================

ALTER TABLE formularios_suctd_parsed
    MODIFY COLUMN rut VARCHAR(50) COMMENT 'RUT expandido de 20 a 50',
    MODIFY COLUMN tipo_proyecto VARCHAR(100) COMMENT 'Tipo de proyecto expandido de 50 a 100';

-- ============================================================================
-- SAC: Expandir columnas
-- ============================================================================

ALTER TABLE formularios_sac_parsed
    MODIFY COLUMN rut VARCHAR(50) COMMENT 'RUT expandido de 20 a 50',
    MODIFY COLUMN tipo_proyecto VARCHAR(100) COMMENT 'Tipo de proyecto expandido de 50 a 100',
    MODIFY COLUMN giro VARCHAR(500) COMMENT 'Giro expandido de 255 a 500';

-- ============================================================================
-- FEHACIENTE: Expandir columnas
-- ============================================================================

ALTER TABLE formularios_fehaciente_parsed
    MODIFY COLUMN rut VARCHAR(50) COMMENT 'RUT expandido de 20 a 50',
    MODIFY COLUMN tipo_proyecto VARCHAR(100) COMMENT 'Tipo de proyecto expandido de 50 a 100';

-- ============================================================================
-- Verificación
-- ============================================================================

SELECT 'Migración 004 completada exitosamente' AS resultado;

-- Ver nuevos tamaños
SELECT
    'SUCTD' AS tabla,
    'rut' AS columna,
    COLUMN_TYPE AS nuevo_tipo
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'cen_acceso_abierto'
  AND TABLE_NAME = 'formularios_suctd_parsed'
  AND COLUMN_NAME = 'rut'

UNION ALL

SELECT
    'SAC' AS tabla,
    'giro' AS columna,
    COLUMN_TYPE AS nuevo_tipo
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'cen_acceso_abierto'
  AND TABLE_NAME = 'formularios_sac_parsed'
  AND COLUMN_NAME = 'giro'

UNION ALL

SELECT
    'FEHACIENTE' AS tabla,
    'tipo_proyecto' AS columna,
    COLUMN_TYPE AS nuevo_tipo
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'cen_acceso_abierto'
  AND TABLE_NAME = 'formularios_fehaciente_parsed'
  AND COLUMN_NAME = 'tipo_proyecto';
