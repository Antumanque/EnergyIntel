# Análisis de Arquitectura: CEN Acceso Abierto

**Fecha**: Octubre 2025
**Propósito**: Documentación completa del sistema de ingesta de datos del Coordinador Eléctrico Nacional

---

## 1. VISIÓN GENERAL

**Proyecto**: CEN Acceso Abierto Data Dumper - Sistema de ingesta de datos reutilizable basado en Python para el Coordinador Eléctrico Nacional de Chile (CEN).

**Propósito**: Extrae, parsea y almacena datos de conexiones de la red eléctrica chilena incluyendo:
- Solicitudes de conexión (solicitudes) para proyectos energéticos
- Documentación de proyectos (formularios) en formatos PDF y XLSX
- Información de stakeholders (interesados) para proyectos energéticos

**Filosofía Clave**:
- Arquitectura limpia en capas con separación de responsabilidades
- Estrategia append-only (nunca actualiza/borra, preserva auditoría completa)
- Contenedorizado con Docker para portabilidad
- Configuración basada en variables de entorno para múltiples despliegues

---

## 2. PIPELINE COMPLETO (8 PASOS)

El orquestador `main.py` ejecuta un pipeline de extracción y procesamiento de 8 pasos:

```
PASO 1: Extract Interesados (stakeholders)
        ↓ [Llamadas API a /interesados endpoint]
        → Guardar en: raw_api_data + interesados tables

PASO 2: Extract Solicitudes (proyectos) + metadatos de documentos
        ↓ [Llamadas API a tipo=6 (por año) + tipo=11 (por solicitud_id)]
        → Guardar en: raw_api_data + solicitudes + documentos tables

PASO 3: Batch download SAC formularios
        ↓ [Descargar PDF/XLSX desde S3 usando URLs prefirmadas]
        → Guardar archivos en: downloads/ + update documentos table

PASO 4: Batch parse SAC formularios
        ↓ [Extraer datos estructurados de PDF/XLSX]
        → Guardar datos parseados en: formularios_sac_parsed table

PASO 5: Batch download SUCTD formularios
        ↓ [Descargar PDF/XLSX desde S3]
        → Guardar archivos en: downloads/

PASO 6: Batch parse SUCTD formularios
        ↓ [Extraer datos estructurados]
        → Guardar en: formularios_suctd_parsed table

PASO 7: Batch download Fehaciente formularios
        ↓ [Descargar PDF/XLSX]

PASO 8: Batch parse Fehaciente formularios
        ↓ [Extraer datos estructurados]
        → Guardar en: formularios_fehaciente_parsed table
```

---

## 3. FUENTES DE DATOS

**Fuente Primaria**: CEN Acceso Abierto Public API
- **Base URL**: `https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public`

**Endpoints Clave**:
- **`/interesados`**: Lista de stakeholders (empresas, desarrolladores de proyectos)
- **`tipo=6`**: Solicitudes de conexión (solicitudes) - lista principal de proyectos
- **`tipo=11`**: Documentos adjuntos a cada solicitud (metadatos + URLs S3)

**Tipos de Documentos Extraídos** (configurado en `.env`):
1. **Formulario SAC** - Solicitud de Autorización de Conexión
2. **Formulario SUCTD** - Solicitud de Uso de Capacidad Técnica Dedicada
3. **Formulario_proyecto_fehaciente** - Formularios de Proyecto Fehaciente

**Años Configurables**: Default 2025, puede extraer cualquier rango de años (ej. 2020-2025)

---

## 4. ESTRUCTURA DE DIRECTORIOS

