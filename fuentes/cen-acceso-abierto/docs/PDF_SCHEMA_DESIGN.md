# Diseño de Schema para Datos Parseados de PDFs

## Contexto

Los formularios PDF (SAC, SUCTD, Fehaciente) contienen información **más detallada** que la tabla `solicitudes`. Necesitamos tablas adicionales para almacenar todos los campos extraídos del parsing de PDFs.

---

## 🎯 Estrategia de Diseño

### Opción 1: Tabla Única con JSON ❌
```sql
CREATE TABLE formularios_parseados (
    id BIGINT PRIMARY KEY,
    documento_id BIGINT,
    data JSON  -- Todo en un campo JSON
);
```
**Desventajas**: Difícil de consultar, no hay validación de tipos, no permite índices en campos específicos.

### Opción 2: Tablas Específicas por Tipo ✅ RECOMENDADA

```sql
CREATE TABLE formularios_sac_parsed (...)
CREATE TABLE formularios_suctd_parsed (...)
CREATE TABLE formularios_fehaciente_parsed (...)
```

**Ventajas**:
- ✅ Cada tipo tiene sus propios campos específicos
- ✅ Tipos de datos validados
- ✅ Índices en campos importantes
- ✅ Fácil de consultar y analizar
- ✅ Schema auto-documentado

---

## 📊 Campos Identificados en Formulario SAC (PDF)

Basado en el análisis de tabla extraída con pdfplumber:

### **Sección 1: Antecedentes Generales del Solicitante**
| Campo | Tipo | Ejemplo |
|-------|------|---------|
| razon_social | VARCHAR(255) | Enel Green Power Chile S.A. |
| rut | VARCHAR(20) | 76.412.562-2 |
| giro | VARCHAR(255) | Generación eléctrica |
| domicilio_legal | VARCHAR(500) | Santa Rosa 76, piso 17, Santiago |
| representante_legal_nombre | VARCHAR(255) | Ali Shakhtur Said |
| representante_legal_email | VARCHAR(255) | Ali.Shakhtur@enel.com |
| representante_legal_telefono | VARCHAR(50) | +56226308559 |
| coordinador_proyecto_1_nombre | VARCHAR(255) | Miguel Monasterio |
| coordinador_proyecto_1_email | VARCHAR(255) | miguel.monasterio@enel.com |
| coordinador_proyecto_1_telefono | VARCHAR(50) | +56966803530 |
| coordinador_proyecto_2_nombre | VARCHAR(255) | Pablo Castro |
| coordinador_proyecto_2_email | VARCHAR(255) | pablo.castro@enel.com |
| coordinador_proyecto_2_telefono | VARCHAR(50) | +56942886196 |

### **Sección 2: Antecedentes del Proyecto**
| Campo | Tipo | Ejemplo |
|-------|------|---------|
| nombre_proyecto | VARCHAR(255) | La Aguada |
| tipo_proyecto | VARCHAR(50) | Gen / Trans / Consumo |
| tecnologia | VARCHAR(255) | Híbrido (Solar Fotovoltaica + BESS) |
| potencia_nominal_mw | VARCHAR(50) | 400 + 100 |
| consumo_propio_mw | DECIMAL(10,2) | 0.3 |
| factor_potencia | DECIMAL(5,2) | 0.95 |
| coordenadas_utm_huso | VARCHAR(10) | 19 H |
| coordenadas_utm_este | VARCHAR(50) | 273601.00 E |
| coordenadas_utm_norte | VARCHAR(50) | 6188194.00 m S |
| proyecto_comuna | VARCHAR(100) | Peralillo |
| proyecto_region | VARCHAR(100) | Libertador General Bernardo O'Higgins |

### **Sección 3: Antecedentes del Punto de Conexión**
| Campo | Tipo | Ejemplo |
|-------|------|---------|
| nombre_subestacion | VARCHAR(255) | S/E Portezuelo |
| nivel_tension_kv | VARCHAR(50) | 220 kV |
| caracter_conexion | VARCHAR(50) | Indefinido / Temporal |
| fecha_estimada_construccion | DATE | 31-02-2024 |
| fecha_estimada_interconexion | DATE | 01-12-2024 |
| conexion_coordenadas_utm_huso | VARCHAR(10) | 19 H |
| conexion_coordenadas_utm_este | VARCHAR(50) | 259639.49 m E |
| conexion_coordenadas_utm_norte | VARCHAR(50) | 6196194.39 m S |
| conexion_comuna | VARCHAR(100) | Marchigüe |
| conexion_region | VARCHAR(100) | Libertador General Bernardo O'Higgins |

