-- Migración: Aumentar tamaño de comuna_nombre
-- Fecha: 2025-10-27
-- Descripción: Algunos nombres de comunas exceden VARCHAR(100)

USE sea;

-- Aumentar tamaño de comuna_nombre
ALTER TABLE proyectos MODIFY COLUMN comuna_nombre VARCHAR(255);

-- Registrar migración
INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('002_increase_comuna_nombre.sql', NOW());
