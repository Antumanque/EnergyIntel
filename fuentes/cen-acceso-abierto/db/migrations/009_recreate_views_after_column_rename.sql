-- =============================================================================
-- Migración 009: Recrear vistas después de renombrar columnas
-- =============================================================================
-- Las vistas quedaron inválidas después de renombrar created_at → fetched_at
-- Esta migración las recrea para que funcionen correctamente
-- =============================================================================

-- Vista: documentos_ultimas_versiones
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

-- Vista: documentos_listos_para_parsear
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

-- Vista: documentos_importantes
CREATE OR REPLACE VIEW documentos_importantes AS
SELECT
    d.*,
    s.proyecto,
    s.tipo_solicitud,
    s.region,
    s.comuna
FROM documentos d
INNER JOIN solicitudes s ON d.solicitud_id = s.id
WHERE d.tipo_documento IN ('Formulario SUCTD', 'Formulario SAC', 'Formulario_proyecto_fehaciente')
    AND d.deleted = 0
    AND d.visible = 1;

-- Vista: solicitudes_con_documentos
CREATE OR REPLACE VIEW solicitudes_con_documentos AS
SELECT
    s.*,
    COUNT(d.id) AS total_documentos,
    SUM(CASE WHEN d.tipo_documento = 'Formulario SUCTD' THEN 1 ELSE 0 END) AS tiene_suctd,
    SUM(CASE WHEN d.tipo_documento = 'Formulario SAC' THEN 1 ELSE 0 END) AS tiene_sac,
    SUM(CASE WHEN d.tipo_documento = 'Formulario_proyecto_fehaciente' THEN 1 ELSE 0 END) AS tiene_fehaciente
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
    AND d.tipo_documento IN ('Formulario SUCTD', 'Formulario SAC', 'Formulario_proyecto_fehaciente')
    AND d.deleted = 0
    AND d.visible = 1
GROUP BY s.id;

-- Vista: estadisticas_extraccion
CREATE OR REPLACE VIEW estadisticas_extraccion AS
SELECT
    'Solicitudes totales' AS metrica,
    COUNT(*) AS valor
FROM solicitudes
UNION ALL
SELECT
    'Documentos totales',
    COUNT(*)
FROM documentos
UNION ALL
SELECT
    'Documentos únicos (última versión)',
    COUNT(*)
FROM documentos_ultimas_versiones
WHERE tipo_documento IN ('Formulario SAC', 'Formulario SUCTD', 'Formulario_proyecto_fehaciente')
UNION ALL
SELECT
    'Documentos SUCTD',
    COUNT(*)
FROM documentos
WHERE tipo_documento = 'Formulario SUCTD' AND deleted = 0
UNION ALL
SELECT
    'Documentos SAC',
    COUNT(*)
FROM documentos
WHERE tipo_documento = 'Formulario SAC' AND deleted = 0
UNION ALL
SELECT
    'Documentos Fehaciente',
    COUNT(*)
FROM documentos
WHERE tipo_documento = 'Formulario_proyecto_fehaciente' AND deleted = 0
UNION ALL
SELECT
    'Documentos descargados',
    COUNT(*)
FROM documentos
WHERE downloaded = 1
UNION ALL
SELECT
    'Documentos listos para parsear',
    COUNT(*)
FROM documentos_listos_para_parsear;
