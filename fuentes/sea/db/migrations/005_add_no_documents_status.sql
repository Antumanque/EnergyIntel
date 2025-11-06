-- Migración 005: Agregar estado 'no_documents' a processing_status
-- Fecha: 2025-10-28
-- Propósito: Trackear expedientes que fueron intentados pero no tienen documentos EIA/DIA

ALTER TABLE expediente_documentos
MODIFY COLUMN processing_status ENUM('pending', 'success', 'error', 'no_documents')
DEFAULT 'pending';

-- Registrar migración
INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('005_add_no_documents_status.sql', NOW())
ON DUPLICATE KEY UPDATE applied_at = NOW();
