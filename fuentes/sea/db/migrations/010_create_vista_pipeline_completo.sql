-- Migración: Crear vista de pipeline completo con todos los datos
-- Fecha: 2025-11-06
-- Descripción: Vista que muestra toda la cadena desde proyectos hasta inteligencia LLM

CREATE OR REPLACE VIEW vista_pipeline_completo AS
SELECT
    -- ETAPA 1: Proyectos
    p.expediente_id,
    p.expediente_nombre,
    p.titular,
    p.workflow_descripcion,
    p.region_nombre,
    p.inversion_mm,
    p.estado_proyecto,
    p.fecha_presentacion,

    -- ETAPA 2: Documentos del Expediente
    ed.id_documento,
    ed.tipo_documento,
    ed.folio,
    ed.fecha_generacion as doc_fecha_generacion,
    ed.url_documento,
    ed.processing_status as doc_processing_status,
    ed.failure_reason as doc_failure_reason,

    -- ETAPA 3: Links a PDF Resumen Ejecutivo
    rel.pdf_url,
    rel.pdf_filename,
    rel.texto_link,
    rel.processing_status as pdf_processing_status,
    rel.error_type as pdf_error_type,
    rel.error_message as pdf_error_message,
    rel.match_criteria,

    -- ETAPA 4: Inteligencia con Claude
    pi.id as inteligencia_id,
    pi.industria,
    pi.es_energia,
    pi.sub_industria,
    pi.ubicacion_geografica,
    pi.capacidad_electrica,
    pi.capacidad_termica,
    pi.requerimientos_infraestructura,
    pi.requerimientos_ingenieria,
    pi.oportunidad_negocio,
    pi.datos_clave,
    pi.modelo_usado,
    pi.status as llm_status,
    pi.error_message as llm_error_message,
    pi.pdf_text_length,
    pi.extracted_at as llm_extracted_at,

    -- Flags de completitud por etapa
    CASE WHEN ed.id_documento IS NOT NULL THEN 1 ELSE 0 END as tiene_documentos,
    CASE WHEN rel.id_documento IS NOT NULL THEN 1 ELSE 0 END as tiene_pdf_link,
    CASE WHEN pi.id IS NOT NULL THEN 1 ELSE 0 END as tiene_inteligencia,

    -- Estado del pipeline
    CASE
        WHEN pi.id IS NOT NULL AND pi.status = 'completed' THEN 'COMPLETO'
        WHEN pi.id IS NOT NULL AND pi.status = 'error' THEN 'ERROR_LLM'
        WHEN rel.id_documento IS NOT NULL AND rel.processing_status = 'pending' THEN 'PENDIENTE_LLM'
        WHEN rel.id_documento IS NOT NULL AND rel.processing_status = 'error' THEN 'ERROR_PDF'
        WHEN ed.id_documento IS NOT NULL AND ed.processing_status = 'pending' THEN 'PENDIENTE_PDF'
        WHEN ed.id_documento IS NOT NULL AND ed.processing_status = 'no_documents' THEN 'SIN_DOCUMENTOS'
        ELSE 'SIN_DOCUMENTOS'
    END as estado_pipeline

FROM proyectos p

-- ETAPA 2: LEFT JOIN con documentos del expediente
LEFT JOIN expediente_documentos ed
    ON p.expediente_id = ed.expediente_id
    AND ed.processing_status != 'no_documents'

-- ETAPA 3: LEFT JOIN con links a PDF
LEFT JOIN resumen_ejecutivo_links rel
    ON ed.id_documento = rel.id_documento

-- ETAPA 4: LEFT JOIN con inteligencia LLM
LEFT JOIN proyecto_inteligencia pi
    ON rel.id_documento = pi.id_documento

ORDER BY p.expediente_id DESC;

-- Registrar migración
INSERT INTO schema_migrations (migration_name)
VALUES ('010_create_vista_pipeline_completo.sql')
ON DUPLICATE KEY UPDATE migration_name=migration_name;
