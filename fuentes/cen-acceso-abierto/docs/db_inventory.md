# Inventario Base de Datos `acceso_abierto`

Generado: 2026-01-13

## Resumen

| Tipo | Cantidad |
|------|----------|
| Tablas Base | 19 |
| Vistas | 18 |

---

## TABLAS

### Tablas Core del Pipeline

| Tabla | Filas | Usado en Pipeline | Creador | Descripción |
|-------|-------|-------------------|---------|-------------|
| `solicitudes` | 2,512 | ✅ Sí | root (init.sql) | Tabla principal de solicitudes CEN |
| `documentos` | 2,575 | ✅ Sí | root (init.sql) | Documentos asociados a solicitudes |
| `pipeline_runs` | 15 | ✅ Sí | root (migration 007) | Registro de ejecuciones del pipeline |
| `raw_api_data` | 31,942 | ✅ Sí | root (init.sql) | Respuestas crudas de la API CEN |
| `solicitudes_history` | 2,507 | ✅ Sí | root (migration 009) | Historial de cambios en solicitudes |
| `documentos_history` | 1,284 | ✅ Sí | chris (manual) | Historial de cambios en documentos |

### Tablas de Formularios Parseados

| Tabla | Filas | Usado en Pipeline | Creador | Descripción |
|-------|-------|-------------------|---------|-------------|
| `formularios_parseados` | 2,282 | ✅ Sí | root (schema) | Metadata de formularios extraídos |
| `formularios_sac_parsed` | 1,198 | ✅ Sí | root (schema) | Formularios SAC parseados |
| `formularios_fehaciente_parsed` | 198 | ✅ Sí | root (schema) | Formularios Fehaciente parseados |
| `formularios_suctd_parsed` | 546 | ❌ No | root (schema) | Formularios SUCTD parseados (sin uso activo) |

### Tablas de Lookup/Catálogos

| Tabla | Filas | Usado en Pipeline | Creador | Descripción |
|-------|-------|-------------------|---------|-------------|
| `tipo_solicitud` | 3 | ❌ No (solo ref) | root (init.sql) | Catálogo tipos de solicitud |
| `estado_solicitud` | 6 | ❌ No (solo ref) | root (init.sql) | Catálogo estados de solicitud |
| `tipo_tecnologia` | 9 | ❌ No (solo ref) | root (init.sql) | Catálogo tipos de tecnología |
| `segmento_transmision` | 4 | ❌ No (solo ref) | root (init.sql) | Catálogo segmentos de transmisión |
| `interesados` | 3,861 | ❌ No | root (init.sql) | Empresas interesadas en solicitudes |

### Tablas de Sistema

| Tabla | Filas | Usado en Pipeline | Creador | Descripción |
|-------|-------|-------------------|---------|-------------|
| `schema_migrations` | 8 | ❌ No (sistema) | root | Control de migraciones aplicadas |
| `parsing_feedback` | 0 | ❌ No | root (schema) | Feedback de parsing (sin uso) |

### ⚠️ Tablas Sospechosas/Residuales

| Tabla | Filas | Usado en Pipeline | Creador | Descripción | Recomendación |
|-------|-------|-------------------|---------|-------------|---------------|
| `salida_1` | 2,756 | ❌ No | **desconocido** (no en migrations) | Tabla de salida/reporte, parece staging para exports | **REVISAR** - posible residual |
| `_h_subestacion` | 996 | ❌ No | **desconocido** (no en migrations) | Lookup de subestaciones por nombre_se | **REVISAR** - tabla auxiliar manual |
| `_distancia_ssee` | 225 | ❌ No | **desconocido** (no en migrations) | Distancias calculadas a subestaciones | **REVISAR** - tabla auxiliar manual |

---

## VISTAS

### Vistas del Pipeline (usadas en código)

| Vista | Definer | Usado en Pipeline | Descripción |
|-------|---------|-------------------|-------------|
| `documentos_listos_para_parsear` | root@10.% | ✅ Sí | Docs pendientes de parseo |
| `documentos_ultimas_versiones` | root@10.% | ✅ Sí | Última versión de cada documento |
| `documentos_importantes` | root@10.% | ✅ Sí (indirecto) | Filtro de docs relevantes para parseo |
| `successful_fetches` | root@10.% | ✅ Sí | Fetches exitosos de la API |
| `latest_fetches` | root@10.% | ✅ Sí | Último fetch por URL |