```
fuentes/cen-acceso-abierto/
├── src/                                    # Código de aplicación Python
│   ├── main.py                            # Orquestador de 8 pasos (entry point)
│   ├── settings.py                        # Gestión de configuración (pydantic)
│   ├── http_client.py                     # Cliente HTTP con retries
│   ├── clean_all.py                       # Utilidad de limpieza de BD
│   │
│   ├── extractors/                        # Capa de extracción de datos
│   │   ├── interesados.py                 # Extraer stakeholders
│   │   └── solicitudes.py                 # Extraer proyectos y documentos
│   │
│   ├── parsers/                           # Capa de transformación de datos
│   │   ├── interesados.py                 # Transformar JSON de stakeholders
│   │   ├── solicitudes.py                 # Transformar JSON de proyectos
│   │   ├── pdf_sac.py        (388 lines)  # Parsear PDFs SAC
│   │   ├── pdf_suctd.py      (447 lines)  # Parsear PDFs SUCTD
│   │   ├── pdf_fehaciente.py (447 lines)  # Parsear PDFs Fehaciente
│   │   ├── xlsx_sac.py       (540 lines)  # Parsear XLSX SAC
│   │   ├── xlsx_suctd.py     (522 lines)  # Parsear XLSX SUCTD
│   │   └── xlsx_fehaciente.py (522 lines) # Parsear XLSX Fehaciente
│   │
│   ├── repositories/                      # Capa de acceso a base de datos
│   │   ├── base.py                        # Gestor genérico de BD para raw_api_data
│   │   └── cen.py                         # Gestor de tablas específicas de CEN
│   │
│   ├── downloaders/
│   │   └── documents.py                   # Descargar archivos desde S3
│   │
│   ├── batch_download_sac.py              # Descargador batch SAC
│   ├── batch_parse_sac.py                 # Parser batch SAC
│   ├── batch_download_suctd.py            # Descargador batch SUCTD
│   ├── batch_parse_suctd.py               # Parser batch SUCTD
│   ├── batch_download_fehaciente.py       # Descargador batch Fehaciente
│   ├── batch_parse_fehaciente.py          # Parser batch Fehaciente
│   │
│   └── __init__.py
│
├── db/                                    # Schemas de BD y setup
│   ├── init.sql                           # Schema inicial (raw_api_data, interesados)
│   ├── schema_solicitudes.sql             # Tablas y vistas de solicitudes + documentos
│   ├── schema_formularios_parsed.sql      # Tablas y vistas de formularios parseados
│   ├── migrations/                        # Migraciones de base de datos
│   │   ├── 001_add_download_error_column.sql
│   │   ├── 002_add_documentos_ultimas_versiones_view.sql
│   │   └── 003_add_pdf_metadata_columns.sql
│   ├── setup.py                           # Ejecutor de migraciones
│   ├── migrate.py                         # Gestión de migraciones
│   └── data/                              # Almacenamiento persistente MariaDB (gitignored)
│
├── downloads/                             # Archivos PDF/XLSX descargados (organizados por solicitud_id)
│   ├── 100/
│   ├── 1000/
│   └── ... (2000+ directorios con documentos)
│
├── docs/                                  # Documentación completa
│   ├── DATABASE_SCHEMA.md                 # Documentación completa del schema
│   ├── DATABASE_MIGRATIONS.md             # Estrategia de migraciones
│   ├── API_DOCUMENTATION.md               # Endpoints de la API CEN (tipos 0-11)
│   ├── PDF_PARSING_ANALYSIS.md            # Análisis de estructura de PDFs
│   ├── PARSING_ERROR_HANDLING.md          # Estrategia de manejo de errores
│   ├── FORMS_IMPLEMENTATION_PLAN.md       # Implementación de parseo de formularios
│   ├── DEPLOYMENT.md                      # Guía de despliegue en producción
│   └── development/
│       ├── DEV_ITERATION.md
│       └── NORMALIZATION.md               # Explicación de estrategia append-only
│
├── docker-compose.yml                     # Dev local: MariaDB + app Python
├── Dockerfile                             # Imagen de contenedor para producción
├── deploy.sh                              # Script de despliegue en producción
├── pyproject.toml                         # Dependencias Python (uv)
├── CLAUDE.md                              # Guía de desarrollo con Claude Code
├── README.md                              # Guía de inicio
└── Notas.md                               # Notas de desarrollo
```

---

## 5. ESTRUCTURA DE BASE DE DATOS

**Nombre de BD**: `cen_acceso_abierto` (MariaDB 10.11)

**Tablas Core**:

