# Guía de Desarrollo con Claude Code

Esta guía describe cómo trabajar con este proyecto usando Claude Code.

## Contexto del Proyecto

**SEA SEIA Extractor** es un sistema de extracción de datos del Sistema de Evaluación de Impacto Ambiental (SEA) de Chile:
- Extrae proyectos de evaluación ambiental desde la API pública del SEA
- Almacena datos crudos y parseados en MariaDB
- Implementa estrategia append-only para preservar historial completo
- Basado en el proyecto `fuentes/base` reutilizable

## Estructura del Proyecto

```
fuentes/sea/
├── src/
│   ├── main.py                # Orquestador principal - PUNTO DE ENTRADA
│   ├── settings.py            # Configuración type-safe con pydantic
│   ├── core/                  # Utilidades fundamentales
│   │   ├── http_client.py     # Cliente HTTP con retries
│   │   ├── database.py        # Gestor de BD
│   │   └── logging.py         # Setup de logging
│   ├── extractors/            # Extractores
│   │   └── proyectos.py       # Extractor de proyectos (con paginación)
│   ├── parsers/               # Parsers
│   │   └── proyectos.py       # Parser de JSON a formato DB
│   └── repositories/          # Acceso a base de datos
│       └── proyectos.py       # Repository para proyectos + raw_data
├── db/
│   ├── init.sql               # Schema inicial
│   └── migrations/            # Migraciones versionadas
├── .env.example               # Template de configuración
├── docker-compose.yml         # Orquestación de servicios
├── Dockerfile
└── pyproject.toml            # Dependencias
```

## Arquitectura en Capas

```
main.py (Orquestador)
    ↓
extractors/ + parsers/ + repositories/
    ↓
core/ (http_client, database, logging)
    ↓
MariaDB
```

**Principio clave**: Separación de responsabilidades - cada capa tiene un propósito único.

## Flujo de Ejecución

### main.py - Orquestador Principal (Guardado Incremental)

El flujo completo con **guardado incremental por batches**:

1. **Inicialización**
   - Cargar settings desde `.env`
   - Setup logging
   - Inicializar componentes (http_client, db_manager, extractor, parser, repository)

2. **Extracción Completa**
   - `extractor.extract_all_proyectos()` → hace requests con paginación automática
   - Usa `totalRegistros` de la API para determinar el fin (no confía en conteo)
   - Retorna lista de `extraction_results` (una por página)

3. **Procesamiento por Batches** (cada 10 páginas por defecto)

   Para cada batch:

   a. **Guardar datos crudos**
      - `repository.insert_raw_data_bulk(batch_results)` → guarda en `raw_data`
      - ✅ Datos persistidos inmediatamente

   b. **Parsear proyectos del batch**
      - Para cada página: `parser.parse_proyectos_from_response(data)`
      - Acumula proyectos del batch

   c. **Guardar proyectos del batch**
      - `repository.insert_proyectos_bulk(batch_proyectos)` → guarda en `proyectos`
      - Implementa deduplicación automática (solo inserta nuevos)
      - ✅ Proyectos persistidos inmediatamente

   d. **Continuar con siguiente batch**
      - Si falla un batch, continúa con el siguiente
      - Progreso no se pierde

4. **Estadísticas Finales**
   - `repository.get_estadisticas()` → muestra resumen completo

## Módulos Principales

### 1. `src/extractors/proyectos.py` - ProyectosExtractor

**Responsabilidad**: Extraer proyectos desde la API del SEA con paginación automática.

**Métodos clave**:
- `extract_all_proyectos()` - Loop de paginación hasta que no haya más datos
- `extract_page(offset)` - Extrae una página específica

**Lógica de paginación** (simplificada - solo array vacío es confiable):
```python
offset = 1
while has_more:
    result = extract_page(offset)
    response_data = parse_json(result["data"])

    # CRÍTICO: Solo detenerse cuando el array está vacío
    proyectos = response_data.get("data", [])
    if len(proyectos) == 0:
        has_more = False  # Fin real de datos
    else:
        offset += 1

# NOTA: NO confiar en totalRegistros - retorna "0" en páginas intermedias
# SOLO el array vacío es confiable para determinar el fin
```

