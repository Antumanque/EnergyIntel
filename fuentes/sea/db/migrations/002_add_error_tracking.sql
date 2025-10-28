-- Migración 002: Agregar tracking de errores para framework iterativo
-- Fecha: 2025-10-27

-- Agregar columnas de tracking a expediente_documentos
ALTER TABLE expediente_documentos 
ADD COLUMN processing_status ENUM('pending', 'success', 'error') DEFAULT 'pending',
ADD COLUMN error_type VARCHAR(100) DEFAULT NULL,
ADD COLUMN error_message TEXT DEFAULT NULL,
ADD COLUMN attempts INT DEFAULT 0,
ADD COLUMN last_attempt_at DATETIME DEFAULT NULL;

-- Agregar columnas de tracking a resumen_ejecutivo_links
ALTER TABLE resumen_ejecutivo_links
ADD COLUMN processing_status ENUM('pending', 'success', 'error') DEFAULT 'pending',
ADD COLUMN error_type VARCHAR(100) DEFAULT NULL,
ADD COLUMN error_message TEXT DEFAULT NULL,
ADD COLUMN attempts INT DEFAULT 0,
ADD COLUMN last_attempt_at DATETIME DEFAULT NULL;

-- Índices para búsqueda rápida de errores
CREATE INDEX idx_expediente_docs_status ON expediente_documentos(processing_status);
CREATE INDEX idx_expediente_docs_error_type ON expediente_documentos(error_type);
CREATE INDEX idx_resumen_links_status ON resumen_ejecutivo_links(processing_status);
CREATE INDEX idx_resumen_links_error_type ON resumen_ejecutivo_links(error_type);

-- Registrar migración
INSERT INTO schema_migrations (migration_name) VALUES ('002_add_error_tracking.sql');
