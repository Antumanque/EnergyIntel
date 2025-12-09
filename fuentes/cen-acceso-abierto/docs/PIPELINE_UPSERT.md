# Pipeline: Lógica de Upsert y Detección de Cambios

Este documento explica cómo el pipeline determina qué registros insertar, actualizar o ignorar cuando sincroniza datos desde la API del CEN (Coordinador Eléctrico Nacional).

## Resumen Ejecutivo

Cuando el pipeline se ejecuta, cada registro de la API pasa por una clasificación:

| Clasificación | Qué significa | Qué hace el pipeline |
|---------------|---------------|---------------------|
| **Nueva** | No existe en la BD | INSERT |
| **Actualizada** | Existe pero cambió algún campo | UPDATE |
| **Sin cambios** | Existe y es idéntica | SKIP (no escribe) |

## Columnas de Metadata

### Timestamps locales (nuestro tracking)

| Columna | Descripción |
|---------|-------------|
| `created_at` | Cuándo insertamos el registro por primera vez |
| `updated_at` | Cuándo modificamos el registro localmente (solo si hubo cambios) |

### Timestamps del CEN (vienen de la API)

| Columna | Descripción |
|---------|-------------|
| `create_date` | Cuándo el CEN creó el registro |
| `api_update_date` | Cuándo el CEN modificó el registro |

### Identificación

| Columna | Descripción |
|---------|-------------|
| `id` | Primary key, viene de la API del CEN |

## Flujo de Decisión

```
┌─────────────────────────────────────────────────────────────────┐
│                     Registro de la API                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ ¿Existe en BD?  │
                    └─────────────────┘
                     │             │
                    NO            SÍ
                     │             │
                     ▼             ▼
              ┌──────────┐  ┌────────────────────┐
              │  NUEVA   │  │ Comparar campos    │
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

## Campos Comparados

### Solicitudes

Se comparan estos 32 campos para detectar cambios:

```
tipo_solicitud_id, tipo_solicitud, estado_solicitud_id, estado_solicitud,
api_update_date, proyecto_id, proyecto, rut_empresa, razon_social,
tipo_tecnologia_nombre, potencia_nominal, comuna_id, comuna,
provincia_id, provincia, region_id, region, lat, lng,
nombre_se, nivel_tension, seccion_barra_conexion, pano_conexion,
fecha_estimada_conexion, calificacion_id, calificacion_nombre,
etapa_id, etapa, nup, cup, deleted_at, cancelled_at
```

**Campos que NO disparan update:**
- `id` (es la PK, no cambia)
- `create_date` (fecha de creación en el CEN)
- `created_at` (cuándo insertamos el registro)
- `updated_at` (se actualiza automáticamente al detectar cambios)

### Documentos

Se comparan estos 14 campos:

```
solicitud_id, nombre, ruta_s3, tipo_documento_id, tipo_documento,
empresa_id, razon_social, api_update_date, estado_solicitud_id,
etapa_id, etapa, version_id, visible, deleted
```

**Campos excluidos de comparación:**
- `downloaded`, `downloaded_at`, `local_path`, `download_error` (estado de descarga local)
- `created_at`, `updated_at` (tracking interno)

## Modo Preview

El modo `--preview` ejecuta todo el análisis sin escribir a la base de datos:

```bash
# Ver qué se insertaría/actualizaría
python pipeline.py --preview

# Guardar reporte detallado en JSON
python pipeline.py --preview --output reporte.json
```

### Output del Preview

El preview muestra:
1. **Resumen de conteos**: cuántas nuevas, actualizadas, sin cambios
2. **Detalle de nuevas**: lista de registros que se insertarían
3. **Detalle de actualizadas**: registros con cambios, mostrando qué campo cambió

Ejemplo de output:

```
================================================================================
  PREVIEW DEL PIPELINE
================================================================================
Tiempo total: 45.2 segundos (0.8 minutos)

SOLICITUDES:
   • En API:        2,460
   • Nuevas:        5
   • Actualizadas:  12
   • Sin cambios:   2,443

DOCUMENTOS:
   • Nuevos:        8
   • Actualizados:  3

================================================================================
  DETALLES DEL PREVIEW
================================================================================

SOLICITUDES NUEVAS (5):
   • ID 2456: Parque Solar Atacama (Empresa Solar SpA)
   • ID 2457: Central Eólica Norte (Vientos Chile SA)
   ...

SOLICITUDES CON CAMBIOS (12):
   • ID 1234: Parque Fotovoltaico Sur
      - estado_solicitud: En Evaluación → Aprobada
      - fecha_estimada_conexion: 2025-06-01 → 2025-09-15
   ...
```

### Formato del Reporte JSON

```json
{
  "generated_at": "2025-12-08T15:30:00",
  "stats": {
    "solicitudes_en_api": 2460,
    "solicitudes_nuevas": 5,
    "solicitudes_actualizadas": 12,
    "solicitudes_sin_cambios": 2443,
    "documentos_nuevos": 8,
    "documentos_actualizados": 3
  },
  "solicitudes": {
    "nuevas": [
      {
        "id": 2456,
        "proyecto": "Parque Solar Atacama",
        "razon_social": "Empresa Solar SpA",
        "estado_solicitud": "En Evaluación",
        "potencia_nominal": 150.0
      }
    ],
    "actualizadas": [
      {
        "id": 1234,
        "proyecto": "Parque Fotovoltaico Sur",
        "_changed_fields": [
          {"field": "estado_solicitud", "old": "En Evaluación", "new": "Aprobada"},
          {"field": "fecha_estimada_conexion", "old": "2025-06-01", "new": "2025-09-15"}
        ]
      }
    ],
    "sin_cambios_count": 2443
  },
  "documentos": {
    "nuevos": [...],
    "actualizados": [...],
    "sin_cambios_count": 1520
  }
}
```

## Queries SQL Útiles

### Solicitudes nuevas desde última corrida

```sql
-- Solicitudes insertadas desde la última corrida exitosa
SELECT
    id,
    proyecto,
    razon_social,
    tipo_tecnologia_nombre,
    potencia_nominal,
    estado_solicitud,
    region,
    created_at
