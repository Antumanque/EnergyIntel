# Vistas de Base de Datos para Documentos

## Contexto

Las solicitudes pueden tener **múltiples versiones** del mismo documento (cuando se re-sube). Para evitar procesar duplicados, se crearon vistas que filtran automáticamente solo la **última versión** de cada documento.

## Vistas Disponibles

### 1. `documentos_ultimas_versiones`

**Propósito**: Filtra SOLO la última versión de cada documento por `solicitud_id` y `tipo_documento`.

**Criterio de última versión**:
```sql
ORDER BY create_date DESC, id DESC
```

**Uso**:
```sql
-- Obtener todas las últimas versiones de formularios
SELECT *
FROM documentos_ultimas_versiones
WHERE tipo_documento IN ('Formulario SAC', 'Formulario SUCTD', 'Formulario_proyecto_fehaciente');
```

**Estadísticas**:
- **Total documentos únicos**: 2,315 (vs 2,542 con duplicados)
- **Duplicados eliminados**: 227 (9%)
- **Solicitudes con múltiples versiones**: 204 (8%)

---

### 2. `documentos_listos_para_parsear`

**Propósito**: Documentos únicos (última versión) que YA fueron descargados y están listos para ser parseados.

**Filtros aplicados**:
- ✅ Solo última versión (usa `documentos_ultimas_versiones`)
- ✅ `downloaded = 1`
- ✅ `local_path IS NOT NULL`
- ✅ Solo formularios importantes (SAC, SUCTD, Fehaciente)
- ✅ Columna adicional `formato_archivo` (PDF, XLSX, XLS, ZIP, RAR, OTRO)

**Uso desde parsers**:
```sql
-- PDF Parser: Obtener todos los PDFs listos para parsear
SELECT id, solicitud_id, tipo_documento, nombre, local_path
FROM documentos_listos_para_parsear
WHERE formato_archivo = 'PDF'
ORDER BY solicitud_id;

-- Excel Parser: Obtener todos los XLSX listos para parsear
SELECT id, solicitud_id, tipo_documento, nombre, local_path
FROM documentos_listos_para_parsear
WHERE formato_archivo IN ('XLSX', 'XLS')
ORDER BY solicitud_id;

-- Filtrar por tipo de formulario específico
SELECT id, solicitud_id, nombre, local_path, formato_archivo
FROM documentos_listos_para_parsear
WHERE tipo_documento = 'Formulario SUCTD'
  AND formato_archivo = 'PDF';
```

---

## Ejemplos de Uso en Python

### Desde Repository:

```python
from src.repositories.cen import get_cen_db_manager

db_manager = get_cen_db_manager()

# Obtener PDFs listos para parsear
with db_manager.connection() as conn:
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, solicitud_id, tipo_documento, nombre, local_path
        FROM documentos_listos_para_parsear
        WHERE formato_archivo = 'PDF'
        ORDER BY solicitud_id
        LIMIT 100
    """)

    pdfs_to_parse = cursor.fetchall()

for doc in pdfs_to_parse:
    print(f"Parseando: {doc['nombre']} (solicitud {doc['solicitud_id']})")
    # Llamar al PDF parser...
```

---

## Comparación: Con vs Sin Vista

### ❌ Sin vista (query complejo):
```sql
-- Código repetitivo y propenso a errores
SELECT d.*
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY solicitud_id, tipo_documento
               ORDER BY create_date DESC, id DESC
           ) as rn
    FROM documentos
    WHERE deleted = 0 AND visible = 1
) d
WHERE d.rn = 1
  AND d.downloaded = 1
  AND d.local_path IS NOT NULL
  AND d.tipo_documento IN ('Formulario SAC', 'Formulario SUCTD', 'Formulario_proyecto_fehaciente')
  AND d.nombre LIKE '%.pdf';
```

### ✅ Con vista (simple y claro):
```sql
-- Código limpio y mantenible
SELECT *
FROM documentos_listos_para_parsear
WHERE formato_archivo = 'PDF';
```

---

## Distribución de Formatos (Últimas Versiones)

Basado en análisis de `documentos_ultimas_versiones`:

| Formato | Cantidad | Porcentaje |
|---------|----------|------------|
| PDF     | 1,541    | 66.6%      |
| XLSX    | 703      | 30.4%      |
| ZIP/RAR | 52       | 2.2%       |
| XLS     | 19       | 0.8%       |

**Total**: 2,315 documentos únicos

---

## Notas Importantes

1. **Siempre usar las vistas**: No consultar directamente la tabla `documentos` para evitar duplicados
2. **Schema automático**: Las vistas se crean automáticamente en `db/schema_solicitudes.sql`
3. **Migrations**: Las vistas también están en `db/migrations/002_add_documentos_ultimas_versiones_view.sql`
4. **Performance**: Las vistas usan window functions (ROW_NUMBER), ten esto en cuenta para queries grandes

---

## Queries Útiles de Estadísticas

```sql
-- Conteo por formato (solo últimas versiones)
SELECT formato_archivo, COUNT(*) as total
FROM documentos_listos_para_parsear
GROUP BY formato_archivo;

-- Conteo por tipo de formulario y formato
SELECT tipo_documento, formato_archivo, COUNT(*) as total
FROM documentos_listos_para_parsear
GROUP BY tipo_documento, formato_archivo
ORDER BY tipo_documento, total DESC;

-- Solicitudes con documentos descargados listos para parsear
SELECT
    s.id,
    s.proyecto,
    s.tipo_solicitud,
    COUNT(d.id) as docs_listos
FROM solicitudes s
INNER JOIN documentos_listos_para_parsear d ON s.id = d.solicitud_id
GROUP BY s.id, s.proyecto, s.tipo_solicitud
ORDER BY docs_listos DESC;
```
