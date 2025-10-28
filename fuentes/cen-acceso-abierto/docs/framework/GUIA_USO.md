# Guía de Uso: Framework Iterativo de Parsing

Este framework permite mejorar el parser sistemáticamente hasta alcanzar 85-95% de tasa de éxito.

---

## 📋 Quick Start

### 1. Primera Iteración - Parsear 1000 Documentos

```bash
python -m src.iterative_parse \
    --tipo SUCTD \
    --batch 1000 \
    --iteracion 1 \
    --parser-version "2.0.0" \
    --notas "Primera ejecución"
```

### 2. Ver Feedback

```bash
python -m src.iterative_parse --feedback --iteracion 1 --tipo SUCTD
```

### 3. Implementar Fix en el Parser

```python
# Editar src/parsers/pdf_suctd.py según el error más común
```

### 4. Re-Parse con Parser Mejorado

```bash
python -m src.iterative_parse \
    --tipo SUCTD \
    --batch 1000 \
    --iteracion 2 \
    --parser-version "2.1.0" \
    --reparse \
    --notas "Fix: búsqueda flexible"
```

### 5. Comparar Iteraciones

```bash
python -m src.iterative_parse --compare --tipo SUCTD
```

### 6. Repetir Hasta Objetivo

Continuar iterando hasta alcanzar 90%+ de tasa de éxito.

---

## 📊 Ciclo Completo

```bash
# ITERACIÓN 1 - Baseline
python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 1
# Resultado: 650/1000 (65%)

# Análisis + Fix
python -m src.iterative_parse --feedback --iteracion 1 --tipo SUCTD

# ITERACIÓN 2 - Re-parse
python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 2 --reparse
# Resultado: 850/1000 (85%)

# ITERACIÓN 3 - Re-parse
python -m src.iterative_parse --tipo SUCTD --batch 1000 --iteracion 3 --reparse
# Resultado: 920/1000 (92%)
# ✅ OBJETIVO ALCANZADO
```

---

## 🎯 Comandos Útiles

### Ver Historial Completo
```bash
python -m src.iterative_parse --compare --tipo SUCTD
```

### Ver Feedback Específico
```bash
python -m src.iterative_parse --feedback --iteracion 3 --tipo SUCTD
```

### Procesar Batch Pequeño (Testing)
```bash
python -m src.iterative_parse --tipo SUCTD --batch 100 --iteracion 0
```

### Re-Parse Todos los Documentos
```bash
python -m src.iterative_parse --tipo SUCTD --batch 10000 --iteracion 5 --reparse
```

---

## 📈 Queries SQL Útiles

### Ver Progreso
```sql
SELECT iteracion, fecha_iteracion, tasa_exito, error_pattern
FROM parsing_feedback
WHERE tipo_formulario = 'SUCTD'
ORDER BY iteracion DESC;
```

### Documentos que Siempre Fallan
```sql
SELECT fp.documento_id, d.local_path, s.proyecto, fp.parsing_error
FROM formularios_parseados fp
INNER JOIN documentos d ON fp.documento_id = d.id
INNER JOIN solicitudes s ON d.solicitud_id = s.id
WHERE fp.tipo_formulario = 'SUCTD' AND fp.parsing_exitoso = 0
LIMIT 20;
```

### Tasa de Éxito Actual
```sql
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) AS exitosos,
    ROUND(100.0 * SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tasa_exito
FROM formularios_parseados
WHERE tipo_formulario = 'SUCTD';
```

---

## 🎓 Tips

1. **Empezar con batch pequeño** (100 docs) para testing
2. **Documentar cada fix** con `--notas`
3. **Usar `--reparse`** después de cada fix
4. **Comparar iteraciones** frecuentemente

---

## 🚨 Troubleshooting

### "No hay documentos para procesar"
→ Usar `--reparse` para re-procesar documentos ya parseados

### "Tabla parsing_feedback no existe"
→ El script la crea automáticamente en la primera ejecución

---

Ver también: [Documentación Técnica](FRAMEWORK_ITERATIVO.md)