**¿Por qué ignorar totalRegistros?**
- La API del SEA tiene 29,886 proyectos (~299 páginas)
- `recordsTotal` solo aparece en la primera página: `"29886"`
- `totalRegistros` NO es confiable - retorna `"0"` en página 2 aunque sigue habiendo datos
- La ÚNICA señal confiable es cuando `len(response_data["data"]) == 0`
- Ejemplo real de la API:
  - Página 1: `totalRegistros="29.886"`, `recordsTotal="29886"`, 100 proyectos ✓
  - Página 2: `totalRegistros="0"`, `recordsTotal=null`, 100 proyectos ✓ (¡todavía hay datos!)
  - Página 300: `totalRegistros="0"`, `recordsTotal=null`, 0 proyectos ✗ (aquí sí termina)

### 2. `src/parsers/proyectos.py` - ProyectosParser

**Responsabilidad**: Transformar JSON de la API en formato estructurado para BD.

**Métodos clave**:
- `parse_proyectos_from_response(response_data)` - Parsea lista completa
- `parse_proyecto(proyecto_raw)` - Parsea proyecto individual
- `_parse_str()`, `_parse_int()`, `_parse_decimal()` - Helpers de conversión

**Ejemplo de transformación**:
```python
# Input (API):
{
  "EXPEDIENTE_ID": "2166674550",
  "EXPEDIENTE_NOMBRE": "Ampliación Centro...",
  "INVERSION_MM": "3500000.0"
}

# Output (DB):
{
  "expediente_id": 2166674550,
  "expediente_nombre": "Ampliación Centro...",
  "inversion_mm": 3500000.0
}
```

### 3. `src/repositories/proyectos.py` - ProyectosRepository

**Responsabilidad**: Operaciones de base de datos con estrategia append-only.

**Métodos clave**:
- `insert_raw_data_bulk()` - Inserta datos crudos
- `insert_proyectos_bulk()` - Inserta proyectos con deduplicación
- `get_existing_expediente_ids()` - Obtiene IDs existentes
- `get_estadisticas()` - Genera estadísticas

**Estrategia append-only**:
```python
# 1. Obtener IDs existentes
existing_ids = get_existing_expediente_ids()  # {123, 456, 789}

# 2. Filtrar solo nuevos
new_proyectos = [p for p in proyectos if p['expediente_id'] not in existing_ids]

# 3. Insertar solo nuevos
insert_proyectos_bulk(new_proyectos)
```

## Tareas Comunes

### 1. Agregar Nuevo Campo a Proyectos

**Escenario**: La API agregó un nuevo campo que queremos capturar.

**Pasos**:

1. **Actualizar schema de BD** (`db/migrations/001_add_new_field.sql`):
   ```sql
   ALTER TABLE proyectos ADD COLUMN nuevo_campo VARCHAR(255);
   INSERT INTO schema_migrations (migration_name) VALUES ('001_add_new_field.sql');
   ```

2. **Actualizar parser** (`src/parsers/proyectos.py`):
   ```python
   def parse_proyecto(self, proyecto_raw: dict) -> dict:
       return {
           # ... campos existentes ...
           "nuevo_campo": self._parse_str(proyecto_raw.get("NUEVO_CAMPO")),
       }
   ```

3. **Actualizar repository** (`src/repositories/proyectos.py`):
   ```python
   query = """
       INSERT INTO proyectos (
           expediente_id, ..., nuevo_campo
       ) VALUES (%s, ..., %s)
   """
   params = (
       p.get("expediente_id"),
       # ...
       p.get("nuevo_campo"),
   )
   ```

### 2. Agregar Filtros de Búsqueda

**Escenario**: Quieres filtrar proyectos por titular o región.