| Tabla | Propósito | Registros | Campos Clave |
|-------|-----------|-----------|--------------|
| **raw_api_data** | Auditoría de todas las llamadas API | ~2,000+ | source_url, status_code, data (JSON), error_message, fetched_at |
| **interesados** | Stakeholders/empresas por proyecto | ~5,000+ | solicitud_id, razon_social, nombre_fantasia |
| **solicitudes** | Proyectos energéticos (SAC, SUCTD, Fehaciente) | ~2,400+ | id (PK), proyecto, tipo_solicitud, rut_empresa, potencia_nominal, region, comuna, estado, fecha_estimada_conexion |
| **documentos** | Archivos PDF/XLSX adjuntos a solicitudes | ~2,200+ | id (PK), solicitud_id (FK), nombre, ruta_s3, tipo_documento, downloaded, local_path |
| **formularios_parseados** | Tracking de parseo | ~500+ | documento_id (FK), tipo_formulario, parsing_exitoso, pdf_metadata |
| **formularios_sac_parsed** | Datos extraídos de formularios SAC | ~400+ | razon_social, rut, giro, nombre_proyecto, tecnologia, potencia_nominal_mw, subestacion, nivel_tension, coordenadas |
| **formularios_suctd_parsed** | Datos extraídos de formularios SUCTD | ~150+ | razon_social, rut, nombre_proyecto, tipo_tecnologia, potencia_inyeccion, potencia_retiro, se_conexion |
| **formularios_fehaciente_parsed** | Datos extraídos de formularios Fehaciente | ~50+ | Similar a SUCTD |

**Patrones de Diseño Clave**:

1. **Almacenamiento Append-Only**: Nunca UPDATE o DELETE de registros. Cada llamada API crea nueva fila en `raw_api_data`
2. **Foreign Keys & Cascades**: Mantiene integridad referencial
3. **Vistas para Análisis**: Vistas pre-computadas para consultas comunes
4. **Índices para Performance**: En columnas frecuentemente consultadas (solicitud_id, rut, proyecto, etc.)

**Vistas Importantes**:
- `successful_fetches` - Solo respuestas HTTP 2xx
- `latest_fetches` - Fetch más reciente por URL
- `documentos_importantes` - Documentos importantes filtrados
- `documentos_ultimas_versiones` - Deduplica múltiples uploads del mismo documento
- `documentos_listos_para_parsear` - Documentos descargados listos para parsear
- `estadisticas_extraccion` - Dashboard de estadísticas resumen

---

## 6. FLUJO DE DESCARGA Y PROCESAMIENTO

**Fase 1: Extracción de Datos API**
```
HTTPClient.fetch_url()
  ├─ Lógica de retry con backoff exponencial (2, 4, 8 segundos)
  ├─ Timeout configurable (default 30s)
  ├─ Parseo JSON con fallback a texto
  └─ Almacenar respuesta raw en tabla raw_api_data

InteresadosExtractor.run()
  ├─ Llamar endpoint /interesados
  ├─ Transformar JSON a registros normalizados
  └─ Insertar en tabla interesados (append-only)

SolicitudesExtractor.run()
  ├─ Iterar por años configurados
  ├─ Fetch solicitudes (tipo=6) por año
  ├─ Deduplicar por ID (mismos proyectos a través de todos los años)
  ├─ Por cada solicitud_id, fetch documentos (tipo=11)
  ├─ Filtrar tipos de documentos importantes (SAC, SUCTD, Fehaciente)
  └─ Insertar en tablas solicitudes + documentos
```

**Fase 2: Descarga Batch de Documentos**
```
SACBatchDownloader.run_batch_download()
  ├─ Consultar tabla documentos para archivos SAC NO descargados
  ├─ Extraer URL S3 del campo ruta_s3
  ├─ Descargar desde AWS S3 con URLs prefirmadas
  ├─ Guardar localmente: downloads/{solicitud_id}/{filename}
  ├─ Actualizar tabla documentos: downloaded=1, local_path, downloaded_at
  └─ Loggear errores en columna download_error
```

