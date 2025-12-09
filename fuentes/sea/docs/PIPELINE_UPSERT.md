# Pipeline: Lógica de Upsert y Detección de Cambios

Este documento explica cómo el pipeline determina qué registros insertar, actualizar o ignorar cuando sincroniza datos desde la API del SEA (Sistema de Evaluación de Impacto Ambiental).

## Resumen Ejecutivo

Cuando el pipeline se ejecuta, cada proyecto de la API pasa por una clasificación:

| Clasificación | Qué significa | Qué hace el pipeline |
|---------------|---------------|---------------------|
| **Nuevo** | No existe en la BD | INSERT |
| **Actualizado** | Existe pero cambió algún campo | UPDATE |
| **Sin cambios** | Existe y es idéntico | SKIP (no escribe) |

## Columnas de Metadata

### Timestamps locales (nuestro tracking)

| Columna | Descripción |
|---------|-------------|
| `created_at` | Cuándo insertamos el registro por primera vez |
| `updated_at` | Cuándo modificamos el registro localmente (solo si hubo cambios) |

### Identificación

| Columna | Descripción |
|---------|-------------|
| `expediente_id` | Primary key, viene de la API del SEA |

## Flujo de Decisión

```
┌─────────────────────────────────────────────────────────────────┐
│                     Proyecto de la API                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ ¿Existe en BD?  │
                    │ (expediente_id) │
                    └─────────────────┘
                     │             │
                    NO            SÍ
                     │             │
                     ▼             ▼
              ┌──────────┐  ┌────────────────────┐
              │  NUEVO   │  │ Comparar 16 campos │
              │  INSERT  │  └────────────────────┘
              └──────────┘           │
                              ┌──────┴──────┐
                              │             │
                         ¿Cambió?      Sin cambios
                              │             │
                              ▼             ▼
                       ┌──────────┐  ┌──────────────┐
                       │ UPDATE   │  │ SKIP         │
                       │ updated_at = NOW() │  │ (no escribe) │
                       └──────────┘  └──────────────┘
```

## Campos Comparados (COMPARE_FIELDS)

Se comparan estos 16 campos para detectar cambios:

```
expediente_nombre, workflow_descripcion, region_nombre, comuna_nombre,
tipo_proyecto, descripcion_tipologia, razon_ingreso, titular,
inversion_mm, estado_proyecto, encargado, actividad_actual, etapa,
fecha_plazo, dias_legales, suspendido
```

**Campos que NO disparan update:**
- `expediente_id` (es la PK, no cambia)
- `expediente_url_ppal`, `expediente_url_ficha` (URLs estáticas)
- `fecha_presentacion`, `fecha_presentacion_format` (fecha de ingreso original)
- `inversion_mm_format`, `fecha_plazo_format` (formatos de display)
- `link_mapa_*` (datos de mapa)
- `acciones`, `ver_actividad` (metadatos de UI)
- `created_at`, `updated_at` (tracking interno)

## Modo Preview

El modo `--preview` ejecuta todo el análisis sin escribir a la base de datos:

```bash
# Ver qué se insertaría/actualizaría
python pipeline.py --preview

# Limitar a 5 páginas (testing rápido)
python pipeline.py --preview --max-pages 5

# Guardar reporte detallado en JSON
python pipeline.py --preview --output reporte.json
```

### Output del Preview

El preview muestra:
1. **Resumen de conteos**: cuántos nuevos, actualizados, sin cambios
2. **Detalle de nuevos**: lista de proyectos que se insertarían
3. **Detalle de actualizados**: proyectos con cambios, mostrando qué campo cambió

Ejemplo de output:

```
================================================================================
  PREVIEW - RESULTADO
================================================================================
ESTADÍSTICAS (sin escribir a BD):
  Proyectos nuevos:       3
  Proyectos actualizados: 15
  Proyectos sin cambios:  2,482
  Total analizados:       2,500

PROYECTOS NUEVOS (primeros 10):
  - [123456] Central Solar Atacama Norte...
    DIA | Antofagasta | En Calificación

PROYECTOS ACTUALIZADOS (primeros 10):
  - [789012] Parque Eólico Biobío...
    Campos: estado_proyecto, actividad_actual
================================================================================
```

### Formato del Reporte JSON

```json
{
  "nuevos": [
    {
      "expediente_id": 123456,
      "expediente_nombre": "Central Solar Atacama Norte",
      "workflow_descripcion": "DIA",
      "region_nombre": "Antofagasta",
      "estado_proyecto": "En Calificación",
      "titular": "Energía Solar SpA"
    }
  ],
  "actualizados": [
    {
      "expediente_id": 789012,
      "expediente_nombre": "Parque Eólico Biobío",
      "_changed_fields": [
        {"field": "estado_proyecto", "old": "En Evaluación", "new": "Aprobado"},
        {"field": "actividad_actual", "old": "Adenda", "new": "RCA"}
      ]
    }
  ],
  "sin_cambios": [...],
  "counts": {
    "nuevos": 3,
    "actualizados": 15,
    "sin_cambios": 2482,
    "total": 2500
  }
}
```

