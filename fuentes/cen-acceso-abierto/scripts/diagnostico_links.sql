-- ============================================================================
-- DIAGNÓSTICO: Análisis de Links Perdidos entre Solicitudes y Formularios
-- ============================================================================
-- Este script identifica dónde se rompe la cadena de relaciones:
-- solicitudes → documentos → formularios_parseados → formularios_*_parsed
-- ============================================================================

USE cen_acceso_abierto;

-- ============================================================================
-- PASO 1: Conteo general de solicitudes por tipo
-- ============================================================================
SELECT
    'PASO 1: Total de Solicitudes por Tipo' AS seccion,
    tipo_solicitud,
    COUNT(*) AS total_solicitudes
FROM solicitudes
WHERE tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
GROUP BY tipo_solicitud
ORDER BY tipo_solicitud;

-- ============================================================================
-- PASO 2: Solicitudes que SÍ tienen documentos
-- ============================================================================
SELECT
    'PASO 2: Solicitudes con Documentos' AS seccion,
    s.tipo_solicitud,
    COUNT(DISTINCT s.id) AS solicitudes_con_documentos,
    COUNT(d.id) AS total_documentos
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
WHERE s.tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
GROUP BY s.tipo_solicitud
ORDER BY s.tipo_solicitud;

-- ============================================================================
-- PASO 3: Solicitudes SIN documentos (primer punto de quiebre)
-- ============================================================================
SELECT
    'PASO 3: Solicitudes SIN Documentos' AS seccion,
    s.tipo_solicitud,
    COUNT(*) AS solicitudes_sin_documentos
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
WHERE s.tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
  AND d.id IS NULL
GROUP BY s.tipo_solicitud
ORDER BY s.tipo_solicitud;

-- ============================================================================
-- PASO 4: Documentos que SÍ fueron parseados
-- ============================================================================
SELECT
    'PASO 4: Documentos Parseados' AS seccion,
    s.tipo_solicitud,
    COUNT(DISTINCT d.id) AS documentos_parseados,
    SUM(CASE WHEN fp.parsing_exitoso = 1 THEN 1 ELSE 0 END) AS parseos_exitosos,
    SUM(CASE WHEN fp.parsing_exitoso = 0 THEN 1 ELSE 0 END) AS parseos_fallidos
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
INNER JOIN formularios_parseados fp ON d.id = fp.documento_id
WHERE s.tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
GROUP BY s.tipo_solicitud
ORDER BY s.tipo_solicitud;

-- ============================================================================
-- PASO 5: Documentos que NO fueron parseados (segundo punto de quiebre)
-- ============================================================================
SELECT
    'PASO 5: Documentos NO Parseados' AS seccion,
    s.tipo_solicitud,
    d.tipo_documento,
    COUNT(*) AS documentos_no_parseados
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
WHERE s.tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
  AND fp.id IS NULL
GROUP BY s.tipo_solicitud, d.tipo_documento
ORDER BY s.tipo_solicitud, documentos_no_parseados DESC;

-- ============================================================================
-- PASO 6: Formularios parseados que SÍ están en tablas específicas
-- ============================================================================
-- SUCTD
SELECT
    'PASO 6a: Formularios SUCTD en tabla específica' AS seccion,
    'SUCTD' AS tipo_formulario,
    COUNT(DISTINCT fp.id) AS formularios_parseados_total,
    COUNT(DISTINCT suctd.id) AS en_tabla_especifica,
    COUNT(DISTINCT fp.id) - COUNT(DISTINCT suctd.id) AS faltantes
FROM formularios_parseados fp
LEFT JOIN formularios_suctd_parsed suctd ON fp.id = suctd.formulario_parseado_id
WHERE fp.tipo_formulario = 'SUCTD';

-- SAC
SELECT
    'PASO 6b: Formularios SAC en tabla específica' AS seccion,
    'SAC' AS tipo_formulario,
    COUNT(DISTINCT fp.id) AS formularios_parseados_total,
    COUNT(DISTINCT sac.id) AS en_tabla_especifica,
    COUNT(DISTINCT fp.id) - COUNT(DISTINCT sac.id) AS faltantes
FROM formularios_parseados fp
LEFT JOIN formularios_sac_parsed sac ON fp.id = sac.formulario_parseado_id
WHERE fp.tipo_formulario = 'SAC';

-- FEHACIENTE
SELECT
    'PASO 6c: Formularios FEHACIENTE en tabla específica' AS seccion,
    'FEHACIENTE' AS tipo_formulario,
    COUNT(DISTINCT fp.id) AS formularios_parseados_total,
    COUNT(DISTINCT feh.id) AS en_tabla_especifica,
    COUNT(DISTINCT fp.id) - COUNT(DISTINCT feh.id) AS faltantes
