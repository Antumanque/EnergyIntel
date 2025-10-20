-- ============================================================================
-- Schema para Formularios Parseados (PDF/XLSX)
-- ============================================================================
-- Este schema almacena los datos estructurados extraídos del parsing de
-- formularios PDF y XLSX del CEN (SAC, SUCTD, Fehaciente)
-- ============================================================================

USE cen_acceso_abierto;

-- ============================================================================
-- Tabla: formularios_parseados
-- Tracking de qué documentos ya fueron parseados
-- ============================================================================

CREATE TABLE IF NOT EXISTS formularios_parseados (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    documento_id BIGINT NOT NULL UNIQUE COMMENT 'FK a documentos.id',
    tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE') NOT NULL,
    formato_archivo ENUM('PDF', 'XLSX', 'XLS') NOT NULL,

    -- Estado del parsing
    parsing_exitoso BOOLEAN NOT NULL DEFAULT FALSE,
    parsing_error TEXT COMMENT 'Mensaje de error si falló el parsing',
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Metadata del parser
    parser_version VARCHAR(50) COMMENT 'Versión del parser usado (ej: 1.0.0)',

    -- Metadata del archivo PDF/XLSX (solo para PDFs)
    pdf_producer VARCHAR(255) COMMENT 'Producer del PDF (ej: Microsoft: Print To PDF)',
    pdf_author VARCHAR(255) COMMENT 'Author del PDF',
    pdf_title VARCHAR(500) COMMENT 'Title del PDF',
    pdf_creation_date DATETIME COMMENT 'CreationDate del PDF',

    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    INDEX idx_tipo_formulario (tipo_formulario),
    INDEX idx_parsing_exitoso (parsing_exitoso),
    INDEX idx_parsed_at (parsed_at),
    INDEX idx_pdf_producer (pdf_producer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracking de parsing de formularios PDF/XLSX';

-- ============================================================================
-- Tabla: formularios_sac_parsed
-- Datos estructurados del Formulario SAC (Solicitud de Autorización de Conexión)
-- ============================================================================

CREATE TABLE IF NOT EXISTS formularios_sac_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE COMMENT 'FK a formularios_parseados.id',
    documento_id BIGINT NOT NULL COMMENT 'FK a documentos.id',
    solicitud_id BIGINT NOT NULL COMMENT 'FK a solicitudes.id',

    -- Antecedentes Generales del Solicitante
    razon_social VARCHAR(255),
    rut VARCHAR(20),
    giro VARCHAR(255),
    domicilio_legal VARCHAR(500),

    -- Representante Legal
    representante_legal_nombre VARCHAR(255),
    representante_legal_email VARCHAR(255),
    representante_legal_telefono VARCHAR(50),

    -- Coordinadores de Proyecto (hasta 3)
    coordinador_proyecto_1_nombre VARCHAR(255),
    coordinador_proyecto_1_email VARCHAR(255),
    coordinador_proyecto_1_telefono VARCHAR(50),

    coordinador_proyecto_2_nombre VARCHAR(255),
    coordinador_proyecto_2_email VARCHAR(255),
    coordinador_proyecto_2_telefono VARCHAR(50),

    coordinador_proyecto_3_nombre VARCHAR(255),
    coordinador_proyecto_3_email VARCHAR(255),
    coordinador_proyecto_3_telefono VARCHAR(50),

    -- Antecedentes del Proyecto
    nombre_proyecto VARCHAR(255),
    tipo_proyecto VARCHAR(50) COMMENT 'Gen / Trans / Consumo',
    tecnologia VARCHAR(255) COMMENT 'Solar, Eólico, Híbrido, etc.',
    potencia_nominal_mw VARCHAR(50) COMMENT 'Puede ser "400 + 100" por eso VARCHAR',
    consumo_propio_mw DECIMAL(10,2),
    factor_potencia DECIMAL(5,2),

    -- Ubicación Geográfica del Proyecto
    proyecto_coordenadas_utm_huso VARCHAR(10),
    proyecto_coordenadas_utm_este VARCHAR(50),
    proyecto_coordenadas_utm_norte VARCHAR(50),
    proyecto_comuna VARCHAR(100),
    proyecto_region VARCHAR(100),

    -- Antecedentes del Punto de Conexión
    nombre_subestacion VARCHAR(255),
    nivel_tension_kv VARCHAR(50),
    caracter_conexion VARCHAR(50) COMMENT 'Indefinido / Temporal',
    fecha_estimada_construccion DATE,
    fecha_estimada_interconexion DATE,

    -- Ubicación Geográfica del Punto de Conexión
    conexion_coordenadas_utm_huso VARCHAR(10),
    conexion_coordenadas_utm_este VARCHAR(50),
    conexion_coordenadas_utm_norte VARCHAR(50),
    conexion_comuna VARCHAR(100),
    conexion_region VARCHAR(100),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_rut (rut),
    INDEX idx_nombre_proyecto (nombre_proyecto),
    INDEX idx_tipo_proyecto (tipo_proyecto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios SAC (PDF/XLSX)';

-- ============================================================================
-- Tabla: formularios_suctd_parsed
-- Datos estructurados del Formulario SUCTD (Solicitud de Uso de Capacidad Técnica Dedicada)
-- TODO: Completar después de analizar estructura de formularios SUCTD
-- ============================================================================

CREATE TABLE IF NOT EXISTS formularios_suctd_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE COMMENT 'FK a formularios_parseados.id',
    documento_id BIGINT NOT NULL COMMENT 'FK a documentos.id',
    solicitud_id BIGINT NOT NULL COMMENT 'FK a solicitudes.id',

    -- Campos específicos de SUCTD
    -- (A completar después de analizar estructura)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios SUCTD (PDF/XLSX)';

-- ============================================================================
-- Tabla: formularios_fehaciente_parsed
-- Datos estructurados del Formulario de Proyecto Fehaciente
-- TODO: Completar después de analizar estructura
-- ============================================================================

CREATE TABLE IF NOT EXISTS formularios_fehaciente_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE COMMENT 'FK a formularios_parseados.id',
    documento_id BIGINT NOT NULL COMMENT 'FK a documentos.id',
    solicitud_id BIGINT NOT NULL COMMENT 'FK a solicitudes.id',

    -- Campos específicos de Fehaciente
    -- (A completar después de analizar estructura)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios Fehaciente (PDF/XLSX)';

-- ============================================================================
-- Vistas Útiles
-- ============================================================================

-- Vista: solicitudes_con_formularios_parseados
-- Muestra qué solicitudes tienen formularios parseados
CREATE OR REPLACE VIEW solicitudes_con_formularios_parseados AS
SELECT
    s.id AS solicitud_id,
    s.proyecto,
    s.tipo_solicitud,
    s.rut_empresa,

    -- Conteo de formularios parseados
    COUNT(DISTINCT fp.id) AS total_formularios_parseados,
    MAX(CASE WHEN fp.tipo_formulario = 'SAC' AND fp.parsing_exitoso = 1 THEN 1 ELSE 0 END) AS tiene_sac_parseado,
    MAX(CASE WHEN fp.tipo_formulario = 'SUCTD' AND fp.parsing_exitoso = 1 THEN 1 ELSE 0 END) AS tiene_suctd_parseado,
    MAX(CASE WHEN fp.tipo_formulario = 'FEHACIENTE' AND fp.parsing_exitoso = 1 THEN 1 ELSE 0 END) AS tiene_fehaciente_parseado,

    -- Datos específicos de SAC (si existe)
    sac.nombre_proyecto AS sac_nombre_proyecto,
    sac.potencia_nominal_mw AS sac_potencia_nominal,
    sac.tecnologia AS sac_tecnologia,
    sac.nombre_subestacion AS sac_subestacion

FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
LEFT JOIN formularios_sac_parsed sac ON fp.id = sac.formulario_parseado_id

GROUP BY s.id, s.proyecto, s.tipo_solicitud, s.rut_empresa,
         sac.nombre_proyecto, sac.potencia_nominal_mw, sac.tecnologia, sac.nombre_subestacion;

-- ============================================================================
-- Fin del schema
-- ============================================================================

SELECT 'Schema de formularios parseados creado exitosamente' AS mensaje;
