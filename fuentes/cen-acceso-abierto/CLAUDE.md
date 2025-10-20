# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CEN Acceso Abierto Data Dumper** - A reusable Python data ingestion template for consuming REST APIs from public sources, specifically CEN (Coordinador Electrico Nacional) from Chile. The service fetches data from configured API endpoints and stores raw responses in MariaDB for further processing.

This is designed as a **template project** that can be extended for web scraping, PDF parsing, and other data ingestion tasks.

## Tech Stack

- **Language**: Python 3.12
- **Package Management**: uv (modern, fast Python package manager)
- **HTTP Client**: httpx (async-capable, modern requests alternative)
- **Database**: MariaDB 10.11 with mysql-connector-python
- **Configuration**: pydantic-settings (type-safe environment variable management)
- **Containerization**: Docker + Docker Compose
- **Deployment**: Container-based with cron scheduling

## Architecture

### High-Level Design

The project follows a **clean, layered architecture** with separation of concerns:

```
User/Cron → main.py (Orchestrator)
                ↓
         ┌──────┴──────┐
         ↓             ↓
   Interesados    Solicitudes
   Extractor      Extractor
         ↓             ↓
    Parsers ←────→ HTTP Client
         ↓             ↓
   Repositories → MariaDB
```

### Module Structure

```
src/
├── main.py                      # Orchestrator (no business logic)
│
├── extractors/                  # Extraction logic
│   ├── interesados.py          # /interesados endpoint
│   └── solicitudes.py          # tipo=6, tipo=11 endpoints
│
├── parsers/                     # Data transformation
│   ├── interesados.py          # JSON → dict
│   └── solicitudes.py          # JSON → dict
│
├── repositories/                # Database access
│   ├── base.py                 # Generic DatabaseManager
│   └── cen.py                  # CEN-specific tables
│
├── http_client.py              # HTTP operations
└── settings.py                 # Configuration
```

### Module Responsibilities

1. **`src/main.py`** - Orchestrator (Pure)
   - NO business logic
   - Loads configuration
   - Determines which extractors to run
   - Executes extractors in order
   - Reports overall results

2. **`src/extractors/`** - Extraction Logic
   - **`interesados.py`**: Extracts stakeholder data from `/interesados` endpoint
   - **`solicitudes.py`**: Extracts projects (tipo=6) and documents (tipo=11)
   - Each extractor is self-contained with its own run() method
   - Handles API calls, parsing, and database storage

3. **`src/parsers/`** - Data Transformation
   - **`interesados.py`**: Transforms raw JSON to normalized stakeholder records
   - **`solicitudes.py`**: Transforms raw JSON to solicitud/documento records
   - Pure functions with no side effects
   - Easy to test and modify

4. **`src/repositories/`** - Database Access Layer
   - **`base.py`**: Generic DatabaseManager for `raw_api_data` and `interesados` tables
   - **`cen.py`**: CENDatabaseManager for `solicitudes` and `documentos` tables
   - Connection management with context managers
   - Bulk insert operations with append-only strategy

5. **`src/http_client.py`** - HTTP Operations
   - Retry logic with exponential backoff
   - Configurable timeouts
   - Returns tuple: (status_code, data, error)
   - Shared by all extractors

6. **`src/settings.py`** - Configuration Management
   - Type-safe configuration using pydantic-settings
   - Loads from environment variables and .env files
   - Singleton pattern
   - Includes helper methods like `get_db_config()`

### Database Schema

**Table: `raw_api_data`**
- `id` (BIGINT, PK) - Auto-incrementing primary key
- `source_url` (VARCHAR) - The URL that was fetched
- `fetched_at` (TIMESTAMP) - When the data was fetched
- `status_code` (INT) - HTTP status code
- `data` (JSON) - Raw response data as JSON
- `error_message` (TEXT) - Error message if request failed

**Views:**
- `successful_fetches` - Only 2xx status codes
- `latest_fetches` - Most recent fetch per URL

### Naming Conventions

Follow standard Python conventions:
- **Database names/tables/columns**: `snake_case` (e.g., `raw_api_data`, `source_url`)
- **Python files/functions**: `snake_case` (e.g., `database.py`, `fetch_url()`)
- **Python classes**: `PascalCase` (e.g., `DatabaseManager`, `APIClient`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `MAX_RETRIES`)

## Development Workflow