FROM formularios_parseados fp
LEFT JOIN formularios_fehaciente_parsed feh ON fp.id = feh.formulario_parseado_id
WHERE fp.tipo_formulario = 'FEHACIENTE';

-- ============================================================================
-- PASO 7: Resumen Final - Solicitudes con Formulario Parseado Completo
-- ============================================================================
-- SUCTD
SELECT
    'PASO 7a: SUCTD - Solicitudes con Formulario Completo' AS seccion,
    COUNT(DISTINCT s.id) AS solicitudes_con_formulario_parseado
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
INNER JOIN formularios_parseados fp ON d.id = fp.documento_id
INNER JOIN formularios_suctd_parsed suctd ON fp.id = suctd.formulario_parseado_id
WHERE s.tipo_solicitud = 'SUCT';

-- SAC
SELECT
    'PASO 7b: SAC - Solicitudes con Formulario Completo' AS seccion,
    COUNT(DISTINCT s.id) AS solicitudes_con_formulario_parseado
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
INNER JOIN formularios_parseados fp ON d.id = fp.documento_id
INNER JOIN formularios_sac_parsed sac ON fp.id = sac.formulario_parseado_id
WHERE s.tipo_solicitud = 'SAC';

-- FEHACIENTE
SELECT
    'PASO 7c: FEHACIENTE - Solicitudes con Formulario Completo' AS seccion,
    COUNT(DISTINCT s.id) AS solicitudes_con_formulario_parseado
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
INNER JOIN formularios_parseados fp ON d.id = fp.documento_id
INNER JOIN formularios_fehaciente_parsed feh ON fp.id = feh.formulario_parseado_id
WHERE s.tipo_solicitud = 'FEHACIENTES';

-- ============================================================================
-- PASO 8: Análisis de tipos de documentos disponibles por tipo de solicitud
-- ============================================================================
SELECT
    'PASO 8: Tipos de Documentos por Tipo de Solicitud' AS seccion,
    s.tipo_solicitud,
    d.tipo_documento,
    COUNT(*) AS cantidad_documentos,
    COUNT(DISTINCT d.solicitud_id) AS solicitudes_unicas
FROM solicitudes s
INNER JOIN documentos d ON s.id = d.solicitud_id
WHERE s.tipo_solicitud IN ('SUCT', 'SAC', 'FEHACIENTES')
GROUP BY s.tipo_solicitud, d.tipo_documento
ORDER BY s.tipo_solicitud, cantidad_documentos DESC;

-- ============================================================================
-- PASO 9: Ejemplos de solicitudes sin formulario parseado (primeras 5 de cada tipo)
-- ============================================================================
-- SUCTD sin formulario
(SELECT
    'PASO 9a: Ejemplos SUCTD sin formulario' AS seccion,
    s.id AS solicitud_id,
    s.proyecto,
    s.rut_empresa,
    COUNT(d.id) AS total_documentos,
    GROUP_CONCAT(DISTINCT d.tipo_documento SEPARATOR ', ') AS tipos_documentos
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
WHERE s.tipo_solicitud = 'SUCT'
  AND fp.id IS NULL
GROUP BY s.id, s.proyecto, s.rut_empresa
ORDER BY s.id
LIMIT 5)
UNION ALL
-- SAC sin formulario
(SELECT
    'PASO 9b: Ejemplos SAC sin formulario' AS seccion,
    s.id AS solicitud_id,
    s.proyecto,
    s.rut_empresa,
    COUNT(d.id) AS total_documentos,
    GROUP_CONCAT(DISTINCT d.tipo_documento SEPARATOR ', ') AS tipos_documentos
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
WHERE s.tipo_solicitud = 'SAC'
  AND fp.id IS NULL
GROUP BY s.id, s.proyecto, s.rut_empresa
ORDER BY s.id
LIMIT 5)
UNION ALL
-- FEHACIENTE sin formulario
(SELECT
    'PASO 9c: Ejemplos FEHACIENTE sin formulario' AS seccion,
    s.id AS solicitud_id,
    s.proyecto,
    s.rut_empresa,
    COUNT(d.id) AS total_documentos,
    GROUP_CONCAT(DISTINCT d.tipo_documento SEPARATOR ', ') AS tipos_documentos
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
WHERE s.tipo_solicitud = 'FEHACIENTES'
  AND fp.id IS NULL
GROUP BY s.id, s.proyecto, s.rut_empresa
ORDER BY s.id
LIMIT 5);

-- ============================================================================
-- FIN DEL DIAGNÓSTICO
-- ============================================================================
