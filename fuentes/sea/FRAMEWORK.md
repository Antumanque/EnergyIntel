# Framework Iterativo de Procesamiento SEA

**PRIORIDAD ALTA**: Este framework es la metodología central para mejorar el pipeline incrementalmente basándose en datos reales.

## Filosofía

En vez de procesar todo el dataset de una vez y esperar que funcione, usamos un **enfoque iterativo data-driven**:

1. ✅ Procesar un **batch pequeño** (1,000 proyectos)
2. ✅ Ver qué **falló y por qué**
3. ✅ Arreglar el **error más común**
4. ✅ Limpiar y **re-ejecutar**
5. ✅ Medir **mejora**
6. 🔁 **Repetir** hasta maximizar conversión

## Componentes del Framework

### 1. `batch_processor.py` - Procesador por Lotes

Procesa N proyectos/documentos y guarda errores detallados en BD.

**Uso**:
```bash
# Procesar 1000 proyectos (Etapa 2: Documentos del expediente)
python batch_processor.py --batch-size 1000 --stage 2

# Procesar 500 documentos (Etapa 3: Links a PDF)
python batch_processor.py --batch-size 500 --stage 3
```

**Salida**:
```
================================================================================
ETAPA 3: EXTRACCIÓN DE LINKS A PDF RESUMEN EJECUTIVO
================================================================================

Procesando 500 documentos...

[1/500] Documento 2160823108... ✓ Link guardado: Resumen Ejecutivo
[2/500] Documento 2154801162... ✗ NO_RESUMEN_EJECUTIVO
[3/500] Documento 2155348321... ✗ NO_RESUMEN_EJECUTIVO
...

================================================================================
RESULTADOS ETAPA 3:
  Procesados: 500
  Exitosos:   147 (29.4%)
  Errores:    353 (70.6%)

  Tipos de error:
    • NO_RESUMEN_EJECUTIVO: 320 (90.6%)
    • HTTP_404: 25 (7.1%)
    • EXCEPTION: 8 (2.3%)
================================================================================
```

### 2. `error_report.py` - Análisis de Errores

Muestra estadísticas detalladas de qué está fallando.

**Uso**:
```bash
# Ver errores de Etapa 3
python error_report.py --stage 3

# Ver top 20 errores más comunes
python error_report.py --stage 3 --top 20
```

**Salida**:
```
================================================================================
REPORTE DE ERRORES - ETAPA 3: LINKS A PDF RESUMEN EJECUTIVO
================================================================================

📊 ESTADÍSTICAS GENERALES
--------------------------------------------------------------------------------
Total de documentos procesados:    500
  ✓ Exitosos:                      147 ( 29.4%)
  ✗ Con errores:                   353 ( 70.6%)
  ⏳ Pendientes:                      0 (  0.0%)

⚠️  TIPOS DE ERROR MÁS COMUNES
--------------------------------------------------------------------------------
  • NO_RESUMEN_EJECUTIVO                   |   320 ( 90.6%)
  • HTTP_404                               |    25 (  7.1%)
  • EXCEPTION                              |     8 (  2.3%)

🔬 EJEMPLOS DEL ERROR MÁS COMÚN: NO_RESUMEN_EJECUTIVO
--------------------------------------------------------------------------------
  Documento: 2154801162 (Expediente: 2154801158)
    Error: No se encontró link al resumen ejecutivo
  Documento: 2155348321 (Expediente: 2155348317)
    Error: No se encontró link al resumen ejecutivo
  ...
```

### 3. `reset_pipeline.py` - Limpieza y Reinicio

Limpia selectivamente etapas para volver a procesar con parsers mejorados.

**Uso**:
```bash
# Ver qué se va a borrar (dry-run)
python reset_pipeline.py --stage 3 --dry-run

# Limpiar solo Etapa 3 (mantener proyectos y documentos)
python reset_pipeline.py --stage 3

# Limpiar Etapas 2 y 3 (mantener solo proyectos)
python reset_pipeline.py --stage 2

# Limpiar TODO (usar con precaución)
python reset_pipeline.py --all
```

### 4. `stats.py` - Monitoreo Global

Ver estadísticas completas del pipeline en cualquier momento.

**Uso**:
```bash
python stats.py
```

## Ciclo Iterativo Completo

### Ejemplo Real: Mejorar Detección de Resumen Ejecutivo

#### Iteración 1: Baseline