**Pasos**:

1. **Actualizar settings** (`src/settings.py`):
   ```python
   sea_titular: str = Field(default="Gasco", description="Filtro por titular")
   ```

2. **Actualizar build_api_params**:
   ```python
   def build_api_params(self, offset: int = 1) -> dict:
       return {
           "titular": self.sea_titular,  # ← Agregar
           # ... otros params ...
       }
   ```

3. **Actualizar .env.example**:
   ```env
   SEA_TITULAR=           # Filtro por titular del proyecto
   ```

### 3. Modificar Tamaño de Página

**Escenario**: La API es lenta, quieres páginas más pequeñas.

**Pasos**:

1. Editar `.env`:
   ```env
   SEA_LIMIT=50  # En vez de 100
   ```

2. Reiniciar extracción:
   ```bash
   docker-compose run --rm sea_app
   ```

### 4. Ver Proyectos Nuevos desde Última Ejecución

**Query SQL**:
```sql
SELECT *
FROM proyectos
WHERE fetched_at > (
    SELECT MAX(fetched_at)
    FROM proyectos
    WHERE fetched_at < (SELECT MAX(fetched_at) FROM proyectos)
)
ORDER BY fetched_at DESC;
```

## Debugging

### 1. Ver Logs en Tiempo Real

```bash
# Durante ejecución
docker-compose run --rm sea_app

# Ver logs de BD
docker-compose logs -f sea_db
```

### 2. Aumentar Nivel de Logging

Editar `.env`:
```env
LOG_LEVEL=DEBUG  # En vez de INFO
```

### 3. Probar Query en BD Directamente

```bash
docker-compose exec sea_db mysql -u sea_user -psea_password sea_seia

# Dentro de MySQL:
SELECT * FROM proyectos LIMIT 5;
SELECT * FROM raw_data ORDER BY extracted_at DESC LIMIT 5;
SELECT * FROM estadisticas_generales;
```

### 4. Ejecutar sin Docker (Desarrollo)

```bash
# Iniciar solo BD
docker-compose up -d sea_db

# Ejecutar app localmente
uv sync
source .venv/bin/activate
python -m src.main
```

### 5. Resetear Base de Datos

```bash
# Borrar todo y empezar de cero
docker-compose down -v
docker-compose up -d sea_db
# Esperar ~30 segundos
docker-compose run --rm sea_app
```

## Convenciones de Código

### Naming

- **Archivos**: `snake_case.py`
- **Clases**: `PascalCase`
- **Funciones/variables**: `snake_case`
- **Constantes**: `SCREAMING_SNAKE_CASE`

### Imports

```python
# Standard library
import logging
from datetime import datetime

# Third-party
import httpx
from pydantic import Field

# Local
from src.core.http_client import HTTPClient
from src.settings import Settings
```

### Type Hints

Usar type hints en todos los métodos públicos:

```python
def extract_page(self, offset: int) -> dict[str, Any]:
    ...
```

### Docstrings

Usar docstrings estilo Google para clases y métodos públicos:

```python
def insert_proyectos_bulk(self, proyectos: list[dict]) -> tuple[int, int]:
    """
    Insertar múltiples proyectos en bulk, solo los que no existan.

    Args:
        proyectos: Lista de diccionarios con datos de proyectos

    Returns:
        Tupla (num_insertados, num_duplicados)

    Raises:
        MySQLError: Si falla la inserción
    """
```

### Comentarios en Español

Todos los comentarios deben estar en español:

```python
# CORRECTO: Comentarios en español
# Filtrar solo proyectos nuevos que no existan en la BD
new_proyectos = [p for p in proyectos if p['id'] not in existing_ids]

# INCORRECTO: Comments in English
# Filter only new projects
new_proyectos = [...]
```

## Configuración

**Archivo**: `.env` (copiar desde `.env.example`)

**Variables principales**:

```env
# Base de datos
DB_HOST=localhost          # 'sea_db' para Docker
DB_PORT=3306
DB_USER=sea_user
DB_PASSWORD=sea_password
DB_NAME=sea_seia

# API del SEA
SEA_API_BASE_URL=https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php
SEA_LIMIT=100
SEA_ORDER_COLUMN=FECHA_PRESENTACION
SEA_ORDER_DIR=desc

# Filtros (dejar vacío extrae todo)
SEA_SELECT_REGION=
SEA_TIPO_PRESENTACION=
SEA_PROJECT_STATUS=

# HTTP
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Workflow de Desarrollo

### Setup Inicial

```bash
# 1. Copiar template de config
cp .env.example .env

# 2. Editar .env con tu configuración
vim .env

# 3. Iniciar BD
docker-compose up -d sea_db

# 4. Esperar que BD esté ready
docker-compose ps

# 5. Instalar dependencias
uv sync

# 6. Activar venv
source .venv/bin/activate

# 7. Ejecutar aplicación
python -m src.main
```

### Desarrollo Iterativo

```bash
# 1. Hacer cambios en código

# 2. Ejecutar para probar
python -m src.main

# 3. Revisar logs y resultados en BD

# 4. Repetir
```

## API del SEA - Referencia

### Endpoint

```
POST https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php
Content-Type: application/x-www-form-urlencoded
```

### Parámetros

```
nombre=                    # Nombre del proyecto
titular=                   # Titular del proyecto
folio=                     # Folio
selectRegion=              # Región
selectComuna=              # Comuna
tipoPresentacion=          # Tipo de presentación (DIA, EIA)
projectStatus=             # Estado del proyecto
PresentacionMin=           # Fecha mínima (DD-MM-YYYY)
PresentacionMax=           # Fecha máxima (DD-MM-YYYY)
offset=1                   # Paginación - offset
limit=100                  # Paginación - límite
orderColumn=FECHA_PRESENTACION
orderDir=desc
```

### Response

```json
{
  "status": true,
  "data": [
    {
      "EXPEDIENTE_ID": "2166674550",
      "EXPEDIENTE_NOMBRE": "Ampliación Centro...",
      "WORKFLOW_DESCRIPCION": "DIA",
      "REGION_NOMBRE": "Región de Los Lagos",
      "TITULAR": "Gasco GLP S.A.",
      "INVERSION_MM": "3500000.0",
      "FECHA_PRESENTACION": "1761327753",
      "ESTADO_PROYECTO": "En Admisión"
    }
  ]
}
```

## Extracción Multi-Etapa: Del Proyecto al PDF

El sistema ahora implementa una extracción multi-etapa para llegar hasta el PDF del Resumen Ejecutivo (Capítulo 20) de cada proyecto.

### Arquitectura de 3 Etapas

```
ETAPA 1: Proyectos
    ↓
ETAPA 2: Documentos del Expediente (EIA/DIA)
    ↓
ETAPA 3: Links a PDFs de Resumen Ejecutivo
```

**Objetivo**: Rastrear pérdida de datos en cada etapa para Business Intelligence.

### Tablas Involucradas

#### 1. `proyectos` (Etapa 1)
- **Fuente**: API `buscarProyectoResumenAction.php`
- **Contenido**: Lista de proyectos ambientales
- **Clave**: `expediente_id` (único)
- **Siguiente paso**: Extraer documentos de cada expediente

#### 2. `expediente_documentos` (Etapa 2)
- **Fuente**: AJAX endpoint `xhr_busqueda_expediente.php?id_expediente={id}`
- **Contenido**: Documentos EIA/DIA de cada expediente
- **Clave**: `id_documento` (único)
- **FK**: `expediente_id` → `proyectos.expediente_id`
- **Siguiente paso**: Extraer link al PDF del documento

#### 3. `resumen_ejecutivo_links` (Etapa 3)
- **Fuente**: HTML de `documento.php?idDocumento={id}`
- **Contenido**: Links a PDFs del Capítulo 20 - Resumen Ejecutivo
- **Clave**: `id` (autoincrement)
- **FK**: `id_documento` → `expediente_documentos.id_documento`
- **Estado**: Tracking de descarga/parseo con enum `status`

### Flujo de Extracción Completo

#### **Etapa 1 → Etapa 2: Extraer Documentos del Expediente**

```python
# 1. Obtener proyectos sin documentos extraídos
proyectos = repository.get_proyectos_pendientes()

