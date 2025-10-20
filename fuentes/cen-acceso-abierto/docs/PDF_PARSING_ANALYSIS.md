# Análisis de Herramientas para Parsing de PDFs del CEN

## Contexto

Los formularios del CEN (SAC, SUCTD, Fehaciente) se suben en formatos PDF y XLSX. Este documento analiza las diferentes opciones de parsing para los PDFs y determina la mejor herramienta para nuestro caso de uso específico.

---

## 🔍 Análisis del Tipo de PDF

### Metadata del PDF Analizado

**Archivo de muestra**: `Formulario_SAC_-_La_Aguada.pdf`

```
Metadata:
  Author: CL24694492K
  CreationDate: D:20211118161022-03'00'
  Producer: Microsoft: Print To PDF
  Title: Formulario-de-solicitud-y-antecedentes-SAC-La Aguada.xlsx

Características:
  - Tamaño: 427 KB
  - Páginas: 1
  - Encriptado: No
  - Texto extraíble: ✅ 2,402 caracteres
  - Campos AcroForm: ❌ No
  - Fonts detectados: ✅ 2 fonts (/F1, /F2)
  - Imágenes: ❌ No contiene
```

### 🎯 Hallazgo Clave #1: Origen del PDF

**El PDF fue generado desde Excel usando "Microsoft: Print To PDF"**

Esto significa:
- ✅ **NO es imagen escaneada** (no necesita OCR)
- ✅ **Texto vectorial real** (extraíble con cualquier librería)
- ✅ **Estructura tabular preservada** (viene de Excel)
- ❌ **NO es PDF interactivo** (no tiene campos de formulario)

**Implicaciones**:
- ❌ No necesitamos OCR (Tesseract)
- ✅ Podemos usar librerías de extracción de texto
- ✅ Debemos buscar herramientas que entiendan tablas

---

## 📊 Comparación de Herramientas

### 1. **pypdf** (librería inicial)

**Características**:
- ✅ Librería Python pura (sin dependencias externas)
- ✅ Rápida y ligera
- ⚠️ Extracción de texto básica

**Resultado con formulario SAC**:
```
Caracteres extraídos: 2,402
Texto: Desordenado, sin estructura tabular
```

**Ejemplo de salida**:
```
Versión 25-05-21
Gen 400 + 100
0,3 0,95
Huso 19 H Este Norte 6188194.00 m S
Región
Huso 19 H Este Norte 6196194.39 m S
...
```

**Veredicto**: ⚠️ **Funciona pero requiere mucho regex** para parsear campos.

---

### 2. **pdfplumber** ⭐ RECOMENDADA

**Características**:
- ✅ Especializada en **extracción de tablas**
- ✅ Detecta estructura tabular automáticamente
- ✅ API rica para análisis de layout
- ✅ Built on top of pdfminer.six

**Resultado con formulario SAC**:
```
Caracteres extraídos: 2,392
Tablas detectadas: 1 tabla con 32 filas x 10 columnas
```

**🎯 Hallazgo Clave #2: Detección Automática de Tablas**

pdfplumber detectó automáticamente que el formulario SAC es una tabla estructurada:

```python
tables = page.extract_tables()
# Retorna: 1 tabla con 32 filas

Ejemplo de estructura:
Fila 2: ['', 'Razón Social (1)', 'Enel Green Power Chile S.A.', '', ...]
Fila 3: ['', 'RUT', '76.412.562-2', '', ...]
Fila 4: ['', 'Giro', 'Generación eléctrica', '', ...]
```

**Ventajas para nuestro caso**:
- ✅ **Estructura preservada**: Label → Valor ya está separado
- ✅ **Menos regex**: No necesitamos parsear texto desordenado
- ✅ **Más robusto**: Funciona aunque el layout cambie ligeramente
- ✅ **Mapeo directo**: Fila de tabla → Campo de BD

**Veredicto**: ✅ **IDEAL para formularios Excel → PDF**

---

### 3. **PyMuPDF (fitz)**

**Características**:
- ✅ Muy rápida (escrita en C)
- ✅ Extracción completa de contenido
- ✅ Manejo de imágenes, anotaciones, etc.

**Resultado con formulario SAC**:
```
Caracteres extraídos: 2,406
Texto: Similar a pypdf, desordenado
```

**Veredicto**: ⚠️ **Overkill para nuestro caso** - Más adecuada para PDFs complejos con imágenes.

---

### 4. **OCR (Tesseract)**

**¿Cuándo usar OCR?**
- ✅ PDFs escaneados (imágenes de documentos)
- ✅ PDFs sin texto vectorial
- ✅ Formularios escritos a mano digitalizados