---

## 📝 Schema SQL Propuesto

### Tabla: `formularios_parseados`

Tabla de tracking para saber qué documentos ya fueron parseados:

```sql
CREATE TABLE IF NOT EXISTS formularios_parseados (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    documento_id BIGINT NOT NULL UNIQUE COMMENT 'FK a documentos.id',
    tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE') NOT NULL,
    formato_archivo ENUM('PDF', 'XLSX', 'XLS') NOT NULL,

    -- Estado del parsing
    parsing_exitoso BOOLEAN NOT NULL DEFAULT FALSE,
    parsing_error TEXT COMMENT 'Mensaje de error si falló',
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    parser_version VARCHAR(50) COMMENT 'Versión del parser usado',

    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    INDEX idx_tipo_formulario (tipo_formulario),
    INDEX idx_parsing_exitoso (parsing_exitoso),
    INDEX idx_parsed_at (parsed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracking de parsing de formularios PDF/XLSX';
```

### Tabla: `formularios_sac_parsed`

Datos estructurados del Formulario SAC:

```sql
CREATE TABLE IF NOT EXISTS formularios_sac_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE COMMENT 'FK a formularios_parseados.id',
    documento_id BIGINT NOT NULL COMMENT 'FK a documentos.id',
    solicitud_id BIGINT NOT NULL COMMENT 'FK a solicitudes.id',

    -- Antecedentes Generales del Solicitante
    razon_social VARCHAR(255),
    rut VARCHAR(20),
    giro VARCHAR(255),
    domicilio_legal VARCHAR(500),

    -- Representante Legal
    representante_legal_nombre VARCHAR(255),
    representante_legal_email VARCHAR(255),
    representante_legal_telefono VARCHAR(50),

    -- Coordinadores de Proyecto (hasta 3)
    coordinador_proyecto_1_nombre VARCHAR(255),
    coordinador_proyecto_1_email VARCHAR(255),
    coordinador_proyecto_1_telefono VARCHAR(50),

    coordinador_proyecto_2_nombre VARCHAR(255),
    coordinador_proyecto_2_email VARCHAR(255),
    coordinador_proyecto_2_telefono VARCHAR(50),

    coordinador_proyecto_3_nombre VARCHAR(255),
    coordinador_proyecto_3_email VARCHAR(255),
    coordinador_proyecto_3_telefono VARCHAR(50),

    -- Antecedentes del Proyecto
    nombre_proyecto VARCHAR(255),
    tipo_proyecto VARCHAR(50) COMMENT 'Gen / Trans / Consumo',
    tecnologia VARCHAR(255),
    potencia_nominal_mw VARCHAR(50) COMMENT 'Puede ser "400 + 100" por eso VARCHAR',
    consumo_propio_mw DECIMAL(10,2),
    factor_potencia DECIMAL(5,2),

    -- Ubicación Geográfica del Proyecto
    proyecto_coordenadas_utm_huso VARCHAR(10),
    proyecto_coordenadas_utm_este VARCHAR(50),
    proyecto_coordenadas_utm_norte VARCHAR(50),
    proyecto_comuna VARCHAR(100),
    proyecto_region VARCHAR(100),

    -- Antecedentes del Punto de Conexión
    nombre_subestacion VARCHAR(255),
    nivel_tension_kv VARCHAR(50),
    caracter_conexion VARCHAR(50) COMMENT 'Indefinido / Temporal',
    fecha_estimada_construccion DATE,
    fecha_estimada_interconexion DATE,

    -- Ubicación Geográfica del Punto de Conexión
    conexion_coordenadas_utm_huso VARCHAR(10),
    conexion_coordenadas_utm_este VARCHAR(50),
    conexion_coordenadas_utm_norte VARCHAR(50),
    conexion_comuna VARCHAR(100),
    conexion_region VARCHAR(100),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_rut (rut),
    INDEX idx_nombre_proyecto (nombre_proyecto),
    INDEX idx_tipo_proyecto (tipo_proyecto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios SAC (PDF/XLSX)';
```

### Tabla: `formularios_suctd_parsed`

Similar estructura para SUCTD (a definir después de analizar un PDF SUCTD):

```sql
CREATE TABLE IF NOT EXISTS formularios_suctd_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE,
    documento_id BIGINT NOT NULL,
    solicitud_id BIGINT NOT NULL,

    -- Campos específicos de SUCTD
    -- (A completar después de analizar estructura)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios SUCTD (PDF/XLSX)';
```

### Tabla: `formularios_fehaciente_parsed`

Similar estructura para Fehaciente (a definir después de analizar):

