# Sistema de Error Handling para Parsing de Formularios

## 📋 Overview

El sistema de parsing implementa estrategias **robustas y defensivas** para manejar datos del mundo real que pueden tener errores, inconsistencias, o formatos inesperados.

**Filosofía**: **Nunca perder datos, siempre registrar errores**.

---

## 🎯 Estrategias Implementadas

### 1. **Tracking Granular** (`formularios_parseados`)

Cada intento de parsing se registra en la tabla `formularios_parseados`:

```sql
CREATE TABLE formularios_parseados (
    id BIGINT PRIMARY KEY,
    documento_id BIGINT UNIQUE,
    tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE'),
    formato_archivo ENUM('PDF', 'XLSX', 'XLS'),

    -- Estado del parsing
    parsing_exitoso BOOLEAN DEFAULT FALSE,
    parsing_error TEXT,           -- ⭐ Error detallado si falla
    parsed_at TIMESTAMP,
    parser_version VARCHAR(50),    -- ⭐ Permite re-parsear con versiones nuevas

    -- Metadata del PDF (para análisis de origen)
    pdf_producer VARCHAR(255),     -- ⭐ Ej: "Microsoft: Print To PDF"
    pdf_author VARCHAR(255),       -- ⭐ Quién creó el PDF
    pdf_title VARCHAR(500),        -- ⭐ Título original
    pdf_creation_date DATETIME     -- ⭐ Fecha de creación del PDF
);
```

**Beneficios**:
- ✅ Saber qué documentos fueron parseados exitosamente
- ✅ Saber qué documentos fallaron (y por qué)
- ✅ Poder re-parsear con versiones mejoradas del parser
- ✅ Audit trail completo
- ✅ **Detectar qué herramientas generan los PDFs** (Microsoft, LibreOffice, etc.)
- ✅ **Identificar problemas por herramienta** (ej: LibreOffice genera PDFs con layout diferente)

---

### 2. **Validación de Campos Críticos**

Antes de marcar parsing como exitoso, se validan campos MÍNIMOS requeridos:

```python
# src/repositories/cen.py:798-803
required_fields = ["razon_social", "rut", "nombre_proyecto"]
missing_fields = [f for f in required_fields if not parsed_data.get(f)]

if missing_fields:
    # Registrar como FALLIDO
    error_msg = f"Campos críticos faltantes: {', '.join(missing_fields)}"
    insert_formulario_parseado(parsing_exitoso=False, parsing_error=error_msg)
```

**Caso real capturado**:
```
Documento: Formulario_Verificación_Antecedentes_-_La_Aguada.pdf
Error: Campos críticos faltantes: razon_social, rut, nombre_proyecto
Acción: Parsing marcado como FALLIDO en BD (no se perdieron datos)
```

---

### 3. **Validación de Fechas Inválidas**

PDFs pueden contener fechas imposibles (ej: "31-02-2024"). El parser las detecta y convierte a `NULL`:

```python
# src/parsers/pdf_sac.py:319
datetime(year_int, month_int, day_int)  # Valida fecha real
return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
```

**Caso real capturado**:
```
Documento: Formulario_SAC_-_La_Aguada.pdf
Entrada: "31-02-2024" (febrero no tiene 31 días)
Salida: NULL (guardado como NULL en BD, no falla el parsing)
Log: ⚠️  Fecha inválida detectada: 31-02-2024
```

---

### 4. **Transacciones Atómicas**

Inserción en BD usa transacciones para garantizar consistencia:

```python
# src/repositories/cen.py:817-831
with self.connection() as conn:
    try:
        # 1. INSERT en formularios_parseados
        cursor.execute("INSERT INTO formularios_parseados ...")

        # 2. INSERT en formularios_sac_parsed
        cursor.execute("INSERT INTO formularios_sac_parsed ...")

        conn.commit()  # ✅ Ambos inserts exitosos

    except Error as e:
        conn.rollback()  # ❌ Rollback automático si algo falla
        # Registrar error en formularios_parseados
```

**Garantía**: O se guardan TODOS los datos, o NO se guarda nada (no datos parciales).

---

### 5. **Manejo de Formatos Inesperados**

El parser está preparado para variaciones en formatos de documentos:

#### **a) Diferentes Herramientas de Generación**

| Herramienta | Características | Manejo |
|-------------|----------------|---------|
| Microsoft Print to PDF | Texto vectorial, tablas estructuradas | ✅ pdfplumber detecta tablas |
| LibreOffice/OpenOffice | Puede tener layout diferente | ✅ Parser busca por labels, no posiciones fijas |
| Excel directo (XLSX) | Estructura de celdas | 🔜 Parser XLSX independiente |

#### **b) Campos Opcionales vs Obligatorios**

**Campos OBLIGATORIOS** (validados):
- `razon_social`
- `rut`
- `nombre_proyecto`

**Campos OPCIONALES** (NULL si faltan):
- `tecnologia`
- `potencia_nominal_mw`
- `coordinador_proyecto_2_*` (no todos los proyectos tienen 2+ coordinadores)