### Vistas de Análisis/Historial (creadas por Claude)

| Vista | Definer | Usado en Pipeline | Descripción |
|-------|---------|-------------------|-------------|
| `v_cambios_solicitudes` | chris@10.% | ❌ No (análisis) | Detalle de cambios en solicitudes |
| `v_cambios_detalle` | chris@10.% | ❌ No (análisis) | Cambios con columnas old/new expandidas |
| `v_resumen_pipelines` | chris@10.% | ❌ No (análisis) | Resumen estadístico por pipeline |
| `v_cambios_documentos` | chris@10.% | ❌ No (análisis) | Detalle de cambios en documentos |
| `v_resumen_documentos_pipelines` | chris@10.% | ❌ No (análisis) | Resumen docs por pipeline |

### ⚠️ Vistas Sospechosas/Posible Overlap

| Vista | Definer | Usado en Pipeline | Descripción | Recomendación |
|-------|---------|-------------------|-------------|---------------|
| `estadisticas_extraccion` | root@10.% | ❌ No | Stats de extracción | **REVISAR** - posible overlap con v_resumen_pipelines |
| `solicitudes_cambios_por_dia` | root@10.% | ❌ No | Cambios agrupados por día | **REVISAR** - overlap con v_cambios_solicitudes? |
| `solicitudes_cambios_recientes` | root@10.% | ❌ No | Cambios recientes | **REVISAR** - overlap con v_cambios_solicitudes? |
| `solicitudes_con_documentos` | root@10.% | ❌ No | Join solicitudes-docs | **REVISAR** - utilidad? |
| `solicitudes_con_formularios_parseados` | root@10.% | ❌ No | Join solicitudes-forms | **REVISAR** - utilidad? |
| `solicitudes_delta` | root@10.% | ❌ No | Diferencias entre runs | **REVISAR** - overlap con history tables? |
| `solicitudes_transiciones_estado` | root@10.% | ❌ No | Cambios de estado | **REVISAR** - overlap con history? |
| `solicitudes_ultimo_run` | root@10.% | ❌ No | Datos del último run | **REVISAR** - utilidad? |

---

## Análisis de Overlaps Potenciales

### 1. Tracking de Cambios
Hay múltiple formas de ver cambios:
- `solicitudes_history` / `documentos_history` (tablas) - **FUENTE DE VERDAD**
- `v_cambios_*` (vistas chris) - Vistas sobre las tablas history
- `solicitudes_cambios_*`, `solicitudes_delta`, `solicitudes_transiciones_estado` (vistas root) - **POSIBLE DEPRECAR**

**Recomendación**: Las vistas de root para cambios podrían estar obsoletas si ahora usamos las tablas `*_history`.

### 2. Tablas sin Migration
Las siguientes tablas no tienen migration y fueron creadas manualmente:
- `salida_1` - Parece tabla de export/reporte
- `_h_subestacion` - Lookup de subestaciones
- `_distancia_ssee` - Cálculos de distancia

**Recomendación**: Documentar origen y decidir si migrar a código o eliminar.

---

## Archivos de Migración

```
db/migrations/
├── 001_add_download_error_column.sql
├── 002_add_documentos_ultimas_versiones_view.sql
├── 003_add_pdf_metadata_columns.sql
├── 004_expand_varchar_columns.sql
├── 005_add_zip_formato.sql
├── 006_add_updated_at_columns.sql
├── 007_add_pipeline_runs_and_smart_upsert.sql
├── 008_align_tracking_with_sea.sql
├── 008_simplify_metadata_columns.sql  ⚠️ DUPLICADO de 008
├── 009_create_solicitudes_history.sql
└── 009_recreate_views_after_column_rename.sql  ⚠️ DUPLICADO de 009
```

**Nota**: Hay archivos 008 y 009 duplicados - revisar cuáles están aplicados.
