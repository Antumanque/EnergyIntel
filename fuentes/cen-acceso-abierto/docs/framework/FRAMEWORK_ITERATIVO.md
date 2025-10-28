# Framework Iterativo de Parsing con Feedback

**🎯 LO MÁS IMPORTANTE DEL PROYECTO**

Este framework permite mejorar el parser de forma sistemática e iterativa, identificando patrones de error y corrigiéndolos progresivamente.

---

## 📋 Concepto

### Ciclo Iterativo

```
1. PARSE Batch (ej: 1000 docs)
      ↓
2. FEEDBACK: Ver fallos
      ↓
3. ANÁLISIS: Identificar patrón más común
      ↓
4. FIX: Arreglar parser
      ↓
5. RE-PARSE: Volver a cargar TODO
      ↓
   (repetir hasta que tasa de éxito sea aceptable)
```

### Ejemplo Concreto

```
ITERACIÓN 1:
- Cargar 1000 docs → 350 exitosos (35%)
- Error más común: "Campos críticos faltantes: nombre_proyecto" (250 casos)
- Fix: Implementar búsqueda flexible de valores
- Re-parse → 650 exitosos (65%)

ITERACIÓN 2:
- Error más común: "Fecha inválida" (150 casos)
- Fix: Mejorar parser de fechas
- Re-parse → 800 exitosos (80%)

ITERACIÓN 3:
- Error más común: "RUT formato inválido" (50 casos)
- Fix: Normalizar RUTs con formatos variados
- Re-parse → 950 exitosos (95%)

OBJETIVO: 95%+ de tasa de éxito
```

---

## 🗄️ Tabla de Feedback

### Estructura: `parsing_feedback`

```sql
CREATE TABLE IF NOT EXISTS parsing_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Iteración
    iteracion INT NOT NULL,
    fecha_iteracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parser_version VARCHAR(50),

    -- Estadísticas Generales
    tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE') NOT NULL,
    total_documentos INT NOT NULL,
    documentos_exitosos INT NOT NULL,
    documentos_fallidos INT NOT NULL,
    tasa_exito DECIMAL(5,2),

    -- Errores Agrupados
    error_pattern VARCHAR(500),
    error_count INT,
    error_sample_ids TEXT, -- JSON array de documento_ids de ejemplo

    -- Campos Faltantes Más Comunes
    campos_faltantes_top JSON, -- {"razon_social": 120, "rut": 80, ...}

    -- Metadata
    notas TEXT,
    duracion_segundos INT,

    INDEX idx_iteracion (iteracion),
    INDEX idx_tipo (tipo_formulario),
    INDEX idx_fecha (fecha_iteracion)
);
```

### Vista de Resumen

```sql
CREATE VIEW parsing_progress AS
SELECT
    iteracion,
    fecha_iteracion,
    parser_version,
    tipo_formulario,
    total_documentos,
    documentos_exitosos,
    tasa_exito,
    LAG(tasa_exito) OVER (
        PARTITION BY tipo_formulario
        ORDER BY iteracion
    ) AS tasa_anterior,
    tasa_exito - LAG(tasa_exito) OVER (
        PARTITION BY tipo_formulario
        ORDER BY iteracion
    ) AS mejora
FROM parsing_feedback
ORDER BY tipo_formulario, iteracion DESC;
```

---

## 🔧 Scripts del Framework

### 1. `src/iterative_parse.py` - Script Principal

```bash
# Primera iteración
python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 1

# Ver feedback
python -m src.iterative_parse --feedback --iteracion 1 --tipo SUCTD

# Re-parse después de fix
python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 2 --reparse

# Comparar iteraciones
python -m src.iterative_parse --compare --tipo SUCTD
```

---

## 🎯 Objetivos por Tipo de Formulario

| Tipo | Objetivo Tasa Éxito | Iteraciones Estimadas |
|------|---------------------|----------------------|
| SUCTD | 90%+ | 3-4 iteraciones |
| SAC | 85%+ | 4-5 iteraciones |
| FEHACIENTE | 95%+ | 2-3 iteraciones |

---

## 📈 Métricas de Éxito

### Por Iteración
- Tasa de éxito aumenta en cada iteración
- Errores más comunes disminuyen significativamente
- Nuevos errores descubiertos = señal de progreso (llegamos a casos más complejos)

### Global
- Al menos 85% de documentos parseados exitosamente
- Todos los campos críticos presentes en >90% de casos
- Tiempo de procesamiento aceptable (<5 min por 1000 docs)

---

## 🛠️ Herramientas del Framework

### 1. Dashboard de Iteraciones (SQL)

```sql
-- Ver progreso histórico
SELECT
    i.iteracion,
    i.fecha_iteracion,
    i.parser_version,
    i.total_documentos,
    i.documentos_exitosos,
    i.tasa_exito,
    i.tasa_exito - LAG(i.tasa_exito) OVER (ORDER BY i.iteracion) AS mejora
FROM parsing_feedback i
WHERE tipo_formulario = 'SUCTD'
ORDER BY iteracion DESC;
```

### 2. Query de Documentos Problemáticos

```sql
-- Documentos que SIEMPRE fallan (en todas las iteraciones)
SELECT
    fp.documento_id,
    d.local_path,
    s.proyecto,
    COUNT(DISTINCT pf.iteracion) AS intentos_fallidos,
    GROUP_CONCAT(DISTINCT fp.parsing_error SEPARATOR ' | ') AS errores
FROM formularios_parseados fp
INNER JOIN documentos d ON fp.documento_id = d.id
INNER JOIN solicitudes s ON d.solicitud_id = s.id
LEFT JOIN parsing_feedback pf ON pf.error_sample_ids LIKE CONCAT('%', fp.documento_id, '%')
WHERE fp.tipo_formulario = 'SUCTD'
  AND fp.parsing_exitoso = 0
GROUP BY fp.documento_id, d.local_path, s.proyecto
HAVING intentos_fallidos >= 3
ORDER BY intentos_fallidos DESC;
```

---

**Este framework es LA PIEZA CLAVE para mejorar sistemáticamente el parser y alcanzar tasas de éxito del 85-90%+**

Ver también: [Guía de Uso](GUIA_USO.md)
