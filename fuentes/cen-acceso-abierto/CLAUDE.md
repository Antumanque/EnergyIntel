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

The project follows a **simple, modular architecture**:

```
User/Cron → main.py → API Client → External APIs
                   ↓
                Database Manager → MariaDB
```

### Module Responsibilities

1. **`src/main.py`** - Main orchestration
   - Loads configuration
   - Initializes database
   - Iterates through API URLs
   - Coordinates fetch and store operations
   - Reports results and handles exit codes

2. **`src/settings.py`** - Configuration management
   - Uses pydantic-settings for type-safe config
   - Loads from environment variables and .env files
   - Provides validated settings as a singleton
   - Includes helper methods like `get_db_config()`

3. **`src/database.py`** - Database operations
   - Connection management with context managers
   - Table creation (idempotent)
   - Raw data insertion with JSON storage
   - Query helpers for latest fetches
   - Proper error handling and logging

4. **`src/client.py`** - HTTP client
   - Retry logic with exponential backoff
   - Configurable timeouts
   - Returns tuple: (status_code, data, error)
   - Includes async version for future concurrent fetches

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
docker-compose run --rm -e API_URL_1="https://example.com/api" cen_app
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

To add new API endpoints:

1. **Simple**: Just add numbered URLs to `.env`:
   ```env
   API_URL_1=https://www.coordinador.cl/api/endpoint1
   API_URL_2=https://www.coordinador.cl/api/endpoint2
   API_URL_3=https://www.coordinador.cl/api/endpoint3
   ```

2. **No code changes needed** - The system processes all URLs identically
3. **Easy to manage** - Each URL on its own line for clarity

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
  -e API_URLS="https://api.example.com/v1/data" \
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
Verify API URLs are set:
```bash
docker-compose run --rm cen_app python -c "from src.settings import get_settings; print(get_settings().api_urls)"
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
