-- ============================================================================
-- Script de limpieza: SASC → SAC
-- ============================================================================
-- Normalizar "SASC" (de la API) a "SAC" (nombre del formulario)
-- para mantener consistencia en toda la base de datos
-- ============================================================================

USE cen_acceso_abierto;

-- Verificar valores actuales antes de la limpieza
SELECT 'ANTES DE LA LIMPIEZA' AS paso;

SELECT
    tipo_solicitud,
    COUNT(*) AS cantidad
FROM solicitudes
GROUP BY tipo_solicitud
ORDER BY tipo_solicitud;

-- ============================================================================
-- LIMPIEZA: Actualizar SASC → SAC
-- ============================================================================

SELECT 'ACTUALIZANDO SASC → SAC' AS paso;

UPDATE solicitudes
SET tipo_solicitud = 'SAC'
WHERE tipo_solicitud = 'SASC';

-- Verificar cambios
SELECT 'DESPUÉS DE LA LIMPIEZA' AS paso;

SELECT
    tipo_solicitud,
    COUNT(*) AS cantidad
FROM solicitudes
GROUP BY tipo_solicitud
ORDER BY tipo_solicitud;

-- ============================================================================
-- Resultado esperado:
-- ANTES:  SASC: ~1584, SUCT: ~631, FEHACIENTES: ~233
-- DESPUÉS: SAC: ~1584, SUCT: ~631, FEHACIENTES: ~233
-- ============================================================================
