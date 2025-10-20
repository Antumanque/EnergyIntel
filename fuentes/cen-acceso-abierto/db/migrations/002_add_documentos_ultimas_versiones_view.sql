-- ============================================================================
-- Migración: Crear vista documentos_ultimas_versiones
-- ============================================================================
-- Fecha: 2025-10-20
-- Descripción: Vista que muestra SOLO la última versión de cada documento
--              por solicitud y tipo de documento, eliminando duplicados
-- ============================================================================

USE cen_acceso_abierto;

-- Crear o reemplazar vista para últimas versiones
CREATE OR REPLACE VIEW documentos_ultimas_versiones AS
SELECT
    d.*
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY solicitud_id, tipo_documento
            ORDER BY create_date DESC, id DESC
        ) as rn
    FROM documentos
    WHERE deleted = 0
      AND visible = 1
) d
WHERE d.rn = 1;

-- Crear vista auxiliar para documentos únicos DESCARGADOS y listos para parsear
CREATE OR REPLACE VIEW documentos_listos_para_parsear AS
SELECT
    d.*,
    CASE
        WHEN d.nombre LIKE '%.pdf' THEN 'PDF'
        WHEN d.nombre LIKE '%.xlsx' THEN 'XLSX'
        WHEN d.nombre LIKE '%.xls' THEN 'XLS'
        WHEN d.nombre LIKE '%.zip' THEN 'ZIP'
        WHEN d.nombre LIKE '%.rar' THEN 'RAR'
        ELSE 'OTRO'
    END AS formato_archivo
FROM documentos_ultimas_versiones d
WHERE d.downloaded = 1
  AND d.local_path IS NOT NULL
  AND d.tipo_documento IN ('Formulario SAC', 'Formulario SUCTD', 'Formulario_proyecto_fehaciente');

-- Verificar resultados
SELECT
    'Total documentos únicos (últimas versiones)' as metrica,
    COUNT(*) as total
FROM documentos_ultimas_versiones
WHERE tipo_documento IN ('Formulario SAC', 'Formulario SUCTD', 'Formulario_proyecto_fehaciente')

UNION ALL

SELECT
    'Documentos únicos descargados' as metrica,
    COUNT(*) as total
FROM documentos_listos_para_parsear;

SELECT 'Migración completada: vistas documentos_ultimas_versiones y documentos_listos_para_parsear creadas' AS mensaje;