```bash
# 1. Limpiar Etapa 3 para empezar de cero
python reset_pipeline.py --stage 3

# 2. Procesar batch de 1000 documentos
python batch_processor.py --batch-size 1000 --stage 3
# Resultado: 59 exitosos (5.9%), 941 errores (94.1%)

# 3. Ver qué falló
python error_report.py --stage 3
# Error más común: NO_RESUMEN_EJECUTIVO (880 casos, 93.5%)
```

**Análisis**: El parser solo busca heading `<h3>Resumen ejecutivo</h3>`, pero las DIAs no tienen heading separado.

#### Iteración 2: Arreglar Parser

```python
# Modificar src/parsers/resumen_ejecutivo.py
# Agregar búsqueda en TODOS los links (no solo después de heading)

# ANTES: Solo estrategia de heading
if not resumen_heading:
    return None  # ← Se rendía

# DESPUÉS: Dos estrategias (heading + búsqueda directa)
if resumen_heading:
    # Buscar en UL siguiente...

# Fallback: buscar en TODOS los links
all_links = soup.find_all('a', href=True)
for link in all_links:
    if 'resumen ejecutivo' in text.lower():
        return link
```

```bash
# 4. Limpiar y re-procesar
python reset_pipeline.py --stage 3
python batch_processor.py --batch-size 1000 --stage 3
# Resultado: 294 exitosos (29.4%), 706 errores (70.6%)

# 5. Medir mejora
python error_report.py --stage 3
# Error más común sigue siendo NO_RESUMEN_EJECUTIVO, pero ahora solo 640 casos

# Mejora: 5.9% → 29.4% = 5x más detección ✓
```

#### Iteración 3: Investigar Casos Restantes

```bash
# 6. Analizar los 706 errores restantes
python error_report.py --stage 3

# Ver ejemplos específicos del error más común
# Investigar manualmente 5-10 documentos para encontrar patrón
```

**Descubrimiento**: Muchos documentos usan "Fichas Resumen" en vez de "Resumen Ejecutivo".

#### Iteración 4: Expandir Patterns

```python
# Modificar parser para detectar más variaciones
if ('resumen ejecutivo' in text.lower() or
    'fichas resumen' in text.lower() or
    'síntesis ejecutiva' in text.lower()):
    return link
```

```bash
# 7. Re-procesar
python reset_pipeline.py --stage 3
python batch_processor.py --batch-size 1000 --stage 3
# Resultado: 350 exitosos (35.0%), 650 errores (65.0%)

# Mejora: 29.4% → 35.0% = +20% relativo ✓
```

### Cuándo Parar de Iterar

Continuar iterando hasta que:
1. ✅ **La conversión se estabilice** (< 5% de mejora entre iteraciones)
2. ✅ **Los errores restantes sean casos reales** (documentos que realmente no tienen resumen ejecutivo)
3. ✅ **El esfuerzo de arreglar no valga la pena** (diminishing returns)

## Esquema de Tracking en BD

### Tabla `expediente_documentos`

```sql
ALTER TABLE expediente_documentos ADD COLUMN (
    processing_status ENUM('pending', 'success', 'error') DEFAULT 'pending',
    error_type VARCHAR(100) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    attempts INT DEFAULT 0,
    last_attempt_at DATETIME DEFAULT NULL
);
```

### Tabla `resumen_ejecutivo_links`

```sql
ALTER TABLE resumen_ejecutivo_links ADD COLUMN (
    processing_status ENUM('pending', 'success', 'error') DEFAULT 'pending',
    error_type VARCHAR(100) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    attempts INT DEFAULT 0,
    last_attempt_at DATETIME DEFAULT NULL
);
```

**Tipos de error comunes**:
- `NO_RESUMEN_EJECUTIVO`: No se encontró link al resumen ejecutivo
- `HTTP_404`: Documento no encontrado
- `HTTP_500`: Error del servidor SEA
- `PARSE_ERROR`: Error parseando HTML
- `EXCEPTION`: Error inesperado en el código

## Queries Útiles

### Ver documentos con un error específico

```sql
SELECT rel.id_documento, rel.error_message, ed.expediente_id
FROM resumen_ejecutivo_links rel
LEFT JOIN expediente_documentos ed ON rel.id_documento = ed.id_documento
WHERE rel.error_type = 'NO_RESUMEN_EJECUTIVO'
LIMIT 10;
```