**¿Necesitamos OCR para CEN?**
- ❌ **NO** - Los PDFs tienen texto vectorial extraíble
- ❌ **NO** - Los PDFs tienen fonts detectados
- ❌ **NO** - Los PDFs vienen de Excel (Microsoft Print to PDF)

**Cómo verificar si un PDF necesita OCR**:
```python
reader = pypdf.PdfReader(pdf_path)
text = reader.pages[0].extract_text()

if len(text) < 100:
    # Probablemente es imagen escaneada
    print("⚠️ Podría necesitar OCR")
else:
    # Tiene texto extraíble
    print("✅ No necesita OCR")
```

**Veredicto**: ❌ **No necesario para formularios CEN**

---

## 🎯 Decisión Final: Usar `pdfplumber`

### Razones:

1. **Detección automática de tablas** (32 filas extraídas del formulario SAC)
2. **Preserva estructura label → valor** (no necesitamos regex complejos)
3. **Ideal para PDFs generados desde Excel** (nuestro caso)
4. **API simple y clara** para extracción estructurada
5. **Mantenida activamente** (última actualización: 2024)

### Instalación:

```bash
uv add pdfplumber
```

### Uso básico:

```python
import pdfplumber

with pdfplumber.open('formulario.pdf') as pdf:
    page = pdf.pages[0]

    # Extraer tabla
    tables = page.extract_tables()

    for row in tables[0]:
        label = row[1]  # Columna de labels
        value = row[2]  # Columna de valores
        print(f"{label}: {value}")
```

---

## 📋 Estructura de Tabla Detectada (Formulario SAC)

**Dimensiones**: 32 filas x 10 columnas

### Campos principales extraídos:

| Fila | Label | Valor Ejemplo |
|------|-------|---------------|
| 2 | Razón Social | Enel Green Power Chile S.A. |
| 3 | RUT | 76.412.562-2 |
| 4 | Giro | Generación eléctrica |
| 5 | Domicilio Legal | Santa Rosa 76, piso 17, Santiago |
| 7 | Nombre del Representante Legal | Ali Shakhtur Said |
| 8 | e-mail | Ali.Shakhtur@enel.com |
| 15 | Nombre del Proyecto | La Aguada |
| 16 | Tipo Proyecto | Gen |
| 17 | Tecnología | Híbrido (Solar Fotovoltaica + BESS) |
| 18 | Potencia Nominal [MW] | 400 + 100 |
| 26 | Nombre de la S/E | S/E Portezuelo |
| 27 | Nivel de Tensión [kV] | 220 kV |
| 30 | Coordenadas U.T.M. WGS84 | Huso 19 H, Este 259639.49 m E |

**Total campos identificados**: ~25-30 campos por formulario

---

## 🔄 Comparación con Formularios XLSX

**Ventaja adicional de pdfplumber**:

Como los PDFs vienen de Excel, la estructura tabular es **idéntica** entre:
- ✅ Formularios XLSX originales
- ✅ Formularios PDF generados desde XLSX

Esto significa que podemos:
1. Usar `openpyxl` para XLSX
2. Usar `pdfplumber` para PDF
3. **Aplicar la misma lógica de parsing** a ambos formatos

---

## 🚀 Próximos Pasos

1. ✅ **Diseñar schema de BD** para campos parseados
2. ✅ **Implementar parser con pdfplumber** para SAC
3. ✅ Extender a SUCTD y Fehaciente
4. ✅ Manejar variaciones en estructura entre versiones

---

## 📚 Referencias

- **pdfplumber**: https://github.com/jsvine/pdfplumber
- **pypdf**: https://pypdf.readthedocs.io/
- **PyMuPDF**: https://pymupdf.readthedocs.io/
- **Tesseract OCR**: https://github.com/tesseract-ocr/tesseract

---

## 🧪 Comandos de Prueba

```bash
# Analizar estructura de un PDF
uv run python -c "
import pdfplumber
pdf = pdfplumber.open('formulario.pdf')
tables = pdf.pages[0].extract_tables()
print(f'Tablas: {len(tables)}')
print(f'Filas: {len(tables[0])}')
"

# Verificar si un PDF necesita OCR
uv run python -c "
import pypdf
reader = pypdf.PdfReader('formulario.pdf')
text = reader.pages[0].extract_text()
print(f'Texto extraíble: {len(text)} caracteres')
print('Necesita OCR: ', 'Sí' if len(text) < 100 else 'No')
"
```

---

**Fecha de análisis**: 2025-10-20
**PDFs analizados**: Formulario SAC (La Aguada)
**Decisión**: ✅ pdfplumber para parsing de PDFs del CEN