#### **c) Valores con Formato Flexible**

**Ejemplo**: `potencia_nominal_mw`

Puede ser:
- `"400"` → String simple
- `"400 + 100"` → Suma (solar + baterías)
- `"500 MW"` → Con unidades

**Solución**: Usar `VARCHAR(50)` en lugar de `DECIMAL`:

```sql
-- db/schema_formularios_parsed.sql:73
potencia_nominal_mw VARCHAR(50) COMMENT 'Puede ser "400 + 100" por eso VARCHAR'
```

---

## 📊 Escenarios de Error Manejados

### Escenario 1: Documento Mal Clasificado

**Problema**: API marca documento como "Formulario SAC" pero es otro tipo.

**Ejemplo real**:
```
nombre: Formulario_Verificación_Antecedentes_-_La_Aguada.pdf
tipo_documento: Formulario SAC  ← ❌ Clasificación incorrecta
```

**Manejo**:
1. Parser intenta extraer campos SAC
2. Faltan campos críticos (`razon_social`, `rut`, `nombre_proyecto`)
3. Parsing marcado como FALLIDO
4. Error registrado: `"Campos críticos faltantes: ..."`
5. ✅ Datos preservados, no se pierde información

---

### Escenario 2: Fecha Inválida

**Problema**: PDF contiene fecha imposible.

**Ejemplo real**:
```
fecha_estimada_construccion: "31-02-2024"  ← ❌ Febrero no tiene 31 días
```

**Manejo**:
1. Parser intenta convertir fecha
2. `datetime(2024, 2, 31)` lanza `ValueError`
3. Parser retorna `NULL` en lugar de fecha
4. Parsing continúa exitosamente (no falla por 1 fecha mala)
5. Log: `⚠️  Fecha inválida detectada: 31-02-2024`
6. ✅ Resto de campos guardados correctamente

---

### Escenario 3: PDF Corrupto

**Problema**: Archivo PDF no puede abrirse.

**Ejemplo**:
```python
pdf = pdfplumber.open("corrupto.pdf")  # Lanza Exception
```

**Manejo**:
```python
# src/repositories/cen.py:933-945
except Exception as e:
    error_msg = f"Error al parsear PDF: {str(e)}"

    # Registrar parsing FALLIDO
    self.insert_formulario_parseado(
        parsing_exitoso=False,
        parsing_error=error_msg
    )
    return False
```

**Resultado**:
- ✅ Error capturado en `formularios_parseados.parsing_error`
- ✅ Sistema continúa con siguiente documento
- ✅ Administrador puede revisar errors después

---

### Escenario 4: Error de Transacción en BD

**Problema**: INSERT falla por constraint violation o error de BD.

**Ejemplo**:
```python
cursor.execute("INSERT INTO formularios_sac_parsed ...")
# Falla por foreign key constraint
```

**Manejo**:
```python
# src/repositories/cen.py:916-931
except Error as e:
    conn.rollback()  # ⬅ Rollback AUTOMÁTICO

    error_msg = f"Error en transacción: {str(e)}"

    # Registrar parsing FALLIDO
    self.insert_formulario_parseado(
        parsing_exitoso=False,
        parsing_error=error_msg
    )
```

**Resultado**:
- ✅ No datos parciales en BD (rollback completo)
- ✅ Error registrado para debugging
- ✅ Documento puede re-parsearse después de fix

---

## 🔄 Re-parsing con Versiones Mejoradas

El campo `parser_version` permite identificar qué documentos fueron parseados con versiones antiguas:

```sql
-- Ver documentos parseados con versión vieja
SELECT documento_id, parser_version, parsed_at
FROM formularios_parseados
WHERE tipo_formulario = 'SAC'
  AND parsing_exitoso = 1
  AND parser_version < '2.0.0';

-- Re-parsear con versión nueva
-- El sistema actualizará automáticamente el registro (ON DUPLICATE KEY UPDATE)
```

**Uso**:
1. Mejorar parser (ej: agregar extracción de campo `tecnologia`)
2. Incrementar versión a `2.0.0`
3. Re-ejecutar parsing en documentos con `parser_version < 2.0.0`
4. Sistema actualiza datos sin perder historial

---

## 📈 Monitoreo y Debugging

### Query: Documentos Fallidos

```sql
SELECT
    fp.documento_id,
    d.nombre,
    fp.tipo_formulario,
    fp.parsing_error,
    fp.parsed_at
FROM formularios_parseados fp
JOIN documentos d ON fp.documento_id = d.id
WHERE fp.parsing_exitoso = 0
ORDER BY fp.parsed_at DESC;
```

### Query: Tasa de Éxito por Tipo

```sql
SELECT
    tipo_formulario,
    COUNT(*) AS total_intentos,
    SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) AS exitosos,
    SUM(CASE WHEN parsing_exitoso = 0 THEN 1 ELSE 0 END) AS fallidos,
    ROUND(SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS tasa_exito_pct
FROM formularios_parseados
GROUP BY tipo_formulario;
```

