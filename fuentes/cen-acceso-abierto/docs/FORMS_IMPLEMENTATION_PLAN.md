# Plan de Implementación - Parseo de Formularios CEN

## Resumen Ejecutivo

Este documento describe la implementación completa del sistema de descarga, parseo y almacenamiento de formularios del CEN (Coordinador Eléctrico Nacional).

**Objetivo**: Extraer datos estructurados de los formularios SAC, SUCTD y Proyecto Fehaciente (Excel y PDF) y almacenarlos en base de datos para análisis.

**Fuente de formularios**: https://www.coordinador.cl/desarrollo/documentos/acceso-abierto/aplicacion-del-regimen-de-acceso-abierto/formularios/

---

## 1. Tipos de Formularios

### 1.1 Formulario SUCTD
**Sistema de Uso de Capacidad Técnica de Distribución**

**Estructura**:
- Hoja 1: `FORMULARIO SUCTD` (datos del proyecto)
- Hoja 2: `FORM. VERIFICACIÓN` (checklist documentos)
- Hoja 3: `Oculto` (catálogos de validación)

**Campos clave**:
- Empresa solicitante (RUT, Razón Social, Representante Legal)
- Coordinadores de proyecto (2)
- Proyecto (Nombre, Tipo, Tecnología, Potencia neta inyección [MW])
- Ubicación (Región, Comuna, Coordenadas)
- Conexión (Tipo, Punto de conexión, Tensión)

**Documentos requeridos** (según checklist):
- Formulario SUCTD
- Informe descriptivo solución de conexión
- Planos (Diagrama Unilineal, DEE Planta, DEE Cortes)
- Instalaciones a modificar
- Carta Gantt
- Declaración jurada
- Garantía
- Informe determinación monto caución

### 1.2 Formulario SAC
**Sistema de Acceso y Conexión**

**Estructura**: Idéntica a SUCTD

**Diferencias clave**:
- Más enfocado en generación eléctrica
- Incluye datos de sistema de almacenamiento (si aplica)
- Verificación de completitud más simple

**Documentos requeridos**:
- Similar a SUCTD
- Sin "Informe determinación monto caución"

### 1.3 Formulario Proyecto Fehaciente
**Proyecto con viabilidad económica demostrable**

**Estructura**: Similar pero más simple

**Campos específicos**:
- Menos detalles técnicos de conexión
- Más enfoque en viabilidad del proyecto

**Documentos requeridos**:
- Formulario Proyecto Fehaciente
- Informe de vínculos societarios
- Informe descriptivo de proyecto
- Carta Gantt
- Antecedentes tramitación ambiental

---

## 2. Arquitectura Propuesta

### 2.1 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────┐
│ PASO 1: DESCARGA                                                │
│                                                                 │
│ documentos (tabla existente)                                    │
│   ├── id, solicitud_id, nombre, ruta_s3, tipo_documento       │
│   └── local_path (NULL inicialmente)                          │
│                                                                 │
│ ↓ Descargar documentos importantes desde ruta_s3              │
│                                                                 │
│ documentos.local_path = "downloads/{solicitud_id}/{filename}"  │
│ documentos.downloaded = 1                                       │
│ documentos.downloaded_at = NOW()                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ PASO 2: DETECCIÓN DE FORMATO                                    │
│                                                                 │
│ Para cada documento descargado:                                 │
│   - Si extensión == .xlsx → Parser Excel                       │
│   - Si extensión == .pdf  → Parser PDF (OCR si necesario)     │
│   - Guardar resultado en: formularios_parseados               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ PASO 3: PARSEO                                                   │
│                                                                 │
│ Parser detecta tipo de formulario:                             │
│   - SUCTD  → Extrae campos específicos SUCTD                  │
│   - SAC    → Extrae campos específicos SAC                    │
│   - FEH    → Extrae campos específicos Proyecto Fehaciente    │
│                                                                 │
│ Extrae datos a tablas normalizadas:                            │
│   ├── formularios_suctd                                        │
│   ├── formularios_sac                                          │
│   └── formularios_fehacientes                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Componentes del Sistema

```
src/
├── downloaders/
│   ├── __init__.py
│   └── documents.py          # Descarga de documentos desde S3/URLs
│
├── parsers/
│   ├── __init__.py
│   ├── excel_parser.py       # Parser genérico para Excel
│   ├── pdf_parser.py         # Parser genérico para PDF
│   ├── form_suctd.py         # Parser específico SUCTD
│   ├── form_sac.py           # Parser específico SAC
│   └── form_fehaciente.py    # Parser específico Proyecto Fehaciente
│
├── repositories/
│   ├── forms.py              # Operaciones BD para formularios
│   └── downloads.py          # Operaciones BD para descargas
│
└── extractors/
    └── forms.py              # Orquestador descarga + parseo
```