```sql
CREATE TABLE IF NOT EXISTS formularios_fehaciente_parsed (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    formulario_parseado_id BIGINT NOT NULL UNIQUE,
    documento_id BIGINT NOT NULL,
    solicitud_id BIGINT NOT NULL,

    -- Campos específicos de Fehaciente
    -- (A completar después de analizar estructura)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,

    INDEX idx_solicitud_id (solicitud_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Datos parseados de Formularios Fehaciente (PDF/XLSX)';
```

---

## 🔗 Relaciones Entre Tablas

```
solicitudes (1) ──┬──> (N) documentos
                  │
                  └──> (N) formularios_parseados ──> (1) formularios_sac_parsed
                                                  └─> (1) formularios_suctd_parsed
                                                  └─> (1) formularios_fehaciente_parsed
```

**Explicación**:
1. Una **solicitud** puede tener múltiples **documentos**
2. Cada **documento** puede tener un registro en **formularios_parseados** (tracking)
3. Cada **formulario_parseado** tiene UNA entrada en la tabla específica según tipo

---

## 📋 Vistas Útiles

### Vista: Solicitudes con Formularios Parseados

```sql
CREATE OR REPLACE VIEW solicitudes_con_formularios_parseados AS
SELECT
    s.id AS solicitud_id,
    s.proyecto,
    s.tipo_solicitud,

    -- SAC parseado
    sac.id AS tiene_sac_parseado,
    sac.nombre_proyecto AS sac_nombre_proyecto,
    sac.potencia_nominal_mw AS sac_potencia,

    -- SUCTD parseado
    suctd.id AS tiene_suctd_parseado,

    -- Fehaciente parseado
    feh.id AS tiene_fehaciente_parseado

FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
LEFT JOIN formularios_parseados fp ON d.id = fp.documento_id
LEFT JOIN formularios_sac_parsed sac ON fp.id = sac.formulario_parseado_id
LEFT JOIN formularios_suctd_parsed suctd ON fp.id = suctd.formulario_parseado_id
LEFT JOIN formularios_fehaciente_parsed feh ON fp.id = feh.formulario_parseado_id;
```

---

## 🎯 Estrategia de Parsing

### Flujo de Trabajo:

1. **Verificar si ya fue parseado**:
   ```sql
   SELECT id FROM formularios_parseados
   WHERE documento_id = ? AND parsing_exitoso = TRUE
   ```

2. **Parsear documento** (PDF o XLSX)

3. **Insertar en `formularios_parseados`**:
   ```python
   formulario_parseado_id = insert_formulario_parseado(
       documento_id, tipo_formulario, formato_archivo,
       parsing_exitoso=True, parser_version='1.0.0'
   )
   ```

4. **Insertar datos parseados** en tabla específica:
   ```python
   if tipo_formulario == 'SAC':
       insert_formulario_sac_parsed(formulario_parseado_id, datos_parseados)
   ```

---

## 🚨 Consideraciones Importantes

### 1. **Duplicados de Datos**

Muchos campos en `formularios_*_parsed` **YA EXISTEN** en la tabla `solicitudes`:
- `nombre_proyecto` → `solicitudes.proyecto`
- `tipo_proyecto` → `solicitudes.tipo_solicitud`
- `rut` → `solicitudes.rut_empresa`

**Decisión**:
- ✅ **Mantener ambos** para:
  - Comparar datos API vs PDF (detectar inconsistencias)
  - Tener datos completos aunque falte la solicitud en API
  - Audit trail completo

### 2. **Campos con Formato Flexible**

Algunos campos tienen valores variables:
- `potencia_nominal_mw`: "400", "400 + 100", "500 MW"
- `fechas`: Diferentes formatos de fecha

**Solución**: Usar VARCHAR para campos flexibles, normalizar después si es necesario.

### 3. **Coordinadores de Proyecto**

Pueden haber 1, 2 o 3 coordinadores.

**Solución**:
- Opción A (elegida): 3 sets de campos `coordinador_proyecto_N_*`
- Opción B: Tabla separada `coordinadores_proyecto` (más normalizado pero más complejo)

---

## 📊 Orden de Implementación

1. ✅ Tabla `formularios_parseados` (tracking)
2. ✅ Tabla `formularios_sac_parsed` (primero porque tenemos muestra)
3. ⏳ Descargar y analizar SUCTD PDF
4. ⏳ Tabla `formularios_suctd_parsed`
5. ⏳ Descargar y analizar Fehaciente PDF
6. ⏳ Tabla `formularios_fehaciente_parsed`

---

**Próximo paso**: Implementar parser de SAC con pdfplumber
