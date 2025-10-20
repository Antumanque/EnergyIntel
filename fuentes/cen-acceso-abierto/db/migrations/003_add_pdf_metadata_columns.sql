-- ============================================================================
-- Migración: Agregar columnas de metadata de PDFs
-- ============================================================================
-- Fecha: 2025-10-20
-- Descripción: Agrega columnas para almacenar metadata extraída de PDFs
--              (Producer, Author, Title, CreationDate)
-- ============================================================================

-- Agregar columnas de metadata a formularios_parseados
ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_producer VARCHAR(255) COMMENT 'Producer del PDF (ej: Microsoft: Print To PDF)';

ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_author VARCHAR(255) COMMENT 'Author del PDF';

ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_title VARCHAR(500) COMMENT 'Title del PDF';

ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_creation_date DATETIME COMMENT 'CreationDate del PDF';

-- Agregar índice en pdf_producer para queries
CREATE INDEX IF NOT EXISTS idx_pdf_producer ON formularios_parseados(pdf_producer);

SELECT 'Metadata columns added successfully' AS mensaje;
