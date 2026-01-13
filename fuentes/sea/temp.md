# Queries útiles SEA

## Datos para dashboard
```sql
SELECT
    expediente_id,
    expediente_nombre,
    inversion_mm AS monto_inversion_mmusd,
    estado_proyecto,
    workflow_descripcion AS tipo_presentacion,
    expediente_url_ppal AS link_proyecto
FROM proyectos;
```