### Local Development Setup

```bash
# Install dependencies with uv
uv sync

# Copy environment template
cp .env.example .env

# Edit .env with your API URLs (numbered format)
nano .env

# Start database only
docker-compose up -d cen_db

# Run application (connects to Docker database)
python -m src.main
```

### Docker Development

```bash
# Start database
docker-compose up -d cen_db

# Wait for health check (30 seconds)
docker-compose ps

# Run data ingestion
docker-compose run --rm cen_app

# View logs
docker-compose logs cen_app
docker-compose logs cen_db
```

### Common Development Commands

```bash
# Build Docker image
docker-compose build cen_app

# Start database in background
docker-compose up -d cen_db

# Stop all services
docker-compose down

# Reset database (delete all data)
docker-compose down -v

# Connect to database
docker-compose exec cen_db mysql -u cen_user -pcen_password cen_acceso_abierto

# View database logs
docker-compose logs -f cen_db

# Run app with custom environment
docker-compose run --rm -e CEN_YEARS="2024,2025" cen_app
```

## Development vs Production

### Local Development
- Uses docker-compose.yml with local MariaDB container
- Database at `DB_HOST=cen_db` (Docker service name)
- Data persisted in `./db/data` volume
- Can reset easily with `docker-compose down -v`

### Production (Antumanque Server)
- Database is external (not in Docker)
- Override `DB_HOST` to point to production database
- Use environment variables or `.env` for config
- Schedule with system cron:
  ```bash
  0 * * * * cd /path/to/project && docker-compose run --rm cen_app
  ```

## Code Patterns and Best Practices

### Pure Functions

Where valuable, functions are kept pure (no side effects):
- `parse_api_urls()` in settings.py
- Factory functions like `get_settings()`, `get_api_client()`

### Error Handling

- **Per-URL errors don't stop execution** - Iterate through all URLs even if some fail
- **Database errors are critical** - Fail fast if database connection fails
- **All errors are logged** with appropriate log levels
- **Exit codes**: 0 for success, 1 for failure

### Context Managers

Database connections use context managers for safe resource cleanup:
```python
with db_manager.connection() as conn:
    cursor = conn.cursor()
    # ... operations
```

### Type Hints

All functions use type hints for clarity:
```python
def fetch_url(self, url: str) -> Tuple[int, Optional[Any], Optional[str]]:
```

### Logging

All modules use standard Python logging:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error", exc_info=True)
```

### Code Comments

**All code comments should be in Spanish** for better team comprehension:

```python
# CORRECTO: Comentarios en español
# Verificar si ya existe en la base de datos
existing_ids = get_existing_ids()

# INCORRECTO: Comments in English
# Check if already exists in database
existing_ids = get_existing_ids()
```

**Bilingual approach for clarity:**
- Spanish comment first (primary)
- English translation on next line (optional, for documentation)

```python
# Filtrar solo los registros NUEVOS
# Filter only NEW records
new_records = [r for r in records if r.id not in existing_ids]
```

**Docstrings:** Keep in English (for compatibility with tools), but add Spanish explanations in key sections.

## Data Normalization Strategy

**Append-Only Approach** - The system ONLY adds new records, never updates or deletes:

### Key Principles
- ✅ **Insert** new records not in database
- ❌ **Never update** existing records
- ❌ **Never delete** records removed from API
- 📊 **Preserve** complete historical record

### Implementation
Located in `src/database.py` → `insert_interesados_bulk()`:
1. Query existing `solicitud_id` values from database
2. Filter incoming records to only NEW ones
3. Insert only the new records
4. Log skipped duplicates

### Why Append-Only?
- Complete audit trail
- Historical preservation
- Idempotent operations (safe to run multiple times)
- Regulatory compliance

**See**: `docs/development/NORMALIZATION.md` for detailed explanation

## Adding New Data Sources

The system is configured for CEN Acceso Abierto API. To add new endpoints from the same API:

1. **Create a new extractor** in `src/extractors/` following the existing pattern
2. **Add parser logic** in `src/parsers/` for data transformation
3. **Update main.py** to include the new extractor in the orchestration flow
4. **Extend database schema** if new tables are needed

The base URL (`CEN_API_BASE_URL`) is shared across all CEN endpoints.

## Extending the Template

Future extensions can follow this pattern:

### Web Scraping
Create `src/scraper.py`:
```python
class WebScraper:
    def scrape_url(self, url: str) -> Tuple[int, Any, Optional[str]]:
        # BeautifulSoup or Playwright logic
        pass