**Fase 3: Parseo de Documentos**
```
SACBatchParser.run_batch_parsing()
  ├─ Consultar vista documentos_listos_para_parsear
  ├─ Por cada PDF: SACPDFParser.parse()
  │   ├─ Abrir PDF con pdfplumber
  │   ├─ Extraer tablas del PDF
  │   ├─ Parsear cada fila buscando labels de campos conocidos
  │   └─ Retornar dict estructurado con 30+ campos
  │
  ├─ Por cada XLSX: SACXLSXParser.parse()
  │   ├─ Abrir Excel con openpyxl
  │   ├─ Leer desde filas estandarizadas
  │   └─ Extraer valores por posición de columna
  │
  └─ Insertar resultados en tabla formularios_sac_parsed
```

---

## 7. PATRONES Y CONVENCIONES CLAVE

**Capas de Arquitectura**:
```
main.py (Orquestador - sin lógica de negocio)
    ↓
extractors/ (Lógica de negocio de extracción)
    ↓
parsers/ (Transformación de datos - funciones puras)
    ↓
repositories/ (Capa de acceso a base de datos)
    ↓
MariaDB (Almacenamiento persistente)
```

**Convenciones de Nombres**:
- **Base de datos**: `snake_case` (raw_api_data, solicitud_id)
- **Archivos Python**: `snake_case` (http_client.py, batch_download_sac.py)
- **Clases Python**: `PascalCase` (APIClient, SACBatchDownloader)
- **Constantes**: `SCREAMING_SNAKE_CASE` (MAX_RETRIES)
- **Comentarios**: Español primario, inglés opcional para clarificación

**Estrategia de Manejo de Errores**:
- Errores por URL no detienen la ejecución (itera por todas las URLs)
- Errores de conexión a BD fallan rápido
- Todos los errores loggeados con niveles apropiados
- Operaciones batch trackean fallos separadamente

**Gestión de Configuración**:
- Toda configuración via variables de entorno o archivo `.env`
- Type-safe usando pydantic-settings
- Patrón Singleton para clase `Settings`
- Helpers: `get_settings()`, `get_api_client()`, `get_cen_db_manager()`

**Patrón de Flujo de Datos**:
```
JSON Raw → Parser → Dictionary → Repository → Database
  ↓                                              ↓
raw_api_data                            solicitudes/documentos
(auditoría completa)                   (normalizado e indexado)
```

---

## 8. TECNOLOGÍAS Y DEPENDENCIAS

**Stack Tecnológico**:
- **Lenguaje**: Python 3.12
- **Package Manager**: `uv` (gestor de paquetes Python rápido y moderno)
- **HTTP**: `httpx` (alternativa moderna a requests, con capacidad async)
- **Base de Datos**: MariaDB 10.11 con `mysql-connector-python`
- **Config**: `pydantic-settings` (env vars type-safe)
- **Parseo PDF**: `pdfplumber`, `PyMuPDF`, `pypdf`
- **Parseo Excel**: `openpyxl`
- **Contenedorización**: Docker + Docker Compose

**Dependencias Clave** (de `pyproject.toml`):
```
httpx>=0.28.1              # Cliente HTTP
mysql-connector-python>=9.4.0  # Driver de base de datos
openpyxl>=3.1.5            # Lectura de Excel
pdfplumber>=0.11.7         # Extracción de tablas PDF
pydantic-settings>=2.0     # Gestión de configuración
pymupdf>=1.26.5            # Manipulación PDF
pypdf>=6.1.2               # Lectura PDF
```

---

## 9. DESPLIEGUE Y OPERACIONES

**Desarrollo Local**:
```bash
docker-compose up -d cen_db           # Iniciar base de datos
python -m src.main                    # Ejecutar extracción (conecta a Docker DB)
```

**Producción Docker**:
```bash
docker build -t cen-acceso-abierto .
docker run --env-file .env cen-acceso-abierto
```

**Scheduling**:
```cron
0 * * * *  cd /path && docker-compose run --rm cen_app      # Cada hora
0 */6 * * * cd /path && docker-compose run --rm cen_app      # Cada 6 horas
0 2 * * *  cd /path && docker-compose run --rm cen_app       # Diario a las 2 AM
```

**Setup de Base de Datos**:
- `deploy.sh` auto-detecta instalación nueva vs. base de datos existente
- Ejecuta `db/init.sql` para nuevas bases de datos
- Ejecuta migraciones desde `db/migrations/` para bases de datos existentes
- Trackea estado de migraciones en tabla `schema_migrations`