### Comparar tasas de éxito por tipo de proyecto

```sql
SELECT
    p.workflow_descripcion,
    COUNT(rel.id) as total_links,
    SUM(CASE WHEN rel.processing_status = 'success' THEN 1 ELSE 0 END) as exitosos,
    ROUND(SUM(CASE WHEN rel.processing_status = 'success' THEN 1 ELSE 0 END) / COUNT(rel.id) * 100, 1) as tasa_exito
FROM resumen_ejecutivo_links rel
JOIN expediente_documentos ed ON rel.id_documento = ed.id_documento
JOIN proyectos p ON ed.expediente_id = p.expediente_id
WHERE rel.processing_status != 'pending'
GROUP BY p.workflow_descripcion;
```

### Ver progreso por estado de proyecto

```sql
SELECT
    p.estado_proyecto,
    COUNT(rel.id) as total_procesados,
    SUM(CASE WHEN rel.processing_status = 'success' THEN 1 ELSE 0 END) as exitosos
FROM proyectos p
JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
WHERE rel.id IS NOT NULL
GROUP BY p.estado_proyecto
ORDER BY total_procesados DESC;
```

## Mejores Prácticas

### 1. Siempre Empezar con Batches Pequeños

❌ **Malo**: Procesar todo el dataset de una vez (29,887 proyectos)
- Si falla, pierdes tiempo
- No tienes feedback hasta el final
- Difícil de debuggear

✅ **Bueno**: Empezar con 1,000 proyectos
- Falla rápido, falla barato
- Feedback inmediato
- Puedes iterar rápidamente

### 2. Usar `--dry-run` Antes de Reset

❌ **Malo**: `python reset_pipeline.py --all` directamente

✅ **Bueno**:
```bash
python reset_pipeline.py --all --dry-run  # Ver qué se va a borrar
python reset_pipeline.py --all            # Confirmar y borrar
```

### 3. Documentar Cada Iteración

Crear un log de iteraciones en `observaciones.md`:

```markdown
## Iteraciones de Mejora

### Iteración 1 (2025-10-27)
- Baseline: 5.9% de conversión
- Error principal: Parser solo buscaba heading H3

### Iteración 2 (2025-10-27)
- Fix: Agregar búsqueda en todos los links
- Resultado: 29.4% de conversión (5x mejora)
- Error principal restante: Documentos sin resumen ejecutivo real
```

### 4. Guardar Scripts de Investigación

Cuando investigues un error específico, guarda el script:

```python
# investigate_error_NO_RESUMEN_EJECUTIVO.py
# Investigar por qué documentos fallan con NO_RESUMEN_EJECUTIVO

# Tomar 10 documentos con este error
# Extraer su HTML
# Buscar patterns comunes
# Proponer fix
```

### 5. Comparar Antes/Después

```bash
# Antes del fix
python batch_processor.py --batch-size 1000 --stage 3 > before.log
python error_report.py --stage 3 > before_errors.txt

# Aplicar fix
# ...

# Después del fix
python reset_pipeline.py --stage 3
python batch_processor.py --batch-size 1000 --stage 3 > after.log
python error_report.py --stage 3 > after_errors.txt

# Comparar
diff before_errors.txt after_errors.txt
```

## Troubleshooting

### "No hay proyectos/documentos pendientes"

Todos ya fueron procesados. Opciones:
1. Limpiar con `reset_pipeline.py` y re-procesar
2. Aumentar batch size para procesar más
3. Ya terminaste - pasar a siguiente etapa

### "Migración 002 ya aplicada"

Normal. La migración solo se aplica una vez.

### "Lost connection to MySQL server"

Hay un lock en la tabla. Solución:
```bash
mysql -h HOST -u USER -pPASS -e "SHOW PROCESSLIST;"
# Identificar proceso bloqueado
mysql -h HOST -u USER -pPASS -e "KILL [ID];"
```

## Roadmap

- [x] Framework de batch processing
- [x] Tracking de errores en BD
- [x] Scripts de reporte y análisis
- [x] Scripts de reset selectivo
- [ ] Dashboard web para ver progreso en tiempo real
- [ ] Alertas automáticas cuando un tipo de error supera threshold
- [ ] A/B testing de diferentes estrategias de parsing
- [ ] Machine learning para clasificar errores automáticamente

---

**Última actualización**: 2025-10-27
**Autor**: Claude + Chris
**Versión**: 1.0
