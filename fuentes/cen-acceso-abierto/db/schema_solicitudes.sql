-- ============================================================================
-- Schema para Solicitudes y Documentos del CEN
-- ============================================================================
-- Este schema almacena la información estructurada de solicitudes y documentos
-- extraídos de la API del CEN Acceso Abierto
-- ============================================================================

-- Tabla: solicitudes
-- Almacena la información completa de cada solicitud (tipo=6 de la API)
CREATE TABLE IF NOT EXISTS solicitudes (
    -- ID principal
    id BIGINT PRIMARY KEY COMMENT 'solicitud_id de la API (tipo=6)',

    -- Tipo de solicitud
    tipo_solicitud_id INT COMMENT '1=SAC, 2=SUCTD, 3=FEHACIENTES',
    tipo_solicitud VARCHAR(20) COMMENT 'Nombre del tipo de solicitud',

    -- Estado
    estado_solicitud_id INT,
    estado_solicitud VARCHAR(255),

    -- Fechas
    create_date TIMESTAMP COMMENT 'Fecha de creación en el sistema CEN',
    update_date TIMESTAMP COMMENT 'Última actualización en el sistema CEN',

    -- Proyecto
    proyecto_id INT,
    proyecto VARCHAR(255) COMMENT 'Nombre del proyecto',

    -- Empresa
    rut_empresa VARCHAR(20) COMMENT 'RUT de la empresa solicitante',
    razon_social VARCHAR(255) COMMENT 'Razón social de la empresa',

    -- Tecnología
    tipo_tecnologia_nombre VARCHAR(100) COMMENT 'Solar, Eólico, Híbrido, etc.',
    potencia_nominal VARCHAR(50) COMMENT 'Potencia nominal en MW',

    -- Ubicación geográfica
    comuna_id INT,
    comuna VARCHAR(100),
    provincia_id INT,
    provincia VARCHAR(100),
    region_id INT,
    region VARCHAR(100),
    lat VARCHAR(50) COMMENT 'Latitud',
    lng VARCHAR(50) COMMENT 'Longitud',

    -- Información de conexión
    nombre_se VARCHAR(255) COMMENT 'Nombre de la subestación eléctrica',
    nivel_tension INT COMMENT 'Nivel de tensión en kV',
    seccion_barra_conexion VARCHAR(255) COMMENT 'Sección de barra de conexión',
    pano_conexion VARCHAR(255) COMMENT 'Paño de conexión',
    fecha_estimada_conexion DATE COMMENT 'Fecha estimada de conexión',

    -- Calificación
    calificacion_id INT,
    calificacion_nombre VARCHAR(100) COMMENT 'Dedicada, Zonal, etc.',

    -- Etapa del proceso
    etapa_id INT,
    etapa VARCHAR(100) COMMENT 'Antecedentes, Admisibilidad, etc.',

    -- Otros campos
    nup INT COMMENT 'Número Único de Proyecto',
    cup VARCHAR(50) COMMENT 'Código Único de Proyecto',
    deleted_at TIMESTAMP COMMENT 'Fecha de eliminación (si aplica)',
    cancelled_at TIMESTAMP COMMENT 'Fecha de cancelación (si aplica)',

    -- Metadata de extracción
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha en que fue extraído de la API',

    -- Índices para búsquedas eficientes
    INDEX idx_tipo_solicitud (tipo_solicitud_id),
    INDEX idx_rut_empresa (rut_empresa),
    INDEX idx_proyecto_id (proyecto_id),
    INDEX idx_region (region_id),
    INDEX idx_estado (estado_solicitud_id),
    INDEX idx_create_date (create_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Solicitudes del CEN (tipo=6)';

-- ============================================================================

-- Tabla: documentos
-- Almacena la metadata de cada documento (tipo=11 de la API)
CREATE TABLE IF NOT EXISTS documentos (
    -- ID principal
    id BIGINT PRIMARY KEY COMMENT 'documento_id de la API (tipo=11)',

    -- Relación con solicitud
    solicitud_id BIGINT NOT NULL COMMENT 'FK a solicitudes.id',

    -- Información del archivo
    nombre VARCHAR(500) COMMENT 'Nombre del archivo',
    ruta_s3 TEXT COMMENT 'Ruta del archivo en AWS S3',

    -- Tipo de documento
    tipo_documento_id INT,
    tipo_documento VARCHAR(100) COMMENT 'Formulario SUCTD, Formulario SAC, etc.',

    -- Empresa
    empresa_id VARCHAR(20) COMMENT 'RUT de la empresa',
    razon_social VARCHAR(255),

    -- Fechas
    create_date TIMESTAMP COMMENT 'Fecha de creación del documento',
    update_date TIMESTAMP COMMENT 'Última actualización del documento',

    -- Estado y etapa
    estado_solicitud_id VARCHAR(20),
    etapa_id INT,
    etapa VARCHAR(100),

    -- Versión
    version_id VARCHAR(100) COMMENT 'ID de versión en S3',

    -- Flags
    visible TINYINT(1) DEFAULT 1 COMMENT 'Si el documento es visible',
    deleted TINYINT(1) DEFAULT 0 COMMENT 'Si el documento fue eliminado',

    -- Metadata de extracción y descarga
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha de extracción de metadata',
    downloaded TINYINT(1) DEFAULT 0 COMMENT 'Si el archivo fue descargado localmente',
    downloaded_at TIMESTAMP NULL COMMENT 'Fecha de descarga del archivo',
    local_path VARCHAR(500) COMMENT 'Ruta local del archivo descargado',
    download_error TEXT COMMENT 'Mensaje de error si la descarga falló',

    -- Foreign key
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    -- Índices
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_tipo_documento (tipo_documento),
    INDEX idx_tipo_documento_id (tipo_documento_id),
    INDEX idx_empresa_id (empresa_id),
    INDEX idx_visible (visible),
    INDEX idx_deleted (deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Documentos del CEN (tipo=11)';

-- ============================================================================

-- Vista: documentos_importantes
-- Filtra solo los documentos de interés: Formulario SUCTD, SAC y Formulario_proyecto_fehaciente
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

-- ============================================================================

-- Vista: solicitudes_con_documentos
-- Muestra solicitudes con conteo de documentos importantes
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

-- ============================================================================

-- Vista: documentos_ultimas_versiones
-- Filtra SOLO la última versión de cada documento por solicitud y tipo
-- Elimina duplicados cuando un documento se sube múltiples veces
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

-- ============================================================================

-- Vista: documentos_listos_para_parsear
-- Documentos únicos (última versión) que ya fueron descargados
-- Incluye columna de formato detectado para filtrar por tipo de archivo
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

-- ============================================================================

-- Vista: estadisticas_extraccion
-- Estadísticas generales de la extracción
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

-- ============================================================================
-- Fin del schema
-- ============================================================================