```

Update `src/main.py` to use scraper for certain URLs.

### PDF Parsing
Create `src/pdf_parser.py`:
```python
class PDFParser:
    def parse_pdf(self, pdf_url: str) -> Tuple[int, Any, Optional[str]]:
        # PyPDF2 or pdfplumber logic
        pass
```

### Data Transformation
Create `src/transformers.py`:
```python
def transform_raw_data(raw_data: dict) -> dict:
    # Transform JSON to structured format
    pass
```

## Testing

*(To be implemented)*

Future testing setup should include:
- pytest for unit tests
- pytest-docker for integration tests with MariaDB
- httpx mocking for API client tests
- Test fixtures for database operations

## Deployment

### Building for Production

```bash
# Build image
docker build -t cen-acceso-abierto:latest .

# Tag for registry (if applicable)
docker tag cen-acceso-abierto:latest registry.example.com/cen-acceso-abierto:latest

# Push to registry
docker push registry.example.com/cen-acceso-abierto:latest
```

### Running in Production

With external database:
```bash
docker run \
  -e DB_HOST=production.db.host \
  -e DB_USER=prod_user \
  -e DB_PASSWORD=secure_pass \
  -e CEN_YEARS="2020,2021,2022,2023,2024,2025" \
  cen-acceso-abierto:latest
```

### Scheduling

System cron is the recommended approach:
```cron
# /etc/cron.d/cen-acceso-abierto
0 * * * * user cd /path/to/project && docker-compose run --rm app >> /var/log/cen-ingestion.log 2>&1
```

## Troubleshooting

### Import Errors
If you see "ModuleNotFoundError: No module named 'src'", run from project root:
```bash
python -m src.main
```

### Database Connection Issues
Check that the database is healthy and credentials match:
```bash
docker-compose ps  # Should show cen_db as "healthy"
docker-compose logs cen_db  # Check for errors
```

### No Data Being Fetched
Verify CEN API configuration:
```bash
docker-compose run --rm cen_app python -c "from src.settings import get_settings; s = get_settings(); print(f'API: {s.cen_api_base_url}'); print(f'Years: {s.cen_years_list}')"
```

## Project Files Reference

- **`pyproject.toml`** - Package metadata and dependencies (managed by uv)
- **`uv.lock`** - Locked dependency versions (committed to git)
- **`.env.example`** - Template for environment variables (committed)
- **`.env`** - Actual environment variables (gitignored, create locally)
- **`Dockerfile`** - Production container definition
- **`docker-compose.yml`** - Local development orchestration
- **`db/init.sql`** - Database initialization script (runs on first start)
- **`PROJECT_PLAN.md`** - Detailed implementation plan (reference document)

## Additional Notes

- **Database name**: `cen_acceso_abierto` (snake_case)
- **Target audience**: Junior developers - keep code simple and well-documented
- **Philosophy**: Prefer clarity over cleverness
- **Retry strategy**: Exponential backoff (2, 4, 8 seconds)
- **Data storage**: Raw, unmodified responses (transformation happens later)

---

## 🆕 NEW: Sistema de Extracción de Solicitudes y Documentos (2025)

### Overview

Se ha agregado un **nuevo sistema completo** para extraer solicitudes de conexión eléctrica y sus documentos asociados desde la API del CEN.

### Nuevos Módulos

#### 1. **`src/main_cen.py`** - Script principal de extracción
   - Orquesta la extracción completa de solicitudes y documentos
   - **Paso 1**: Extrae solicitudes por año (tipo=6 de la API)
   - **Paso 2**: Para cada solicitud, extrae sus documentos (tipo=11)
   - **Paso 3**: Filtra y guarda solo documentos importantes
   - Implementa estrategia **append-only** (nunca actualiza ni borra)

#### 2. **`src/cen_database.py`** - Gestor de BD para solicitudes/documentos
   - Maneja tablas `solicitudes` y `documentos`
   - Funciones helper para parsear fechas ISO 8601 a MySQL
   - Métodos bulk insert con deduplicación automática
   - Estadísticas y queries útiles

#### 3. **`src/cen_extractor.py`** - Extractor de la API del CEN
   - Construye URLs dinámicamente con parámetros
   - Extrae solicitudes por año
   - Extrae documentos por solicitud_id
   - Filtra documentos por tipo (SUCTD, SAC, Formulario_proyecto_fehaciente)

### Nuevas Tablas en la Base de Datos

#### `solicitudes`
Almacena información completa de cada solicitud de conexión eléctrica:
- Datos del proyecto (nombre, potencia, tecnología)
- Empresa solicitante (RUT, razón social)
- Ubicación (región, comuna, lat/lng)
- Estado y etapa del proceso
- Información de conexión (subestación, tensión, fecha estimada)

**Fuente**: API endpoint `tipo=6&anio={year}`

#### `documentos`
Almacena metadata de documentos adjuntos a cada solicitud:
- Nombre del archivo y ruta en S3
- Tipo de documento (Formulario SUCTD, SAC, etc.)
- Fechas de creación/actualización
- Flags de visibilidad y descarga
- Relación con `solicitudes` via `solicitud_id` (FK)

**Fuente**: API endpoint `tipo=11&solicitud_id={id}`

#### Vistas Útiles
- `documentos_importantes`: Filtra solo SUCTD, SAC y Formulario_proyecto_fehaciente
- `solicitudes_con_documentos`: Solicitudes con conteo de documentos
- `estadisticas_extraccion`: Dashboard de estadísticas generales

### Documentación Completa

Ver documentación detallada en:
- **`docs/API_DOCUMENTATION.md`**: Documentación completa de todos los endpoints de la API del CEN (tipos 0-11)
- **`docs/DATABASE_SCHEMA.md`**: Schema de BD, relaciones, orden de llenado, y queries útiles

### Ejecución

```bash
# Local (con base de datos en Docker)
DB_HOST=localhost uv run python -m src.main_cen

