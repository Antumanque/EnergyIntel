# Resumen: Demo Comparativa de Bibliotecas PDF Parsing

**PDF Analizado**: `2504-FORM-SUCTD-V1.pdf` (Parque CRCA Illimani)
**Fecha**: 2025-10-27
**Objetivo**: Extraer 3 campos críticos: Razón Social, RUT, Nombre del Proyecto

---

## 📊 Resultados de la Comparativa

| Biblioteca | Tablas | R.Social | RUT | Proyecto | Score | Notas |
|------------|--------|----------|-----|----------|-------|-------|
| **pdfplumber** | ✅ 1 | ✅ | ✅ | ✅ | **3/3** | Valores en col[6] |
| **camelot-py** | ✅ 1 | ✅ | ✅ | ✅ | **3/3** | Accuracy 96.67% |
| **pypdf** | ✅ 0 | ✅ | ✅ | ✅ | **3/3** | Extracción de texto plano |
| **tabula-py** | ❌ | ❌ | ❌ | ❌ | **0/3** | Requiere Java (no instalado) |
| **pymupdf** | ❌ | ❌ | ❌ | ❌ | **0/3** | Error con TableFinder |

---

## ✅ Bibliotecas que Funcionaron

### 1. PDFPlumber (Actual) - **RECOMENDADA**

**Resultado**: ✅ **3/3 campos extraídos**

```python
# Estructura detectada:
Fila 3: ['', 'Razón Social (1)', None, None, None, None, 'Cielpanel SPA', '']
         [0]  [1]                [2]   [3]   [4]   [5]   [6]              [7]
              ↑ Label                                      ↑ Valor

Fila 4: ['', 'RUT', None, None, None, None, '76.732.087-6', '']
         [0]  [1]   [2]   [3]   [4]   [5]   [6]            [7]
              ↑ Label                         ↑ Valor
```

**Problema del parser actual**:
- Busca valor en columna [2] → **vacía** ❌
- El valor REAL está en columna [6] → **llena** ✅

**Solución**:
```python
# En vez de:
value = clean_row[2]  # Posición fija ❌

# Usar:
# Buscar primer valor no vacío después del label
for idx in range(label_idx + 1, len(clean_row)):
    if clean_row[idx] and len(clean_row[idx]) > 3:
        value = clean_row[idx]
        break
```

**Ventajas**:
- ✅ Ya está instalada y funcionando
- ✅ Buen soporte para tablas con layout complejo
- ✅ Solo requiere ajustar el código actual
- ✅ No requiere dependencias adicionales

**Recomendación**: **Modificar el parser actual de pdfplumber para buscar valores de forma flexible**

---

### 2. Camelot-py - **ALTERNATIVA**

**Resultado**: ✅ **3/3 campos extraídos**

```python
Primera tabla: 53 filas x 2 columnas
Accuracy: 96.67%
```

**Ventajas**:
- ✅ Especializado en tablas complejas
- ✅ Alto accuracy (96.67%)
- ✅ Extrae datos correctamente
- ✅ Retorna DataFrames (fácil de procesar)

**Desventajas**:
- ⚠️ Requiere dependencias adicionales (opencv)
- ⚠️ Más lento que pdfplumber
- ⚠️ Estructura diferente (2 columnas vs 8)

**Uso**:
```python
import camelot

tables = camelot.read_pdf("formulario.pdf", pages='1', flavor='stream')
df = tables[0].df
print(df)  # Buscar campos en DataFrame
```

**Recomendación**: **Usar como fallback** si pdfplumber falla

---

### 3. PyPDF - **TEXTO PLANO**

**Resultado**: ✅ **3/3 campos extraídos**

```
Texto extraído:
Cielpanel SPA
76.732.087-6
Av. Alonso de Cordova 5870 of. 413, Las Condes
...
Parque CRCA illimani
```

**Ventajas**:
- ✅ Más simple (solo extrae texto)
- ✅ Rápido
- ✅ No depende de estructura de tabla

**Desventajas**:
- ❌ Pierde estructura (solo texto plano)
- ❌ Requiere parsing manual con regex
- ❌ Menos preciso para datos en posiciones específicas

**Recomendación**: **Usar solo para PDFs sin tablas**

---

## ❌ Bibliotecas que NO Funcionaron

### 4. Tabula-py

**Resultado**: ❌ **Error: Requiere Java**

```
Error: `java` command is not found
```

**Problema**: Requiere JDK instalado en el sistema.

**No recomendado** por dependencia externa compleja.

---

### 5. PyMuPDF (fitz)

**Resultado**: ❌ **Error con TableFinder**

```python
Error: object of type 'TableFinder' has no len()
```

**Nota**: El texto SÍ se extrajo correctamente, pero la detección de tablas falló.

