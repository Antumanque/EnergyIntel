-- Add match_criteria column to track which pattern matched
ALTER TABLE resumen_ejecutivo_links
ADD COLUMN match_criteria VARCHAR(100)
COMMENT 'Criterio/patrón que identificó este link como resumen ejecutivo';

-- Add index for analytics
CREATE INDEX idx_match_criteria ON resumen_ejecutivo_links(match_criteria);