# 2. Para cada proyecto, extraer su lista de documentos
extractor = ExpedienteDocumentosExtractor(http_client)
results = extractor.extract_batch(proyectos)

# 3. Parsear HTML para encontrar documentos EIA/DIA
parser = ExpedienteDocumentosParser()
documentos = []
for result in results:
    docs = parser.parse_documentos(result["html_content"], result["expediente_id"])
    for doc in docs:
        doc["extracted_at"] = result["extracted_at"]
    documentos.extend(docs)

# 4. Guardar documentos en BD
repository = ExpedienteDocumentosRepository(db_manager)
repository.insert_documentos_bulk(documentos)
```

**URL de extracción**: `https://seia.sea.gob.cl/expediente/xhr_busqueda_expediente.php?id_expediente={id}`

**Datos extraídos**:
- `id_documento` - ID único del documento en sistema SEA
- `folio` - Folio del documento (ej: "2025-05-105-3")
- `tipo_documento` - "Estudio de impacto ambiental" o "Declaración de impacto ambiental"
- `remitente`, `destinatario` - Partes involucradas
- `fecha_generacion` - Fecha del documento
- `url_documento` - Link a la página del documento
- `url_anexos` - Link a anexos del documento

#### **Etapa 2 → Etapa 3: Extraer Links de Resumen Ejecutivo**

```python
# 1. Obtener documentos sin link de resumen ejecutivo
documentos = repository.get_documentos_sin_resumen_ejecutivo()

# 2. Para cada documento, extraer su contenido HTML
extractor = ResumenEjecutivoExtractor(http_client)
results = extractor.extract_batch(documentos)

# 3. Parsear HTML para encontrar link al PDF de Capítulo 20
parser = ResumenEjecutivoParser()
links = []
for result in results:
    link = parser.parse_resumen_ejecutivo_link(
        result["html_content"],
        result["id_documento"]
    )
    if link:
        link["extracted_at"] = result["extracted_at"]
        links.append(link)

    # También buscar link al documento firmado completo
    doc_firmado = parser.parse_documento_firmado_link(result["html_content"])
    if doc_firmado:
        link.update(doc_firmado)

# 4. Guardar links en BD
repository = ResumenEjecutivoLinksRepository(db_manager)
repository.insert_links_bulk(links)
```

**URL de extracción**: `https://seia.sea.gob.cl/documentos/documento.php?idDocumento={id}`

**Parsing HTML**:
- Buscar `<h3>Resumen ejecutivo</h3>` o `<h4>Resumen ejecutivo</h4>`
- En el siguiente `<ul>`, buscar links que contengan:
  - "Resumen ejecutivo" (case-insensitive)
  - "Capítulo 20" o "Cap 20"
- Extraer: `pdf_url`, `pdf_filename`, `texto_link`

**Datos extraídos**:
- `pdf_url` - URL completa al PDF del Capítulo 20
- `pdf_filename` - Nombre del archivo PDF
- `texto_link` - Texto del link (ej: "Capítulo 20 Resumen Ejecutivo")
- `documento_firmado_url` - URL al documento firmado completo (opcional)
- `documento_firmado_docid` - docId del documento firmado (opcional)

### Tracking de Pérdida de Datos

Queries útiles para Business Intelligence:

#### **Ver cobertura por etapa**