## Queries SQL Útiles

### Proyectos nuevos desde última corrida

```sql
-- Proyectos insertados desde la última corrida exitosa
SELECT
    expediente_id,
    expediente_nombre,
    workflow_descripcion,
    region_nombre,
    estado_proyecto,
    titular,
    created_at
FROM proyectos
WHERE created_at > (
    SELECT MAX(started_at)
    FROM pipeline_runs
    WHERE status = 'completed'
)
ORDER BY created_at DESC;
```

### Proyectos actualizados desde última corrida

```sql
-- Proyectos modificados desde la última corrida exitosa
SELECT
    expediente_id,
    expediente_nombre,
    workflow_descripcion,
    region_nombre,
    estado_proyecto,
    updated_at
FROM proyectos
WHERE updated_at > (
    SELECT MAX(started_at)
    FROM pipeline_runs
    WHERE status = 'completed'
)
AND updated_at != created_at  -- Excluir recién insertados
ORDER BY updated_at DESC;
```

### Delta desde fecha específica

```sql
-- Todo lo nuevo o modificado desde una fecha
SELECT
    expediente_id,
    expediente_nombre,
    workflow_descripcion,
    estado_proyecto,
    CASE
        WHEN created_at > '2025-12-01' THEN 'NUEVO'
        ELSE 'ACTUALIZADO'
    END as tipo_cambio,
    created_at,
    updated_at
FROM proyectos
WHERE created_at > '2025-12-01'
   OR updated_at > '2025-12-01'
ORDER BY GREATEST(created_at, COALESCE(updated_at, created_at)) DESC;
```

### Resumen por tipo de workflow

```sql
-- Conteo de nuevos por tipo de workflow esta semana
SELECT
    workflow_descripcion,
    COUNT(*) as nuevos
FROM proyectos
WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY workflow_descripcion
ORDER BY nuevos DESC;
```

### Historial de pipeline runs

```sql
-- Últimas 10 ejecuciones del pipeline
SELECT
    id,
    started_at,
    finished_at,
    status,
    proyectos_nuevos,
    proyectos_actualizados,
    proyectos_sin_cambios,
    duration_seconds
FROM pipeline_runs
ORDER BY started_at DESC
LIMIT 10;
```

## Casos de Uso Comunes

### 1. Monitoreo Diario

Ejecutar preview diariamente para detectar cambios:

```bash
# Guardar reporte con fecha
python pipeline.py --preview -o reportes/preview_$(date +%Y%m%d).json
```

### 2. Análisis de Cambios de Estado

Los cambios en `estado_proyecto` son particularmente importantes:

```bash
# Después del preview, buscar cambios de estado en el JSON
cat reporte.json | jq '.actualizados[] | select(._changed_fields[].field == "estado_proyecto")'
```

### 3. Detectar Nuevos Proyectos por Región

```bash
# Nuevos proyectos en región específica
cat reporte.json | jq '.nuevos[] | select(.region_nombre == "Metropolitana")'
```

### 4. Proyectos con Alta Inversión

```sql
-- Proyectos nuevos con inversión > 100 MM USD
SELECT
    expediente_id,
    expediente_nombre,
    titular,
    inversion_mm,
    workflow_descripcion,
    estado_proyecto
FROM proyectos
WHERE created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND inversion_mm > 100
ORDER BY inversion_mm DESC;
```

## Comportamiento de Timestamps

| Campo | Cuándo se actualiza |
|-------|---------------------|
| `created_at` | Solo en INSERT (primera vez que insertamos el registro) |
| `updated_at` | Solo cuando hay cambios reales en los 16 campos comparados |

## Pipeline Run Tracking

Cada ejecución del pipeline (no preview) se registra en `pipeline_runs`:

```sql
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;

-- Campos importantes:
-- proyectos_nuevos, proyectos_actualizados, proyectos_sin_cambios
-- status ('running', 'completed', 'failed')
-- duration_seconds
```

Esto permite:
- Auditar cuándo se ejecutó el pipeline
- Ver tendencias de nuevos registros
- Detectar problemas (status='failed')

## Preguntas Frecuentes

### ¿Por qué un registro aparece como "actualizado" si no cambió nada importante?

Los 16 campos comparados incluyen algunos que pueden cambiar frecuentemente:
- `estado_proyecto` (cambios de workflow)
- `actividad_actual` (etapa actual del proceso)
- `dias_legales`, `suspendido` (plazos legales)

Si quieres ignorar ciertos campos, puedes modificar `COMPARE_FIELDS` en `src/repositories/proyectos.py`.

### ¿Cómo sé si el preview es confiable?

El preview usa exactamente la misma lógica de comparación que el upsert real. La única diferencia es que no ejecuta los INSERT/UPDATE.

### ¿Puedo ver el historial de cambios?

Actualmente no hay tabla de historial. Las opciones son:
1. Guardar los reportes JSON del preview periódicamente
2. Implementar una tabla `proyectos_history` con triggers
