# Documentación de la API - CEN Acceso Abierto

**Fuente**: Coordinador Eléctrico Nacional (CEN) de Chile
**Base URL**: `https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public`

---

## Índice

1. [Parámetros de la API](#parámetros-de-la-api)
2. [Tipos de Endpoints (tipo=0 a tipo=11)](#tipos-de-endpoints)
3. [Tipos de Solicitud](#tipos-de-solicitud)
4. [Documentos de Interés](#documentos-de-interés)
5. [Estrategia de Extracción](#estrategia-de-extracción)

---

## Parámetros de la API

La API utiliza los siguientes parámetros en la URL:

| Parámetro | Tipo | Descripción | Ejemplo |
|-----------|------|-------------|---------|
| `tipo` | int | Tipo de datos a consultar (0-11) | `tipo=6` |
| `anio` | int/null | Año de las solicitudes | `anio=2025` |
| `tipo_solicitud_id` | int | ID del tipo de solicitud (1=SAC, 2=SUCTD, 3=FEHACIENTES) | `tipo_solicitud_id=2` |
| `solicitud_id` | int/null | ID específico de una solicitud | `solicitud_id=2756` |

**Formato de URL**:
```
https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public?tipo={tipo}&anio={anio}&tipo_solicitud_id={tipo_solicitud_id}&solicitud_id={solicitud_id}
```

---

## Tipos de Endpoints

### TIPO 0: Años Disponibles en la Base de Datos

**Propósito**: Obtener la lista de años que tienen datos disponibles en el sistema.

**Ejemplo de Request**:
```
?tipo=0&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {"id": 784, "anio": 2021},
  {"id": 1097, "anio": 2022},
  {"id": 1366, "anio": 2023},
  {"id": 1631, "anio": 2024},
  {"id": 1864, "anio": 2025}
]
```

**Total de registros**: 9 años disponibles (desde 2017 hasta 2025)

---

### TIPO 1: Resumen Mensual de Solicitudes por Año

**Propósito**: Estadísticas mensuales agregadas de solicitudes por tipo (SAC, SUCT, FEHACIENTES).

**Ejemplo de Request**:
```
?tipo=1&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "mes": 1,
    "anio": 2025,
    "nombre": "Enero",
    "total": 34,
    "sasc": 12,
    "suct": 5,
    "fehacientes": 17
  }
]
```

**Total de registros**: 12 (uno por cada mes del año)

**Campos**:
- `mes`: Número del mes (1-12)
- `anio`: Año de las solicitudes
- `nombre`: Nombre del mes en español
- `total`: Total de solicitudes en ese mes
- `sasc`: Solicitudes de Acceso y Conexión (SAC)
- `suct`: Solicitudes de Uso de Capacidad de Transporte Dedicada (SUCTD)
- `fehacientes`: Proyectos Fehacientes

---

### TIPO 2: Distribución Geográfica de Solicitudes

**Propósito**: Cantidad de solicitudes por ubicación geográfica (región, provincia, comuna).

**Ejemplo de Request**:
```
?tipo=2&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "total": 71,
    "comuna": "Maria Elena",
    "provincia": "Tocopilla",
    "region": "Antofagasta",
    "id_region": 3,
    "ordinal": "II"
  }
]
```

**Total de registros**: 14 comunas con solicitudes en 2025

**Campos**:
- `total`: Número de solicitudes en esa ubicación
- `comuna`: Nombre de la comuna
- `provincia`: Nombre de la provincia
- `region`: Nombre de la región
- `id_region`: ID numérico de la región
- `ordinal`: Número ordinal de la región (ej: "II", "RM", "XV")

---

### TIPO 3: Tipos de Solicitud (Resumen)

**Propósito**: Resumen de los tres tipos principales de solicitudes con totales por año.

**Ejemplo de Request**:
```
?tipo=3&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "tipo_id": 1,
    "nombre": "SAC",
    "total": 223,
    "anio": 2025,
    "color": "#fd7e14"
  },
  {
    "tipo_id": 2,
    "nombre": "SUCTD",
    "total": 82,
    "anio": 2025,
    "color": "#6cb33f"
  },
  {
    "tipo_id": 3,
    "nombre": "FEHACIENTES",
    "total": 93,
    "anio": 2025,
    "color": "#00a8f3"
  }
]
```

**Total de registros**: 3 (uno por cada tipo de solicitud)

**Tipos de Solicitud**:

| tipo_id | Nombre | Descripción | Color |
|---------|--------|-------------|-------|
| 1 | SAC | Solicitud de Acceso y Conexión | Naranja (#fd7e14) |
| 2 | SUCTD | Solicitud de Uso de Capacidad de Transporte Dedicada | Verde (#6cb33f) |
| 3 | FEHACIENTES | Proyectos Fehacientes | Azul (#00a8f3) |

---

### TIPO 4: Tecnologías por Tipo (Solicitudes del Año)

**Propósito**: Cantidad de solicitudes por tipo de tecnología de generación (solo para el año especificado).

**Ejemplo de Request**:
```
?tipo=4&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "id": 1,
    "tipo": "Hidroeléctrica",
    "total": 3
  },
  {
    "id": 2,
    "tipo": "Eólico",
    "total": 6
  },
  {
    "id": 3,
    "tipo": "Solar",
    "total": 11
  }
]
```

**Total de registros**: 6 tipos de tecnología

**Tecnologías identificadas**:
1. Hidroeléctrica
2. Eólico
3. Solar
4. Térmica
5. Híbrido
6. Consumo

---

### TIPO 5: Tipos de Tecnología (Renovable vs No Renovable)

**Propósito**: Clasificación de tecnologías según si son renovables o no.

**Ejemplo de Request**:
```
?tipo=5&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "id": 15,
    "nombre": "Híbrido",
    "total": 332,
    "anio": 2025,
    "renovable": 1,
    "tipo": "Renovable"
  }
]
```

**Campos**:
- `renovable`: 1 = Renovable, 0 = No renovable
- `tipo`: "Renovable" o "No Renovable"

---

### TIPO 6: Solicitudes Completas ⭐ (ENDPOINT PRINCIPAL)

**Propósito**: **Este es el endpoint más importante**. Devuelve todas las solicitudes con información completa de proyectos, ubicación, empresa solicitante, estado, etc.

**Ejemplo de Request**:
```
?tipo=6&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "id": 2756,
    "tipo_solicitud_id": 2,
    "tipo_solicitud": "SUCT",
    "estado_solicitud_id": 101,
    "estado_solicitud": "Solicitud ingresada",
    "create_date": "2025-10-15T17:22:32.000Z",
    "nombre_se": "S/E Tap Off La Cruz 23 kV",
    "nivel_tension": 23,
    "seccion_barra_conexion": "Principal",
    "pano_conexion": "TBD",
    "fecha_estimada_conexion": "2029-03-31T00:00:00.000Z",
    "tipo_tecnologia_nombre": "Híbrido",
    "update_date": "2025-10-15T17:22:32.000Z",
    "proyecto_id": 2830,
    "deleted_at": null,
    "empresa_solicitante": null,
    "rut_solicitante": null,
    "calificacion_id": 5,
    "calificacion_nombre": "Dedicada",
    "proyecto": "Taruca",
    "lat": "-22.27253695149175",
    "lng": "-69.6601854126403",
    "cancelled_at": null,
    "potencia_nominal": "9",
    "comuna_id": 12,
    "comuna": "Antofagasta",
    "nup": null,
    "provincia_id": 5,
    "provincia": "Antofagasta",
    "region_id": 3,
    "region": "Antofagasta",
    "re_ordinal": "II",
    "etapa_id": 101,
    "etapa": "Antecedentes",
    "rut_empresa": "76.257.813-1",
    "razon_social": "Grenergy Renovables Pacific Limitada",
    "cup": "",
    "fecha_informe": null,
    "last_prorroga_dec_const": null,
    "plazo_dec_en_const": null,
    "informe_fechaciente": null
  }
]
```

**Total de registros**: 2,448 solicitudes para el año 2025

**Campos principales**:
- `id`: ID único de la solicitud (usar como `solicitud_id` en tipo=11)
- `tipo_solicitud_id`: 1=SASC, 2=SUCT, 3=FEHACIENTES
- `estado_solicitud`: Estado actual del proceso
- `proyecto`: Nombre del proyecto
- `proyecto_id`: ID del proyecto
- `rut_empresa`: RUT de la empresa solicitante
- `razon_social`: Razón social de la empresa
- `tipo_tecnologia_nombre`: Tipo de tecnología (Solar, Eólico, etc.)
- `potencia_nominal`: Potencia nominal del proyecto (MW)
- Ubicación: `comuna`, `provincia`, `region`, `lat`, `lng`
- Fechas: `create_date`, `update_date`, `fecha_estimada_conexion`

---

### TIPO 7: Estados de Solicitudes por Tipo

**Propósito**: Distribución de solicitudes según su estado de tramitación, agrupadas por tipo de solicitud.

**Ejemplo de Request**:
```
?tipo=7&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "total": 42,
    "estado": "Desarrollo de estudios y/o antecedentes",
    "tipo": "SASC"
  },
  {
    "total": 32,
    "estado": "Rechazada",
    "tipo": "SASC"
  }
]
```

**Total de registros**: 31 combinaciones de estado-tipo

**Estados comunes**:
- Solicitud ingresada
- Evaluación Admisibilidad
- Desarrollo de estudios y/o antecedentes
- Rechazada
- Detenida a la espera de definición de ingeniería de la obra
- Aprobada
- Desistida

---

### TIPO 8: Potencia por Tipo de Tecnología

**Propósito**: Capacidad instalada (MW) total por tipo de tecnología, con cantidad de solicitudes.

**Ejemplo de Request**:
```
?tipo=8&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "id": 3,
    "tipo": "Solar",
    "cantidad_solicitudes": 18,
    "total": 1315
  }
]
```

**Total de registros**: 6 tipos de tecnología

**Campos**:
- `cantidad_solicitudes`: Número de proyectos
- `total`: Capacidad total en MW

---

### TIPO 9: Potencia por Tecnología con Estados

**Propósito**: Similar a tipo 8, pero desglosado por estado (rechazadas, desistidas, aprobadas, en curso).

**Ejemplo de Request**:
```
?tipo=9&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  {
    "id": 2,
    "tipo": "Eólico",
    "cantidad_solicitudes": 11,
    "total": 1775,
    "rechazadas": 360,
    "desistidas": 1080,
    "aprobadas": 200,
    "en_curso": 135
  }
]
```

**Total de registros**: 9 tipos de tecnología

**Campos adicionales**:
- `rechazadas`: MW rechazados
- `desistidas`: MW desistidos
- `aprobadas`: MW aprobados
- `en_curso`: MW en curso

---

### TIPO 10: Resumen Anual de Estados

**Propósito**: Totales agregados por año de solicitudes según su estado final.

**Ejemplo de Request**:
```
?tipo=10&anio=2025&tipo_solicitud_id=0&solicitud_id=null
```

**Ejemplo de Response**:
```json
[
  [
    {
      "annio": 2025,
      "rechazadas": 62,
      "desistidas": 40,
      "aprobadas": 66,
      "en_curso": 230
    }
  ]
]
```

**Total de registros**: 1 (resumen del año consultado)

---

### TIPO 11: Documentos de una Solicitud ⭐ (DOCUMENTOS)

**Propósito**: **Segundo endpoint más importante**. Devuelve todos los documentos adjuntos a una solicitud específica, incluyendo los formularios SUCTD, SAC y Formulario_proyecto_fehaciente.

**Ejemplo de Request**:
```
?tipo=11&anio=null&tipo_solicitud_id=null&solicitud_id=2756
```

**Ejemplo de Response**:
```json
[
  {
    "id": 58958,
    "nombre": "PMG_Taruca_Formulario_de_solicitud_y_antecedentes_SUCTD.pdf",
    "ruta_s3": "empresa-1/proyecto-2830/solicitud-2756/Formulario_SUCTD/76.257.813-1/15-9-2025 17:22:40_PMG_Taruca_Formulario_de_solicitud_y_antecedentes_SUCTD.pdf",
    "solicitud_id": 2756,
    "tipo_documento_id": 44,
    "create_date": "2025-10-15T17:22:40.000Z",
    "update_date": "2025-10-15T17:22:48.000Z",
    "deleted": 0,
    "user_management_id": null,
    "empresa_id": "76.257.813-1",
    "estado_solicitud_id": "101",
    "version_id": "8AOGKTVS6tncO0dBdeax0w2Q58JkJkfQ",
    "visible": 1,
    "garantia": null,
    "etapa_id": 101,
    "etapa": "Antecedentes",
    "tipo_documento": "Formulario SUCTD",
    "razon_social": "Grenergy Renovables Pacific Limitada"
  }
]
```

**Total de registros**: Variable (depende de la solicitud)

**Campos principales**:
- `id`: ID único del documento
- `nombre`: Nombre del archivo
- `ruta_s3`: Ruta del archivo en S3 (AWS)
- `solicitud_id`: ID de la solicitud padre
- `tipo_documento_id`: ID del tipo de documento
- `tipo_documento`: **Nombre del tipo de documento** (ej: "Formulario SUCTD")
- `empresa_id`: RUT de la empresa
- `razon_social`: Razón social de la empresa
- `etapa_id`: ID de la etapa del proceso
- `etapa`: Nombre de la etapa
- `version_id`: Versión del documento en S3

---

## Tipos de Solicitud

### SAC (Solicitud de Acceso y Conexión)

**ID**: 1
**Color**: Naranja (#fd7e14)
**Descripción**: Solicitudes para acceder y conectarse al sistema de transmisión eléctrica.

**Formulario asociado**: "Formulario SAC"

---

### SUCTD (Solicitud de Uso de Capacidad de Transporte Dedicada)

**ID**: 2
**Color**: Verde (#6cb33f)
**Descripción**: Solicitudes para uso de capacidad de transporte en líneas dedicadas.

**Formulario asociado**: "Formulario SUCTD"

---

### FEHACIENTES (Proyectos Fehacientes)

**ID**: 3
**Color**: Azul (#00a8f3)
**Descripción**: Proyectos que ya cuentan con respaldo fehaciente para su desarrollo.

**Documento asociado**: "Formulario_proyecto_fehaciente"

---

## Documentos de Interés

### Documentos Objetivo

Los tres tipos de documentos que nos interesan extraer son:

1. **Formulario SUCTD** (`tipo_documento_id` = 44)
   - Extensiones: `.pdf` (más común), `.xlsx`
   - Contiene: Información técnica del proyecto de transporte dedicado

2. **Formulario SAC** (`tipo_documento_id` = ?)
   - Extensiones: `.pdf`, `.xlsx`
   - Contiene: Información técnica del proyecto de acceso y conexión

3. **Formulario_proyecto_fehaciente** (`tipo_documento_id` = ?)
   - Extensiones: `.pdf`
   - Contiene: Antecedentes fehacientes del proyecto

### Otros Tipos de Documentos

Otros documentos disponibles en tipo=11:
- Carta gantt
- Otros documentos
- Garantía
- Diagrama unilineal
- Planos de ubicación
- Estudios técnicos
- Y más...

---

## Estrategia de Extracción

### Flujo de Trabajo

1. **Obtener años disponibles** (tipo=0)
   - Filtrar desde 2020 en adelante (para producción)
   - Usar solo 2025 para desarrollo/pruebas

2. **Obtener solicitudes por año** (tipo=6)
   - Parámetro: `tipo=6&anio=2025&tipo_solicitud_id=0&solicitud_id=null`
   - Extraer todos los `id` de solicitudes
   - Guardar datos de solicitud en tabla `solicitudes`

3. **Obtener documentos por solicitud** (tipo=11)
   - Para cada `solicitud_id` obtenido en paso 2
   - Parámetro: `tipo=11&anio=null&tipo_solicitud_id=null&solicitud_id={id}`
   - Filtrar por `tipo_documento` en: ["Formulario SUCTD", "Formulario SAC", "Formulario_proyecto_fehaciente"]
   - Guardar metadata en tabla `documentos`
   - Descargar archivo desde `ruta_s3` (si es necesario)

### Esquema de Base de Datos Propuesto

#### Tabla: `solicitudes`

Almacena la información completa de cada solicitud (tipo=6):

```sql
CREATE TABLE solicitudes (
    id BIGINT PRIMARY KEY,  -- solicitud_id de la API
    tipo_solicitud_id INT,
    tipo_solicitud VARCHAR(20),
    estado_solicitud_id INT,
    estado_solicitud VARCHAR(255),
    create_date TIMESTAMP,
    update_date TIMESTAMP,
    proyecto_id INT,
    proyecto VARCHAR(255),
    rut_empresa VARCHAR(20),
    razon_social VARCHAR(255),
    tipo_tecnologia_nombre VARCHAR(100),
    potencia_nominal VARCHAR(50),
    -- Ubicación
    comuna_id INT,
    comuna VARCHAR(100),
    provincia_id INT,
    provincia VARCHAR(100),
    region_id INT,
    region VARCHAR(100),
    lat VARCHAR(50),
    lng VARCHAR(50),
    -- Conexión
    nombre_se VARCHAR(255),
    nivel_tension INT,
    seccion_barra_conexion VARCHAR(100),
    pano_conexion VARCHAR(100),
    fecha_estimada_conexion DATE,
    -- Otros
    calificacion_id INT,
    calificacion_nombre VARCHAR(100),
    etapa_id INT,
    etapa VARCHAR(100),
    nup INT,
    cup VARCHAR(50),
    deleted_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tipo_solicitud (tipo_solicitud_id),
    INDEX idx_rut_empresa (rut_empresa),
    INDEX idx_proyecto_id (proyecto_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### Tabla: `documentos`

Almacena la metadata de cada documento (tipo=11):

```sql
CREATE TABLE documentos (
    id BIGINT PRIMARY KEY,  -- documento_id de la API
    solicitud_id BIGINT NOT NULL,
    nombre VARCHAR(500),
    ruta_s3 TEXT,
    tipo_documento_id INT,
    tipo_documento VARCHAR(100),
    empresa_id VARCHAR(20),
    razon_social VARCHAR(255),
    create_date TIMESTAMP,
    update_date TIMESTAMP,
    estado_solicitud_id VARCHAR(20),
    etapa_id INT,
    etapa VARCHAR(100),
    version_id VARCHAR(100),
    visible TINYINT(1),
    deleted TINYINT(1),
    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    downloaded TINYINT(1) DEFAULT 0,
    downloaded_at TIMESTAMP NULL,
    local_path VARCHAR(500),
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id),
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_tipo_documento (tipo_documento),
    INDEX idx_tipo_documento_id (tipo_documento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Configuración de URLs Dinámica

En lugar de listar URLs estáticas, se propone configurar parámetros base:

**.env**:
```env
# CEN API Configuration
CEN_API_BASE_URL=https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public

# Years to fetch (comma-separated)
CEN_YEARS=2025  # Para desarrollo, en producción: 2020,2021,2022,2023,2024,2025

# Document types to extract (comma-separated IDs)
CEN_DOCUMENT_TYPES=Formulario SUCTD,Formulario SAC,Formulario_proyecto_fehaciente
```

### Estrategia de Append-Only

- ✅ **Insertar** solo solicitudes nuevas (comparar por `id`)
- ✅ **Insertar** solo documentos nuevos (comparar por `id`)
- ❌ **No actualizar** registros existentes
- ❌ **No eliminar** registros históricos
- 📊 **Preservar** historial completo

---

## Notas Adicionales

- La API utiliza AWS Lambda en `us-east-2`
- Los archivos están almacenados en S3 (ruta en campo `ruta_s3`)
- Algunos campos pueden ser `null` si no aplican
- Las fechas están en formato ISO 8601 con zona horaria UTC
- La API no requiere autenticación (es pública)

---

**Última actualización**: 2025-10-19
**Investigado por**: Claude Code
**Estado**: Completo ✅
