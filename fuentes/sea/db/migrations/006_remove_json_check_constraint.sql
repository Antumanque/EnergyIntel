-- Remove JSON check constraint from raw_data.data column
-- The constraint is too strict and fails with valid JSON from Python

ALTER TABLE raw_data MODIFY COLUMN data longtext COMMENT 'Response completo de la API en formato JSON';

INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('006_remove_json_check_constraint.sql', NOW());