# Docker
docker-compose run --rm cen_app python -m src.main_cen
```

### Configuración (.env)

```env
# Años a extraer (separados por coma)
CEN_YEARS=2025  # Para desarrollo
# CEN_YEARS=2020,2021,2022,2023,2024,2025  # Para producción

# Tipos de documentos a extraer
CEN_DOCUMENT_TYPES=Formulario SUCTD,Formulario SAC,Formulario_proyecto_fehaciente
```

### Datos Extraídos (Ejemplo: 2025)

- **2,448 solicitudes** de conexión eléctrica
  - 1,584 SASC (Solicitudes de Acceso y Conexión)
  - 631 SUCT (Uso de Capacidad de Transporte Dedicada)
  - 233 FEHACIENTES (Proyectos Fehacientes)
- **2,290 documentos** importantes
  - 655 Formularios SUCTD
  - 1,635 Formularios SAC
  - 0 Proyectos Fehacientes (no hay en 2025)

**Tiempo de extracción**: ~22 minutos (incluye 2,448 llamadas a la API)

### Estrategia Append-Only

El sistema **NUNCA** actualiza ni elimina registros:
- ✅ Solo **inserta** nuevos registros
- ✅ Seguro ejecutar múltiples veces (deduplicación automática)
- ✅ Preserva historial completo para auditoría
- ✅ Idempotente

### Próximos Pasos Sugeridos

1. **Descargar archivos**: Usar `documentos.ruta_s3` para descargar PDFs/XLSX
2. **Parsear PDFs**: Extraer datos estructurados de Formularios SUCTD/SAC
3. **Ampliar cobertura**: Procesar años 2020-2024
4. **Automatización**: Configurar cron para ejecución periódica

### Arquitectura Unificada del Sistema CEN

**Todos los componentes son parte del mismo sistema CEN**, usando la misma API base:

```
CEN API Base: https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public
│
├─→ src/main.py          → Endpoint /interesados      → tabla interesados
│                           (empresas stakeholders)
│
└─→ src/main_cen.py      → Endpoints parametrizados   → tablas solicitudes + documentos
    ├─ tipo=6              (solicitudes por año)
    └─ tipo=11             (documentos por solicitud_id)

Audit Trail Compartido:
└─→ raw_api_data (AMBOS scripts guardan todas sus respuestas API aquí)
```

**Relación entre tablas**:
```
interesados.solicitud_id → solicitudes.id (many-to-one)
```

Ambos scripts se complementan para proporcionar la vista completa de cada proyecto eléctrico.