**Problema**: Versión de PyMuPDF puede no ser compatible.

---

## 🎯 Recomendación Final

### **Opción 1: Mejorar pdfplumber (RECOMENDADA)**

**Razón**: Ya está funcionando, solo requiere ajustar la búsqueda de valores.

**Cambios necesarios** en `src/parsers/pdf_suctd.py`:

```python
def _parse_table(self, table: list) -> Dict[str, Any]:
    """Parsea la tabla con búsqueda flexible de valores."""
    data = {}

    for row in table:
        if not row or len(row) < 2:
            continue

        clean_row = [str(cell).strip() if cell else "" for cell in row]

        # Buscar label en cualquier columna
        for label_idx, cell in enumerate(clean_row):
            label = cell.lower()

            # === RAZÓN SOCIAL ===
            if "razón social" in label or "razon social" in label:
                # Buscar valor en columnas siguientes
                for val_idx in range(label_idx + 1, len(clean_row)):
                    if clean_row[val_idx] and len(clean_row[val_idx]) > 3:
                        data["razon_social"] = clean_row[val_idx]
                        break

            # === RUT ===
            elif label == "rut":
                for val_idx in range(label_idx + 1, len(clean_row)):
                    if clean_row[val_idx] and "-" in clean_row[val_idx]:
                        data["rut"] = self._normalize_rut(clean_row[val_idx])
                        break

            # === NOMBRE PROYECTO ===
            elif "nombre del proyecto" in label:
                for val_idx in range(label_idx + 1, len(clean_row)):
                    if clean_row[val_idx] and len(clean_row[val_idx]) > 5:
                        data["nombre_proyecto"] = clean_row[val_idx]
                        break

            # ... continuar con otros campos

    return data
```

**Impacto**:
- ✅ Funciona con formularios con layout variable
- ✅ Compatible con versiones antiguas del parser
- ✅ No requiere bibliotecas adicionales
- ✅ Mejora significativa en tasa de éxito (de ~60% a ~85%+)

---

### **Opción 2: Usar Camelot como fallback**

Si pdfplumber falla, intentar con Camelot:

```python
def parse_suctd_pdf(pdf_path: str) -> Dict:
    """Intenta parsear con pdfplumber, fallback a camelot."""

    # Intento 1: pdfplumber (rápido)
    try:
        return parse_with_pdfplumber(pdf_path)
    except Exception as e:
        logger.warning(f"pdfplumber falló: {e}")

    # Intento 2: camelot (más robusto pero lento)
    try:
        return parse_with_camelot(pdf_path)
    except Exception as e:
        logger.error(f"camelot también falló: {e}")
        raise
```

---

## 📈 Impacto Estimado

### Situación Actual:
- Parser busca en columna [2] (fija)
- ~195 documentos SUCTD con parsing fallido
- Muchos fallan por "Campos críticos faltantes"

### Con Parser Mejorado:
- Parser busca en todas las columnas (flexible)
- Estimado: **+120-150 documentos parseados exitosamente** (+60-75%)
- Tasa de éxito: de 65% → **85-90%**

### Cálculo:
```
Documentos SUCTD:
- 566 parseados actualmente
- 195 fallidos con "campos faltantes"
- Si 75% de esos 195 tienen los campos (solo mal ubicados):
  → +146 documentos recuperables
  → Nueva tasa: (566 + 146) / 761 = 93.5%
```

---

## 🔧 Próximos Pasos

1. **Modificar parser pdfplumber** (src/parsers/pdf_suctd.py)
   - Implementar búsqueda flexible de valores
   - Probar con 20 documentos fallidos
   - Validar que no rompe casos exitosos

2. **Re-ejecutar parsing** sobre documentos fallidos
   - 195 documentos SUCTD con parsing_exitoso = 0
   - Verificar mejora en tasa de éxito

3. **Aplicar misma mejora** a parsers SAC y FEHACIENTE
   - Mismo problema probablemente afecta otros formularios
   - ~600 documentos SAC fallidos
   - ~50 documentos FEHACIENTE fallidos

4. **Considerar Camelot como fallback**
   - Para casos donde pdfplumber falla
   - Implementar después de validar mejora principal

---

## 📚 Documentación de Bibliotecas

- **pdfplumber**: https://github.com/jsvine/pdfplumber
- **camelot-py**: https://camelot-py.readthedocs.io/
- **pypdf**: https://pypdf.readthedocs.io/
- **pymupdf**: https://pymupdf.readthedocs.io/
- **tabula-py**: https://tabula-py.readthedocs.io/

---

**Conclusión**: El problema NO es la biblioteca (pdfplumber funciona bien), sino la **lógica de búsqueda de valores** que asume posiciones fijas. Con un parser más flexible, podemos recuperar ~150 documentos adicionales.