```sql
-- Total de proyectos
SELECT COUNT(*) as total_proyectos FROM proyectos;

-- Proyectos con documentos extraídos
SELECT COUNT(DISTINCT expediente_id) as con_documentos
FROM expediente_documentos;

-- Documentos con link a PDF extraído
SELECT COUNT(DISTINCT id_documento) as con_pdf
FROM resumen_ejecutivo_links;

-- Resumen completo
SELECT
    (SELECT COUNT(*) FROM proyectos) as total_proyectos,
    (SELECT COUNT(DISTINCT expediente_id) FROM expediente_documentos) as con_documentos,
    (SELECT COUNT(*) FROM resumen_ejecutivo_links) as con_pdf_link,
    ROUND(
        (SELECT COUNT(DISTINCT expediente_id) FROM expediente_documentos) /
        (SELECT COUNT(*) FROM proyectos) * 100,
        2
    ) as pct_con_documentos,
    ROUND(
        (SELECT COUNT(*) FROM resumen_ejecutivo_links) /
        (SELECT COUNT(*) FROM expediente_documentos) * 100,
        2
    ) as pct_con_pdf;
```

#### **Identificar proyectos sin documentos**

```sql
SELECT p.expediente_id, p.expediente_nombre, p.titular
FROM proyectos p
LEFT JOIN expediente_documentos ed ON p.expediente_id = ed.expediente_id
WHERE ed.id IS NULL
LIMIT 100;
```

#### **Identificar documentos sin PDF**

```sql
SELECT
    ed.id_documento,
    ed.expediente_id,
    ed.tipo_documento,
    ed.url_documento
FROM expediente_documentos ed
LEFT JOIN resumen_ejecutivo_links rel ON ed.id_documento = rel.id_documento
WHERE rel.id IS NULL
LIMIT 100;
```

### Módulos de Etapa 2 y 3

#### `src/extractors/expediente_documentos.py`
**Responsabilidad**: Extraer lista de documentos del expediente desde AJAX endpoint.

**Métodos clave**:
- `extract_documentos(expediente_id)` - Extrae una página de expediente
- `extract_batch(expedientes)` - Procesa múltiples expedientes

#### `src/parsers/expediente_documentos.py`
**Responsabilidad**: Parsear tabla HTML de documentos para encontrar EIA/DIA.

**Métodos clave**:
- `parse_documentos(html_content, expediente_id)` - Parsea tabla de documentos
- `_extract_id_documento(actions_cell)` - Extrae ID del onclick attribute
- `_parse_fecha(fecha_str)` - Convierte fecha a formato MySQL

**Filtros de búsqueda**: Solo extrae documentos con tipo:
- "Estudio de impacto ambiental"
- "Declaración de impacto ambiental"

#### `src/extractors/resumen_ejecutivo.py`
**Responsabilidad**: Extraer contenido HTML de la página del documento.

**Métodos clave**:
- `extract_documento_content(id_documento)` - Extrae HTML de documento
- `extract_batch(documentos)` - Procesa múltiples documentos

#### `src/parsers/resumen_ejecutivo.py`
**Responsabilidad**: Parsear HTML del documento para encontrar PDF del Capítulo 20.

**Métodos clave**:
- `parse_resumen_ejecutivo_link(html_content, id_documento)` - Busca link al PDF
- `parse_documento_firmado_link(html_content)` - Busca documento firmado completo

**Lógica de parsing**:
1. Buscar `<h3>` o `<h4>` con texto "resumen ejecutivo" (case-insensitive)
2. Buscar siguiente `<ul>` sibling
3. Buscar `<a>` con texto que contenga "resumen ejecutivo", "capítulo 20", o "cap 20"
4. Extraer `href` como `pdf_url`

#### `src/repositories/expediente_documentos.py`
**Responsabilidad**: Operaciones de BD para documentos del expediente.

**Métodos clave**:
- `insert_documentos_bulk(documentos)` - Inserción bulk con deduplicación
- `get_documentos_sin_resumen_ejecutivo(limit)` - Documentos pendientes de Etapa 3
- `mark_as_parsed(id_documento)` - Marcar como procesado
- `get_estadisticas()` - Stats de cobertura

