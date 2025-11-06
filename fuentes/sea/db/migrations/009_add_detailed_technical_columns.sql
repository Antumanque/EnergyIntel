-- Migración: Agregar columnas técnicas detalladas a proyecto_inteligencia
-- Fecha: 2025-11-06
-- Descripción: Agregar columnas específicas para energía, infraestructura e ingeniería

ALTER TABLE proyecto_inteligencia
ADD COLUMN ubicacion_geografica TEXT COMMENT 'Ubicación geográfica detallada (región, comuna, coordenadas si aplica)',
ADD COLUMN capacidad_electrica VARCHAR(200) COMMENT 'Capacidad de generación eléctrica (ej: "150 MWp / 55 MWn")',
ADD COLUMN capacidad_termica VARCHAR(200) COMMENT 'Capacidad térmica si aplica (ej: "500 MW térmico")',
ADD COLUMN requerimientos_infraestructura TEXT COMMENT 'Infraestructura necesaria: líneas transmisión, subestaciones, caminos, etc.',
ADD COLUMN requerimientos_ingenieria TEXT COMMENT 'Requerimientos de ingeniería: estudios, diseños, consultorías necesarias';

-- Registrar migración
INSERT INTO schema_migrations (migration_name)
VALUES ('009_add_detailed_technical_columns.sql')
ON DUPLICATE KEY UPDATE migration_name=migration_name;
