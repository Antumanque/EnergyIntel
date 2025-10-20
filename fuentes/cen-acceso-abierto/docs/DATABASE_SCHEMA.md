# Esquema de Base de Datos - CEN Acceso Abierto

**Última actualización**: 2025-10-19

---

## Índice

1. [Visión General](#visión-general)
2. [Tablas de Datos](#tablas-de-datos)
3. [Vistas](#vistas)
4. [Relaciones entre Tablas](#relaciones-entre-tablas)
5. [Orden de Llenado](#orden-de-llenado)

---

## Visión General

Este sistema extrae y almacena datos del **Coordinador Eléctrico Nacional (CEN) de Chile** a través de su API pública de Acceso Abierto.

### URL Base
```
https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public
```

### Filosofía de Datos

- **Append-only**: Solo se insertan nuevos registros, **NUNCA** se actualizan ni eliminan
- **Datos crudos + Normalizados**: Se guardan respuestas crudas (`raw_api_data`) y datos estructurados
- **Histórico completo**: Preserva todo el historial para auditoría y análisis

---

## Tablas de Datos

### 1. `raw_api_data` 🗄️

**Propósito**: Almacenar respuestas RAW (sin procesar) de TODOS los endpoints de la API.

**Fuente de datos**:
- Cualquier llamada a la API del CEN
- Se usa como "caché histórico" de todas las extracciones

**Estructura**:
```sql
CREATE TABLE raw_api_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_url VARCHAR(500),      -- URL completa que se consultó
    fetched_at TIMESTAMP,         -- Cuándo se hizo la extracción
    status_code INT,              -- HTTP status (200, 404, etc.)
    data JSON,                    -- Respuesta completa en JSON
    error_message TEXT            -- Si falló, el mensaje de error
);
```

**Ejemplo de datos**:
```
source_url: https://...public/interesados
status_code: 200
data: [{"solicitud_id": 219, "razon_social": "Codelco", ...}, ...]
```

**Cuándo se llena**: Cada vez que se hace una llamada a la API, independiente del endpoint.

---

### 2. `solicitudes` 📋

**Propósito**: Información estructurada de cada **solicitud de conexión eléctrica** (proyectos).

**Fuente de datos**:
- **Endpoint API**: `?tipo=6&anio={year}&tipo_solicitud_id=0&solicitud_id=null`
- Extrae TODAS las solicitudes de un año específico

**Estructura clave**:
```sql
CREATE TABLE solicitudes (
    id BIGINT PRIMARY KEY,              -- solicitud_id de la API (ej: 2756)
    tipo_solicitud_id INT,              -- 1=SAC, 2=SUCTD, 3=FEHACIENTES
    tipo_solicitud VARCHAR(20),         -- Nombre del tipo
    proyecto VARCHAR(255),              -- Nombre del proyecto (ej: "Taruca")
    proyecto_id INT,                    -- ID del proyecto
    rut_empresa VARCHAR(20),            -- RUT de la empresa principal
    razon_social VARCHAR(255),          -- Nombre de la empresa principal
    tipo_tecnologia_nombre VARCHAR(100),-- Solar, Eólico, Híbrido, etc.
    potencia_nominal VARCHAR(50),       -- Potencia en MW

    -- Ubicación geográfica
    comuna VARCHAR(100),
    provincia VARCHAR(100),
    region VARCHAR(100),
    lat VARCHAR(50),                    -- Latitud
    lng VARCHAR(50),                    -- Longitud

    -- Conexión eléctrica
    nombre_se VARCHAR(255),             -- Nombre de la subestación
    nivel_tension INT,                  -- kV
    fecha_estimada_conexion DATE,

    -- Estado del proceso
    estado_solicitud VARCHAR(255),
    etapa VARCHAR(100),

    -- Metadata
    fetched_at TIMESTAMP                -- Cuándo se extrajo
);
```

**Ejemplo de registro**:
```
id: 2756
tipo_solicitud: "SUCT"
proyecto: "Taruca"
rut_empresa: "76.257.813-1"
razon_social: "Grenergy Renovables Pacific Limitada"
tipo_tecnologia_nombre: "Híbrido"
potencia_nominal: "9"
region: "Antofagasta"
comuna: "Antofagasta"
estado_solicitud: "Solicitud ingresada"
etapa: "Antecedentes"
```

**Cuándo se llena**: Al ejecutar la extracción de solicitudes por año.

**Relaciones**:
- Una solicitud puede tener **múltiples empresas interesadas** → `interesados.solicitud_id`
- Una solicitud puede tener **múltiples documentos** → `documentos.solicitud_id`

---

### 3. `interesados` 🏢

**Propósito**: Empresas **stakeholders** (partes interesadas) en cada solicitud.

**¿Por qué existe?**: Una solicitud puede involucrar a múltiples empresas (no solo la empresa solicitante). Por ejemplo:
- Empresa generadora
- Empresa de transmisión
- Empresas que comparten la subestación
- Empresas financiadoras

**Fuente de datos**:
- **Endpoint API**: `https://...public/interesados`
- Devuelve TODAS las relaciones solicitud-empresa del sistema

**Estructura**:
```sql
CREATE TABLE interesados (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    solicitud_id INT UNIQUE,           -- FK a solicitudes.id
    razon_social VARCHAR(255),         -- Nombre legal de la empresa
    nombre_fantasia VARCHAR(255),      -- Nombre comercial
    raw_data_id BIGINT,                -- FK a raw_api_data.id
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Ejemplo de datos**:
```
solicitud_id: 2756
razon_social: "Grenergy Renovables Pacific Limitada"
nombre_fantasia: "Grenergy"
```

**Importante**:
- Una `solicitud_id` puede aparecer **MÚLTIPLES veces** en esta tabla (una por cada empresa interesada)
- La tabla `solicitudes` tiene `rut_empresa` y `razon_social` que es la **empresa PRINCIPAL** solicitante
- La tabla `interesados` lista **TODAS** las empresas relacionadas (incluida la principal)

**Cuándo se llena**: Al ejecutar el endpoint `/interesados` (sistema anterior).

**Relaciones**:
- `interesados.solicitud_id` → `solicitudes.id` (muchos a uno)

---

### 4. `documentos` 📄

**Propósito**: Metadata de TODOS los documentos adjuntos a cada solicitud (PDFs, Excel, etc.).

**Fuente de datos**:
- **Endpoint API**: `?tipo=11&anio=null&tipo_solicitud_id=null&solicitud_id={id}`
- Para cada `solicitud_id`, extrae todos sus documentos

**Estructura**:
```sql
CREATE TABLE documentos (
    id BIGINT PRIMARY KEY,              -- documento_id de la API
    solicitud_id BIGINT NOT NULL,       -- FK a solicitudes.id
    nombre VARCHAR(500),                -- Nombre del archivo
    ruta_s3 TEXT,                       -- Ruta en AWS S3 para descargarlo
    tipo_documento_id INT,              -- ID del tipo de documento
    tipo_documento VARCHAR(100),        -- Nombre del tipo (ej: "Formulario SUCTD")
    empresa_id VARCHAR(20),             -- RUT de la empresa
    razon_social VARCHAR(255),
    create_date TIMESTAMP,              -- Cuándo se creó el documento
    etapa VARCHAR(100),                 -- En qué etapa del proceso se subió
    version_id VARCHAR(100),            -- Versión del documento en S3
    visible TINYINT(1),                 -- Si está visible públicamente
    deleted TINYINT(1),                 -- Si fue eliminado

    -- Metadata de descarga local
    downloaded TINYINT(1) DEFAULT 0,    -- Si ya fue descargado localmente
    downloaded_at TIMESTAMP,            -- Cuándo se descargó
    local_path VARCHAR(500),            -- Ruta local del archivo descargado

    fetched_at TIMESTAMP                -- Cuándo se extrajo la metadata
);
```

**Tipos de documentos comunes**:
- **Formulario SUCTD** (tipo_documento_id = 44): Formulario técnico para transporte dedicado
- **Formulario SAC**: Formulario de acceso y conexión
- **Formulario_proyecto_fehaciente**: Documento fehaciente del proyecto
- Carta gantt
- Garantía
- Otros documentos
- Diagrama unilineal
- Planos de ubicación

**Ejemplo de registro**:
```
id: 58958
solicitud_id: 2756
nombre: "PMG_Taruca_Formulario_de_solicitud_y_antecedentes_SUCTD.pdf"
ruta_s3: "empresa-1/proyecto-2830/solicitud-2756/Formulario_SUCTD/76.257.813-1/15-9-2025 17:22:40_PMG_Taruca_Formulario_de_solicitud_y_antecedentes_SUCTD.pdf"
tipo_documento: "Formulario SUCTD"
empresa_id: "76.257.813-1"
downloaded: 0
```

**Cuándo se llena**: Después de extraer las solicitudes, se itera por cada `solicitud_id`.

**Relaciones**:
- `documentos.solicitud_id` → `solicitudes.id` (muchos a uno)

---

## Vistas

### 1. `successful_fetches` ✅

**Propósito**: Filtrar solo las extracciones exitosas de `raw_api_data`.

```sql
CREATE VIEW successful_fetches AS
SELECT * FROM raw_api_data
WHERE status_code BETWEEN 200 AND 299;
```

---

### 2. `latest_fetches` 🕐

**Propósito**: Obtener la extracción más reciente de cada URL.

```sql
CREATE VIEW latest_fetches AS
SELECT source_url, MAX(fetched_at) as last_fetch
FROM raw_api_data
GROUP BY source_url;
```

---

### 3. `documentos_importantes` ⭐

**Propósito**: Filtrar SOLO los documentos que nos interesan (SUCTD, SAC, Formulario_proyecto_fehaciente).

**¿Por qué existe?**: De los ~10-20 documentos que puede tener una solicitud, solo nos interesan 3 tipos para análisis posterior.

```sql
CREATE VIEW documentos_importantes AS
SELECT
    d.*,
    s.proyecto,
    s.tipo_solicitud,
    s.region,
    s.comuna
FROM documentos d
INNER JOIN solicitudes s ON d.solicitud_id = s.id
WHERE d.tipo_documento IN ('Formulario SUCTD', 'Formulario SAC', 'Formulario_proyecto_fehaciente')
    AND d.deleted = 0
    AND d.visible = 1;
```

**Documentos importantes**:
1. **Formulario SUCTD**: Contiene información técnica detallada del proyecto de transporte
2. **Formulario SAC**: Contiene información de acceso y conexión
3. **Formulario_proyecto_fehaciente**: Antecedentes fehacientes del proyecto

**Otros documentos** (excluidos de esta vista):
- Carta gantt
- Garantías
- Otros documentos genéricos
- Planos
- Cartas conductoras

---

### 4. `solicitudes_con_documentos` 📊

**Propósito**: Ver cuántos documentos importantes tiene cada solicitud.

```sql
CREATE VIEW solicitudes_con_documentos AS
SELECT
    s.*,
    COUNT(d.id) AS total_documentos,
    SUM(CASE WHEN d.tipo_documento = 'Formulario SUCTD' THEN 1 ELSE 0 END) AS tiene_suctd,
    SUM(CASE WHEN d.tipo_documento = 'Formulario SAC' THEN 1 ELSE 0 END) AS tiene_sac,
    SUM(CASE WHEN d.tipo_documento = 'Formulario_proyecto_fehaciente' THEN 1 ELSE 0 END) AS tiene_fehaciente
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
    AND d.tipo_documento IN ('Formulario SUCTD', 'Formulario SAC', 'Formulario_proyecto_fehaciente')
    AND d.deleted = 0
    AND d.visible = 1
GROUP BY s.id;
```

**Uso**: Identificar solicitudes que NO tienen documentos importantes para re-extraer.

---

### 5. `estadisticas_extraccion` 📈

**Propósito**: Dashboard rápido del estado del sistema.

```sql
CREATE VIEW estadisticas_extraccion AS
SELECT 'Solicitudes totales' AS metrica, COUNT(*) AS valor FROM solicitudes
UNION ALL
SELECT 'Documentos totales', COUNT(*) FROM documentos
UNION ALL
SELECT 'Documentos SUCTD', COUNT(*) FROM documentos WHERE tipo_documento = 'Formulario SUCTD' AND deleted = 0
UNION ALL
SELECT 'Documentos SAC', COUNT(*) FROM documentos WHERE tipo_documento = 'Formulario SAC' AND deleted = 0
UNION ALL
SELECT 'Documentos Fehaciente', COUNT(*) FROM documentos WHERE tipo_documento = 'Formulario_proyecto_fehaciente' AND deleted = 0
UNION ALL
SELECT 'Documentos descargados', COUNT(*) FROM documentos WHERE downloaded = 1;
```

**Salida ejemplo**:
```
+---------------------------+-------+
| metrica                   | valor |
+---------------------------+-------+
| Solicitudes totales       | 2448  |
| Documentos totales        | 15234 |
| Documentos SUCTD          | 456   |
| Documentos SAC            | 1234  |
| Documentos Fehaciente     | 234   |
| Documentos descargados    | 0     |
+---------------------------+-------+
```

---

## Relaciones entre Tablas

```
┌─────────────────┐
│  raw_api_data   │ (Datos crudos de TODOS los endpoints)
└─────────────────┘
        │
        │ (se parsea)
        ↓
┌─────────────────┐         ┌─────────────────┐
│  solicitudes    │←────────│  interesados    │
│  (proyectos)    │  1:N    │  (stakeholders) │
└─────────────────┘         └─────────────────┘
        │
        │ 1:N
        ↓
┌─────────────────┐
│   documentos    │ (Todos los documentos)
└─────────────────┘
        │
        │ (filtro)
        ↓
┌─────────────────┐
│  documentos_    │ (Vista: solo SUCTD, SAC, Fehaciente)
│  importantes    │
└─────────────────┘
```

### Relaciones Detalladas

1. **`raw_api_data` → `interesados`**
   - `interesados.raw_data_id` → `raw_api_data.id`
   - Los datos de `interesados` se extraen parseando el JSON de `raw_api_data`

2. **`solicitudes` ← `interesados`**
   - `interesados.solicitud_id` → `solicitudes.id`
   - Relación **1:N** (una solicitud puede tener múltiples empresas interesadas)

3. **`solicitudes` ← `documentos`**
   - `documentos.solicitud_id` → `solicitudes.id`
   - Relación **1:N** (una solicitud puede tener múltiples documentos)
   - Con **FOREIGN KEY CASCADE**: si se borra una solicitud, se borran sus documentos

---

## Orden de Llenado

### Orden de Extracción y Llenado de Tablas

```
PASO 1: Extracción de datos crudos
│
├─→ raw_api_data (se llena SIEMPRE en cada llamada a la API)
│
PASO 2: Extracción de interesados
│
├─→ interesados (endpoint /interesados)
│
PASO 3: Extracción de solicitudes
│
├─→ solicitudes (endpoint tipo=6, por cada año)
│
PASO 4: Extracción de documentos
│
└─→ documentos (endpoint tipo=11, por cada solicitud_id)
```

### Script Único: `src/main.py` - Orquestador de Extractores

**Base URL**: `https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public`

**Qué hace**:
El orquestador ejecuta SIEMPRE ambos extractores:

1. **Extractor de Interesados**:
   - Extrae datos del endpoint `/interesados` (usando `CEN_API_BASE_URL + "/interesados"`)
   - Guarda respuesta cruda en `raw_api_data`
   - Parsea y normaliza datos en `interesados`

2. **Extractor de Solicitudes y Documentos**:
   - Extrae solicitudes por año usando parámetro `tipo=6` (años configurados en `CEN_YEARS`)
   - Guarda solicitudes en tabla `solicitudes`
   - Para cada solicitud, extrae documentos usando parámetro `tipo=11`
   - Filtra solo documentos importantes (SUCTD, SAC, Formulario_proyecto_fehaciente)
   - Guarda documentos en tabla `documentos`
   - **TODAS las respuestas API se guardan en `raw_api_data` como audit trail**

**Comando**:
```bash
# Configurar en .env:
# CEN_API_BASE_URL=https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public
# CEN_YEARS=2024,2025
# CEN_DOCUMENT_TYPES=Formulario SUCTD,Formulario SAC,Formulario_proyecto_fehaciente

# Ejecuta extracción completa (interesados + solicitudes + documentos):
uv run python -m src.main

# O con Docker:
docker-compose run --rm cen_app
```

---

## Arquitectura Unificada

**Ambos scripts son parte del mismo sistema CEN y usan la misma API base:**

```
CEN API: https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public
│
├─→ Endpoint /interesados                  → main.py      → tabla interesados
│
└─→ Endpoints parametrizados (tipo=0-11)   → main_cen.py  → tablas solicitudes + documentos
    ├─ tipo=6  (solicitudes por año)
    └─ tipo=11 (documentos por solicitud_id)

Audit Trail Compartido:
└─→ raw_api_data (TODOS los scripts guardan aquí sus respuestas API)
```

---

## Resumen de Fuentes de Datos

| Tabla | Endpoint API | Parámetros | Descripción |
|-------|--------------|------------|-------------|
| `raw_api_data` | Cualquiera | - | Caché de todas las respuestas |
| `interesados` | `/interesados` | - | Empresas stakeholders |
| `solicitudes` | `?tipo=6` | `anio=2025` | Proyectos de conexión eléctrica |
| `documentos` | `?tipo=11` | `solicitud_id=2756` | Documentos adjuntos a solicitudes |

---

## Queries Útiles

### Ver solicitudes sin documentos importantes

```sql
SELECT s.id, s.proyecto, s.razon_social
FROM solicitudes s
LEFT JOIN documentos d ON s.id = d.solicitud_id
    AND d.tipo_documento IN ('Formulario SUCTD', 'Formulario SAC', 'Formulario_proyecto_fehaciente')
WHERE d.id IS NULL;
```

### Ver empresas interesadas en un proyecto

```sql
SELECT s.proyecto, i.razon_social, i.nombre_fantasia
FROM solicitudes s
INNER JOIN interesados i ON s.id = i.solicitud_id
WHERE s.id = 2756;
```

### Contar documentos por tipo

```sql
SELECT tipo_documento, COUNT(*) as total
FROM documentos
WHERE deleted = 0
GROUP BY tipo_documento
ORDER BY total DESC;
```

---

**Fin de la documentación**