---

## 10. ESTADO ACTUAL (Octubre 2025)

**Datos Ya Extraídos**:
- **Año 2025**: 2,448 solicitudes, 2,290 documentos (mayormente SAC)
- **Documentos por tipo**: 655 SUCTD, 1,635 SAC, 0 Fehaciente en 2025
- **Tiempo de extracción**: ~22 minutos para año 2025 (incluye 2,448 llamadas API)

**Archivos con Cambios Activos** (desde git status):
```
M  db/schema_formularios_parsed.sql
M  src/batch_download_sac.py
M  src/extractors/solicitudes.py
M  src/main.py
M  src/repositories/cen.py
?? src/batch_download_fehaciente.py      (nuevo)
?? src/batch_download_suctd.py            (nuevo)
?? src/batch_parse_fehaciente.py          (nuevo)
?? src/batch_parse_suctd.py               (nuevo)
?? src/clean_all.py                       (nuevo)
?? src/parsers/pdf_fehaciente.py          (nuevo)
?? src/parsers/pdf_suctd.py               (nuevo)
?? src/parsers/xlsx_fehaciente.py         (nuevo)
?? src/parsers/xlsx_suctd.py              (nuevo)
```

**Commits Recientes**:
1. `b08608e` - add .gitignore rule for .claude folder
2. `5f8098a` - refactor: better structure, simplified init.sql
3. `d213dc5` - feat: add drop_existing option to fresh_install
4. `05f9f35` - fix: consume cursor results to prevent unread result errors
5. `41828f5` - feat: add XLSX parsing, batch download/parse scripts

---

## RESUMEN: CÓMO TODO FUNCIONA JUNTO

```
┌─────────────────────────────────────────────────────────┐
│                    CEN API (Chile)                       │
│  https://pkb3ax2pkg.execute-api.us-east-2.amazonaws...  │
│                 (/interesados, tipo=6, tipo=11)          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    main.py Orchestrator      │
            │  (pipeline de 8 pasos)       │
            └──────────────────────────────┘
                    ↙   ↓   ↘
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │Extractors│ │Parsers   │ │Repositories  │
        │(API)     │ │(JSON→dict│ │(Database)    │
        └──────────┘ └──────────┘ └──────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    MariaDB (10.11)           │
            │   raw_api_data (auditoría)   │
            │   interesados (empresas)     │
            │   solicitudes (proyectos)    │
            │   documentos (archivos)      │
            │   formularios_*_parsed (data)│
            └──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
    Downloads/        Query Views        Para Análisis
    (PDF/XLSX)      (estadísticas)       (dashboards)
    (archivos locales)
```

---

## ARCHIVOS CLAVE PARA REFERENCIA

**Documentación**: `/home/chris/EnergyIntel/fuentes/cen-acceso-abierto/docs/`
- `DATABASE_SCHEMA.md` - Documentación completa de tablas
- `API_DOCUMENTATION.md` - Endpoints de la API CEN (tipos 0-11)
- `FORMS_IMPLEMENTATION_PLAN.md` - Detalles de parseo de formularios

**Código Principal**: `/home/chris/EnergyIntel/fuentes/cen-acceso-abierto/src/`
- `main.py` (246 líneas) - Orquestador de 8 pasos
- `settings.py` (113 líneas) - Configuración
- `http_client.py` (227 líneas) - Cliente HTTP con retries
- `extractors/solicitudes.py` (396 líneas) - Extracción de proyectos/documentos
- `repositories/cen.py` (CENDatabaseManager) - Operaciones de base de datos
- Parsers: 3,000+ líneas total (PDF + XLSX para SAC, SUCTD, Fehaciente)

**Schemas**: `/home/chris/EnergyIntel/fuentes/cen-acceso-abierto/db/`
- `init.sql` - Tablas base
- `schema_solicitudes.sql` - Proyectos y documentos
- `schema_formularios_parsed.sql` - Tablas y vistas de formularios parseados

---

Este es un sistema de ingesta de datos production-ready y bien documentado para datos de conexiones de la red eléctrica chilena.
