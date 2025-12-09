-- Migración: Agregar columnas para RUTs extraídos de PDFs
-- Fecha: 2024-12-09

-- Columnas para los 3 primeros RUTs encontrados (acceso rápido)
ALTER TABLE resumen_ejecutivo_links
ADD COLUMN rut_1 VARCHAR(15) DEFAULT NULL COMMENT 'Primer RUT encontrado (formato XX.XXX.XXX-X)',
ADD COLUMN rut_2 VARCHAR(15) DEFAULT NULL COMMENT 'Segundo RUT encontrado',
ADD COLUMN rut_3 VARCHAR(15) DEFAULT NULL COMMENT 'Tercer RUT encontrado';

-- JSON con todos los RUTs y sus contextos
ALTER TABLE resumen_ejecutivo_links
ADD COLUMN ruts_json JSON DEFAULT NULL COMMENT 'Todos los RUTs encontrados con contexto';

-- Timestamp de extracción
ALTER TABLE resumen_ejecutivo_links
ADD COLUMN ruts_extracted_at DATETIME DEFAULT NULL COMMENT 'Fecha de extracción de RUTs';

-- Índices para búsquedas por RUT
CREATE INDEX idx_rel_rut_1 ON resumen_ejecutivo_links(rut_1);
CREATE INDEX idx_rel_rut_2 ON resumen_ejecutivo_links(rut_2);
CREATE INDEX idx_rel_rut_3 ON resumen_ejecutivo_links(rut_3);