**Deduplicación**: Usa `ON DUPLICATE KEY UPDATE` con `id_documento` como unique key.

#### `src/repositories/resumen_ejecutivo_links.py`
**Responsabilidad**: Operaciones de BD para links de PDFs.

**Métodos clave**:
- `insert_links_bulk(links)` - Inserción bulk con deduplicación
- `get_links_pending_download(limit)` - Links pendientes de descarga (futuro)
- `mark_as_downloaded(id_documento)` - Marcar como descargado (futuro)
- `mark_as_parsed(id_documento)` - Marcar como parseado (futuro)
- `update_status(id_documento, status, error_message)` - Actualizar estado
- `get_estadisticas()` - Stats de cobertura y tasa de éxito

**Estados posibles**: `pending`, `downloaded`, `parsed`, `error`

### Scripts de Ejecución (Futuros)

Los siguientes scripts de batch procesarán cada etapa:

#### `batch_extract_documentos.py` (Etapa 1→2)
```python
# Extrae documentos de todos los proyectos sin documentos
# Procesa en batches de 100 proyectos
```

#### `batch_extract_pdf_links.py` (Etapa 2→3)
```python
# Extrae links de PDFs de todos los documentos sin link
# Procesa en batches de 100 documentos
```

#### `batch_download_pdfs.py` (Futuro)
```python
# Descarga PDFs de todos los links en estado 'pending'
# Procesa en batches de 50 PDFs
```

#### `batch_parse_pdfs.py` (Futuro)
```python
# Parsea PDFs descargados para extraer datos estructurados
# Procesa en batches de 20 PDFs
```

## Próximos Pasos Sugeridos

1. ✅ **Extracción de Documentos EIA/DIA**: Completado
2. ✅ **Extracción de Links a PDFs**: Completado
3. **Descarga de PDFs**: Descargar PDFs de Resumen Ejecutivo
4. **Parseo de PDFs**: Extraer tablas con datos de involucrados
5. **Dashboard**: Crear visualizaciones de los datos extraídos
6. **Alertas**: Notificar cuando se agreguen proyectos nuevos

## Best Practices

1. **Siempre usar .env**: Nunca hardcodear credenciales
2. **Loggear apropiadamente**: INFO para progreso, ERROR para fallos
3. **Validar entrada**: Usar type hints y pydantic
4. **Manejar errores**: Try/except en extractors, retornar error en result
5. **Documentar código**: Docstrings en métodos públicos
6. **Append-only**: Nunca UPDATE/DELETE en proyectos o raw_data
7. **Índices en BD**: Agregar índices en columnas de query frecuente
8. **Guardado incremental**: Procesar en batches para no perder progreso (BATCH_SIZE=10)
9. **Encoding**: Siempre decodificar con ISO-8859-1 antes de parsear JSON de la API
10. **Paginación confiable**: Solo detenerse cuando el array de datos esté vacío - ignorar totalRegistros

## Troubleshooting

### Error: "No module named 'src'"

**Solución**: Ejecutar desde la raíz del proyecto:
```bash
python -m src.main  # ✓ Correcto
python src/main.py  # ✗ Incorrecto
```

### Error: "Can't connect to MySQL server"

**Solución**:
```bash
# Verificar que BD esté corriendo
docker-compose ps

# Si no está, iniciar
docker-compose up -d sea_db

# Esperar ~30 segundos
```

### La API retorna 0 proyectos

**Posibles causas**:
1. Filtros muy restrictivos en `.env` (dejarlos vacíos extrae todo)
2. API del SEA no disponible (probar manualmente con curl)
3. Error en parámetros de la API

**Solución**:
```bash
# Probar API manualmente
curl -X POST "https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php" \
  -d "offset=1&limit=10&orderColumn=FECHA_PRESENTACION&orderDir=desc"
```

---

**Happy coding with Claude!** 🚀