FROM solicitudes
WHERE created_at > (
    SELECT MAX(started_at)
    FROM pipeline_runs
    WHERE status = 'completed'
)
ORDER BY created_at DESC;
```

### Solicitudes actualizadas desde última corrida

```sql
-- Solicitudes modificadas desde la última corrida exitosa
SELECT
    id,
    proyecto,
    razon_social,
    estado_solicitud,
    etapa,
    updated_at
FROM solicitudes
WHERE updated_at > (
    SELECT MAX(started_at)
    FROM pipeline_runs
    WHERE status = 'completed'
)
AND updated_at != created_at  -- Excluir recién insertadas
ORDER BY updated_at DESC;
```

### Delta desde fecha específica

```sql
-- Todo lo nuevo o modificado desde una fecha
SELECT
    id,
    proyecto,
    razon_social,
    estado_solicitud,
    potencia_nominal,
    CASE
        WHEN created_at > '2025-12-01' THEN 'NUEVO'
        ELSE 'ACTUALIZADO'
    END as tipo_cambio,
    created_at,
    updated_at
FROM solicitudes
WHERE created_at > '2025-12-01'
   OR updated_at > '2025-12-01'
ORDER BY GREATEST(created_at, COALESCE(updated_at, created_at)) DESC;
```

### Resumen por tipo de tecnología

```sql
-- Conteo de nuevas solicitudes por tecnología esta semana
SELECT
    tipo_tecnologia_nombre,
    COUNT(*) as nuevas,
    SUM(potencia_nominal) as potencia_total_mw
FROM solicitudes
WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY tipo_tecnologia_nombre
ORDER BY nuevas DESC;
```

### Historial de pipeline runs

```sql
-- Últimas 10 ejecuciones del pipeline
SELECT
    id,
    started_at,
    finished_at,
    status,
    solicitudes_nuevas,
    solicitudes_actualizadas,
    solicitudes_sin_cambios,
    documentos_nuevos,
    documentos_actualizados,
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

Los cambios en `estado_solicitud` son particularmente importantes:

```bash
# Después del preview, buscar cambios de estado en el JSON
cat reporte.json | jq '.solicitudes.actualizadas[] | select(._changed_fields[].field == "estado_solicitud")'
```

### 3. Detectar Nuevos Proyectos

```bash
# Nuevos proyectos con potencia > 100 MW
cat reporte.json | jq '.solicitudes.nuevas[] | select(.potencia_nominal > 100)'
```

### 4. Proyectos Solares Nuevos

```sql
-- Proyectos solares ingresados este mes
SELECT
    id,
    proyecto,
    razon_social,
    potencia_nominal,
    region,
    estado_solicitud
FROM solicitudes
WHERE created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND tipo_tecnologia_nombre LIKE '%Solar%'
ORDER BY potencia_nominal DESC;
```

## Comportamiento de Timestamps

| Campo | Cuándo se actualiza |
|-------|---------------------|
| `created_at` | Solo en INSERT (primera vez que insertamos el registro) |
| `updated_at` | Solo cuando hay cambios reales en campos comparados |
| `create_date` | Nunca (viene de la API, es inmutable) |
| `api_update_date` | Viene de la API, se compara pero no se modifica localmente |

## Normalización de Datos

Antes de comparar, el pipeline normaliza:

1. **Fechas ISO 8601** → formato MySQL
   - `2025-10-15T17:22:32.000Z` → `2025-10-15 17:22:32`

2. **Valores None/null** → se manejan consistentemente
   - `None`, `'null'`, `''` → `None`

3. **Comparación como strings**
   - Todos los valores se convierten a string para comparar
   - Esto evita problemas con tipos mixtos (int vs str)

## Pipeline Run Tracking

Cada ejecución del pipeline (no preview) se registra en `pipeline_runs`:

```sql
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;

-- Campos importantes:
-- solicitudes_nuevas, solicitudes_actualizadas, solicitudes_sin_cambios
-- documentos_nuevos, documentos_actualizados
-- status ('running', 'completed', 'failed')
-- duration_seconds
```

Esto permite:
- Auditar cuándo se ejecutó el pipeline
- Ver tendencias de nuevos registros
- Detectar problemas (status='failed')

## Preguntas Frecuentes

### ¿Por qué un registro aparece como "actualizado" si no cambió nada importante?

Los 32 campos comparados incluyen algunos que pueden cambiar frecuentemente:
- `api_update_date` (cambia si alguien edita cualquier cosa en el CEN)
- `etapa`, `estado_solicitud` (cambios de workflow)

Si quieres ignorar ciertos campos, puedes modificar `SOLICITUD_COMPARE_FIELDS` en `src/repositories/cen.py`.

### ¿Cómo sé si el preview es confiable?

El preview usa exactamente la misma lógica de comparación que el upsert real. La única diferencia es que no ejecuta los INSERT/UPDATE.

### ¿Puedo ver el historial de cambios?

Actualmente no hay tabla de historial. Las opciones son:
1. Guardar los reportes JSON del preview periódicamente
2. Implementar una tabla `solicitudes_history` con triggers