---

## 3. Modelo de Base de Datos

### 3.1 Tabla: `formularios_parseados`
**Registro de cada intento de parseo**

```sql
CREATE TABLE formularios_parseados (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Relación con documento original
    documento_id BIGINT NOT NULL,
    solicitud_id INT NOT NULL,

    -- Tipo de formulario detectado
    tipo_formulario ENUM('SUCTD', 'SAC', 'FEHACIENTE', 'DESCONOCIDO') NOT NULL,

    -- Formato del archivo
    formato ENUM('XLSX', 'PDF', 'OTRO') NOT NULL,

    -- Estado del parseo
    parseado BOOLEAN DEFAULT FALSE,
    parse_exitoso BOOLEAN DEFAULT NULL,
    parse_error TEXT DEFAULT NULL,

    -- Datos raw extraídos (JSON)
    datos_raw JSON DEFAULT NULL,

    -- Metadatos
    parseado_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices
    INDEX idx_documento_id (documento_id),
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_tipo_formulario (tipo_formulario),
    INDEX idx_parse_exitoso (parse_exitoso),

    -- Foreign keys
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3.2 Tabla: `formularios_suctd`
**Datos normalizados de formularios SUCTD**

```sql
CREATE TABLE formularios_suctd (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Relación
    formulario_parseado_id BIGINT NOT NULL UNIQUE,
    solicitud_id INT NOT NULL,

    -- Antecedentes Empresa
    razon_social VARCHAR(255),
    rut VARCHAR(20),
    domicilio_legal TEXT,
    representante_legal VARCHAR(255),
    email_representante VARCHAR(255),
    telefono_representante VARCHAR(50),

    -- Coordinadores
    coordinador1_nombre VARCHAR(255),
    coordinador1_email VARCHAR(255),
    coordinador1_telefono VARCHAR(50),
    coordinador2_nombre VARCHAR(255),
    coordinador2_email VARCHAR(255),
    coordinador2_telefono VARCHAR(50),

    -- Antecedentes Proyecto
    nombre_proyecto VARCHAR(255),
    tipo_proyecto VARCHAR(100),
    tipo_tecnologia VARCHAR(100),
    potencia_neta_inyeccion DECIMAL(10,3),  -- MW

    -- Ubicación
    region VARCHAR(100),
    comuna VARCHAR(100),
    coordenada_norte VARCHAR(50),
    coordenada_este VARCHAR(50),

    -- Conexión
    tipo_conexion VARCHAR(100),
    punto_conexion VARCHAR(255),
    tension_conexion DECIMAL(10,3),  -- kV

    -- Metadatos
    version_formulario VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_rut (rut),
    INDEX idx_tipo_proyecto (tipo_proyecto),
    INDEX idx_tipo_tecnologia (tipo_tecnologia),

    -- Foreign keys
    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3.3 Tabla: `formularios_sac`
**Datos normalizados de formularios SAC**

```sql
CREATE TABLE formularios_sac (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Relación
    formulario_parseado_id BIGINT NOT NULL UNIQUE,
    solicitud_id INT NOT NULL,

    -- Antecedentes Empresa (igual que SUCTD)
    razon_social VARCHAR(255),
    rut VARCHAR(20),
    domicilio_legal TEXT,
    representante_legal VARCHAR(255),
    email_representante VARCHAR(255),
    telefono_representante VARCHAR(50),

    -- Coordinadores
    coordinador1_nombre VARCHAR(255),
    coordinador1_email VARCHAR(255),
    coordinador1_telefono VARCHAR(50),
    coordinador2_nombre VARCHAR(255),
    coordinador2_email VARCHAR(255),
    coordinador2_telefono VARCHAR(50),

    -- Antecedentes Proyecto
    nombre_proyecto VARCHAR(255),
    tipo_proyecto VARCHAR(100),
    tipo_tecnologia VARCHAR(100),
    potencia_neta_inyeccion DECIMAL(10,3),  -- MW

    -- Específico SAC: Sistema de Almacenamiento
    tiene_almacenamiento BOOLEAN DEFAULT FALSE,
    potencia_almacenamiento DECIMAL(10,3),  -- MW
    capacidad_almacenamiento DECIMAL(10,3),  -- MWh

    -- Ubicación
    region VARCHAR(100),
    comuna VARCHAR(100),
    coordenada_norte VARCHAR(50),
    coordenada_este VARCHAR(50),

    -- Conexión
    tipo_conexion VARCHAR(100),
    punto_conexion VARCHAR(255),
    tension_conexion DECIMAL(10,3),  -- kV

    -- Metadatos
    version_formulario VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_rut (rut),
    INDEX idx_tipo_proyecto (tipo_proyecto),
    INDEX idx_tipo_tecnologia (tipo_tecnologia),

    -- Foreign keys
    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3.4 Tabla: `formularios_fehacientes`
**Datos normalizados de formularios Proyecto Fehaciente**

```sql
CREATE TABLE formularios_fehacientes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Relación
    formulario_parseado_id BIGINT NOT NULL UNIQUE,
    solicitud_id INT NOT NULL,

    -- Antecedentes Empresa
    razon_social VARCHAR(255),
    rut VARCHAR(20),
    domicilio_legal TEXT,
    representante_legal VARCHAR(255),
    email_representante VARCHAR(255),
    telefono_representante VARCHAR(50),

    -- Coordinadores
    coordinador1_nombre VARCHAR(255),
    coordinador1_email VARCHAR(255),
    coordinador1_telefono VARCHAR(50),
    coordinador2_nombre VARCHAR(255),
    coordinador2_email VARCHAR(255),
    coordinador2_telefono VARCHAR(50),

    -- Antecedentes Proyecto
    nombre_proyecto VARCHAR(255),
    tipo_proyecto VARCHAR(100),
    tipo_tecnologia VARCHAR(100),
    potencia_neta_inyeccion DECIMAL(10,3),  -- MW

    -- Ubicación
    region VARCHAR(100),
    comuna VARCHAR(100),

    -- Específico Fehaciente
    fecha_puesta_servicio DATE,
    inversion_estimada DECIMAL(15,2),  -- USD o CLP (especificar)

    -- Metadatos
    version_formulario VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices
    INDEX idx_solicitud_id (solicitud_id),
    INDEX idx_rut (rut),
    INDEX idx_tipo_proyecto (tipo_proyecto),
    INDEX idx_tipo_tecnologia (tipo_tecnologia),

    -- Foreign keys
    FOREIGN KEY (formulario_parseado_id) REFERENCES formularios_parseados(id) ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3.5 Actualización Tabla Existente: `documentos`
**Agregar campos para tracking de descarga**

```sql
ALTER TABLE documentos
ADD COLUMN downloaded BOOLEAN DEFAULT FALSE AFTER fetched_at,
ADD COLUMN downloaded_at TIMESTAMP NULL AFTER downloaded,
ADD COLUMN local_path VARCHAR(512) NULL AFTER downloaded_at,
ADD COLUMN download_error TEXT NULL AFTER local_path,
ADD INDEX idx_downloaded (downloaded),
ADD INDEX idx_downloaded_at (downloaded_at);
```

---

## 4. Plan de Implementación por Fases

### FASE 1: Descarga de Documentos ✅
**Objetivo**: Descargar formularios desde S3/URLs a almacenamiento local

**Tareas**:
1. ✅ Crear `src/downloaders/documents.py`
2. ✅ Implementar lógica de descarga desde `ruta_s3`
3. ✅ Actualizar tabla `documentos` con campos de tracking
4. ✅ Guardar archivos en `downloads/{solicitud_id}/{filename}`
5. ✅ Marcar documentos como `downloaded = TRUE`

**Entregables**:
- [ ] Downloader funcional
- [ ] Documentos almacenados localmente
- [ ] Logs de descarga
- [ ] Tests unitarios

**Tiempo estimado**: 2-3 días

---

### FASE 2: Parser de Excel (XLSX) ✅
**Objetivo**: Extraer datos de formularios en formato Excel

**Tareas**:
1. ✅ Crear `src/parsers/excel_parser.py` (genérico)
2. ✅ Crear `src/parsers/form_suctd.py` (específico)
3. ✅ Crear `src/parsers/form_sac.py` (específico)
4. ✅ Crear `src/parsers/form_fehaciente.py` (específico)
5. ✅ Implementar detección automática de tipo de formulario
6. ✅ Extraer campos comunes (empresa, coordinadores, proyecto)
7. ✅ Extraer campos específicos de cada tipo

**Entregables**:
- [ ] Parser XLSX funcional
- [ ] Detección automática de tipo
- [ ] Datos extraídos en JSON
- [ ] Tests con formularios reales

**Tiempo estimado**: 4-5 días

---

### FASE 3: Parser de PDF ⏸️
**Objetivo**: Extraer datos de formularios en formato PDF

**Tareas**:
1. ⏸️ Crear `src/parsers/pdf_parser.py`
2. ⏸️ Implementar extracción de texto con PyPDF
3. ⏸️ Implementar OCR con Tesseract (si es necesario)
4. ⏸️ Mapear texto extraído a campos estructurados
5. ⏸️ Manejar PDFs escaneados vs. PDFs nativos

**Entregables**:
- [ ] Parser PDF funcional
- [ ] Soporte para PDFs nativos y escaneados
- [ ] Extracción de campos clave
- [ ] Tests con PDFs reales

**Tiempo estimado**: 5-7 días

**Nota**: Esta fase puede postergarse si la mayoría de documentos son XLSX.

---

### FASE 4: Base de Datos y Almacenamiento ✅
**Objetivo**: Guardar datos parseados en tablas normalizadas

**Tareas**:
1. ✅ Crear tablas SQL (formularios_parseados, etc.)
2. ✅ Crear `src/repositories/forms.py`
3. ✅ Implementar inserts con estrategia append-only
4. ✅ Crear vistas de analytics
5. ✅ Documentar esquema de datos

**Entregables**:
- [ ] Tablas creadas
- [ ] Repository funcional
- [ ] Datos guardados correctamente
- [ ] Vistas de análisis

**Tiempo estimado**: 2-3 días

---

### FASE 5: Integración y Orquestación ✅
**Objetivo**: Integrar descarga + parseo en flujo unificado

**Tareas**:
1. ✅ Crear `src/extractors/forms.py`
2. ✅ Implementar flujo completo:
   - Descargar documentos importantes
   - Detectar formato (XLSX/PDF)
   - Parsear según tipo de formulario
   - Guardar en BD
3. ✅ Actualizar `src/main.py` con nuevo extractor
4. ✅ Agregar logging detallado
5. ✅ Agregar manejo de errores robusto

**Entregables**:
- [ ] Flujo end-to-end funcional
- [ ] Integrado en orquestador principal
- [ ] Documentación completa
- [ ] Tests de integración

**Tiempo estimado**: 3-4 días

---

## 5. Consideraciones Técnicas

### 5.1 Manejo de Errores

**Estrategia de reintentos**:
- Descargas fallidas: 3 intentos con backoff exponencial
- Parseo fallido: Guardar en `formularios_parseados` con `parse_exitoso = FALSE`
- No bloquear pipeline si un formulario falla

**Logging**:
- Log nivel INFO: Progreso general
- Log nivel WARNING: Campos faltantes pero formulario válido
- Log nivel ERROR: Fallo crítico en descarga/parseo

### 5.2 Validación de Datos

**Campos obligatorios**:
- RUT (validar formato chileno)
- Nombre proyecto
- Tipo de proyecto
- Tipo de tecnología

**Campos opcionales**:
- Coordinadores (puede haber 0, 1 o 2)
- Ubicación geográfica
- Datos de conexión

### 5.3 Performance

**Optimizaciones**:
- Descargas en paralelo (ThreadPoolExecutor, max 5 workers)
- Batch inserts en BD (grupos de 100 registros)
- Cache de formularios ya parseados

**Límites**:
- Timeout descarga: 60 segundos
- Tamaño máximo archivo: 50 MB
- Memoria máxima por parseo: 500 MB

### 5.4 Seguridad

**Validación de archivos**:
- Verificar extensión antes de parsear
- Sanitizar nombres de archivo
- Validar que archivos XLSX son válidos (no corrompidos)

**Almacenamiento**:
- Archivos descargados en `downloads/` (fuera de git)
- Permisos restrictivos (chmod 600)
- No almacenar credenciales en formularios parseados

---

## 6. Métricas de Éxito

**KPIs**:
- % de documentos descargados exitosamente (> 95%)
- % de formularios parseados exitosamente (> 85%)
- Tiempo promedio de descarga + parseo (< 30 seg por documento)
- Campos extraídos por formulario (> 15 campos en promedio)

**Reportes**:
```sql
-- Vista de estadísticas de parseo
CREATE VIEW estadisticas_parseo AS
SELECT
    tipo_formulario,
    formato,
    COUNT(*) as total,
    SUM(CASE WHEN parse_exitoso THEN 1 ELSE 0 END) as exitosos,
    ROUND(100.0 * SUM(CASE WHEN parse_exitoso THEN 1 ELSE 0 END) / COUNT(*), 2) as tasa_exito
FROM formularios_parseados
GROUP BY tipo_formulario, formato;
```

---

## 7. Próximos Pasos

### Prioridad Alta
1. [ ] Implementar FASE 1 (Descarga)
2. [ ] Implementar FASE 2 (Parser XLSX)
3. [ ] Crear tablas de BD
4. [ ] Integrar en flujo principal

### Prioridad Media
5. [ ] Parser PDF (FASE 3)
6. [ ] Dashboard de métricas
7. [ ] Alertas de fallos

### Prioridad Baja
8. [ ] OCR para PDFs escaneados
9. [ ] API REST para consultar datos parseados
10. [ ] Export a CSV/Excel

---

**Última actualización**: 2025-10-20
**Autor**: Equipo Antumanque / Claude
**Versión**: 1.0.0