**Output esperado**:
```
tipo_formulario | total_intentos | exitosos | fallidos | tasa_exito_pct
----------------|----------------|----------|----------|----------------
SAC             | 1635          | 1520     | 115      | 92.97%
SUCTD           | 655           | 590      | 65       | 90.08%
FEHACIENTE      | 0             | 0        | 0        | NULL
```

---

### Query: Tasa de Éxito por Herramienta (Producer)

```sql
SELECT
    pdf_producer,
    COUNT(*) AS total_documentos,
    SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) AS exitosos,
    SUM(CASE WHEN parsing_exitoso = 0 THEN 1 ELSE 0 END) AS fallidos,
    ROUND(SUM(CASE WHEN parsing_exitoso = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS tasa_exito_pct
FROM formularios_parseados
WHERE pdf_producer IS NOT NULL
GROUP BY pdf_producer
ORDER BY total_documentos DESC;
```

**Output esperado**:
```
pdf_producer                 | total_documentos | exitosos | fallidos | tasa_exito_pct
-----------------------------|------------------|----------|----------|----------------
Microsoft: Print To PDF      | 1200             | 1180     | 20       | 98.33%
LibreOffice 7.0              | 300              | 250      | 50       | 83.33%
macOS Version 11.6.1         | 100              | 95       | 5        | 95.00%
```

**Uso**: Identificar qué herramientas generan PDFs más fáciles de parsear.

---

## 🚨 Mejores Prácticas

### 1. **Siempre usar método de alto nivel**

✅ **Correcto**:
```python
db.parse_and_store_sac_document(
    documento_id=15809,
    solicitud_id=1067,
    local_path="downloads/1067/Formulario_SAC.pdf",
    parser_version="1.0.0"
)
```

❌ **Incorrecto**:
```python
# No hacer esto manualmente - pierde transacciones y error handling
data = parse_sac_pdf("formulario.pdf")
db.insert_formulario_sac_parsed(data)  # ⚠️ Sin transacción, sin validación
```

---

### 2. **Definir campos críticos mínimos**

Para cada tipo de formulario, definir campos ESENCIALES:

```python
# SAC
required_fields_sac = ["razon_social", "rut", "nombre_proyecto"]

# SUCTD (ejemplo futuro)
required_fields_suctd = ["razon_social", "rut", "capacidad_solicitada"]
```

---

### 3. **Log warnings para datos parciales**

Datos opcionales faltantes deben loggearse pero NO fallar el parsing:

```python
if not parsed_data.get("tecnologia"):
    logger.warning(f"⚠️  Campo 'tecnologia' faltante en documento {documento_id}")
    # Continuar - no es crítico
```

---

### 4. **Validar tipos de datos**

Antes de insertar, validar tipos:

```python
# Ejemplo: potencia_propio_mw debe ser decimal o None
if parsed_data.get("consumo_propio_mw"):
    try:
        float(parsed_data["consumo_propio_mw"])
    except ValueError:
        logger.warning(f"⚠️  'consumo_propio_mw' no es decimal: {parsed_data['consumo_propio_mw']}")
        parsed_data["consumo_propio_mw"] = None
```

---

## 🎯 Casos de Uso Futuros

### 1. **Parsing de XLSX**

Misma estrategia para archivos Excel:

```python
def parse_and_store_sac_xlsx(documento_id, local_path):
    try:
        data = parse_sac_xlsx(local_path)  # ← Parser específico XLSX

        # Misma validación + transacción
        # ...

    except Exception as e:
        insert_formulario_parseado(
            parsing_exitoso=False,
            parsing_error=f"Error XLSX: {str(e)}"
        )
```

---

### 2. **Detección Automática de Versión de Formulario**

Formularios pueden cambiar formato entre años:

```python
def detect_sac_version(pdf_path):
    """Detecta qué versión de formulario SAC es (2020, 2021, 2022, etc.)."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()

        if "Versión 25-05-21" in text:
            return "v2021"
        elif "Versión 15-03-22" in text:
            return "v2022"
        else:
            return "unknown"
```

---

### 3. **Machine Learning para Clasificación**

Si API clasifica mal documentos, entrenar ML:

```python
def classify_document_type(pdf_path):
    """
    Usa ML para clasificar tipo real de documento.
    Útil cuando API marca tipo incorrectamente.
    """
    features = extract_features(pdf_path)
    predicted_type = ml_model.predict(features)

    return predicted_type  # "SAC", "SUCTD", "FEHACIENTE", "OTHER"
```

---

## 📚 Referencias

- **Parser SAC**: `src/parsers/pdf_sac.py`
- **Repository Methods**: `src/repositories/cen.py:561-946`
- **Schema**: `db/schema_formularios_parsed.sql`
- **Test End-to-End**: `test_sac_pipeline.py`

---

**Última actualización**: 2025-10-20
**Parser Version**: 1.0.0
**Documentos parseados exitosamente**: 2 SAC (100% success rate en test)
