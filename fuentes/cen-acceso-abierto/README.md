# CEN Acceso Abierto Data Dumper

A reusable Python-based data ingestion template for consuming REST APIs from public sources. This service fetches data from configured API endpoints and stores raw responses in a MariaDB database.

## Features

- 🚀 Simple, maintainable architecture designed for low maintenance
- 🔄 Automatic retry logic with exponential backoff
- 📦 Raw data storage in JSON format
- 🐳 Fully containerized with Docker and Docker Compose
- ⚙️ Environment-based configuration with sensible defaults
- 📊 MariaDB 10.11 for reliable data storage
- 🔧 Built with modern Python tools (httpx, pydantic-settings, uv)

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git

### Setup

1. **Clone the repository**
   ```bash
   git clone git@github.com:
   cd cen-acceso-abierto
   ```

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure CEN API settings** (optional)

   The `.env` file is pre-configured for CEN Acceso Abierto. Optionally adjust:
   ```env
   # Years to extract (comma-separated)
   CEN_YEARS=2025

   # Or for production, extract all available years:
   CEN_YEARS=2020,2021,2022,2023,2024,2025
   ```

4. **Start the database**
   ```bash
   docker-compose up -d cen_db
   ```

   Wait for the database to be healthy (about 30 seconds):
   ```bash
   docker-compose ps
   ```

5. **Run the data ingestion**
   ```bash
   docker-compose run --rm cen_app
   ```

## Usage

### Running Manually

Execute a single ingestion run:
```bash
docker-compose run --rm cen_app
```

### Running on a Schedule

Add to your system crontab for periodic execution:

```bash
# Run every hour
0 * * * * cd /path/to/cen-acceso-abierto && docker-compose run --rm cen_app

# Run every 6 hours
0 */6 * * * cd /path/to/cen-acceso-abierto && docker-compose run --rm cen_app

# Run daily at 2 AM
0 2 * * * cd /path/to/cen-acceso-abierto && docker-compose run --rm cen_app
```

### Viewing Data

Connect to the database to view stored data:

```bash
docker-compose exec cen_db mysql -u cen_user -pcen_password cen_acceso_abierto
```

Query examples:
```sql
-- View all fetched data
SELECT * FROM raw_api_data ORDER BY fetched_at DESC LIMIT 10;

-- View successful fetches only
SELECT * FROM successful_fetches LIMIT 10;

-- View latest fetch per URL
SELECT * FROM latest_fetches;

-- Count fetches per URL
SELECT source_url, COUNT(*) as fetch_count
FROM raw_api_data
GROUP BY source_url;
```

## Project Structure

```
cen-acceso-abierto/
├── src/
│   ├── __init__.py
│   ├── main.py          # Main orchestration logic
│   ├── settings.py      # Configuration management
│   ├── database.py      # Database operations
│   └── client.py        # HTTP client for APIs
├── db/
│   ├── init.sql         # Database initialization
│   └── data/            # MariaDB data (gitignored)
├── .env.example         # Example environment variables
├── Dockerfile           # Application container
├── docker-compose.yml   # Service orchestration
├── pyproject.toml       # Python dependencies
└── CLAUDE.md           # Development guide
```

## Configuration

All configuration is done via environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | Database hostname | `cen_db` |
| `DB_PORT` | Database port | `3306` |
| `DB_USER` | Database username | `cen_user` |
| `DB_PASSWORD` | Database password | `cen_password` |
| `DB_NAME` | Database name | `cen_acceso_abierto` |
| `CEN_API_BASE_URL` | CEN Public API base URL | `https://pkb3ax2pkg...` |
| `CEN_YEARS` | Years to extract (comma-separated) | `2025` |
| `CEN_DOCUMENT_TYPES` | Document types to filter | `Formulario SUCTD,...` |
| `REQUEST_TIMEOUT` | HTTP timeout in seconds | `30` |
| `MAX_RETRIES` | Max retry attempts | `3` |

## Development

### Local Development without Docker

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Create virtual environment and install dependencies**:
   ```bash
   uv sync
   ```

3. **Activate virtual environment**:
   ```bash
   source .venv/bin/activate  # On Unix/macOS
   # or
   .venv\Scripts\activate  # On Windows
   ```

4. **Run the application**:
   ```bash
   python -m src.main
   ```

### Running Tests

*(Testing framework to be added)*

## Production Deployment

For production deployment on the Antumanque server:

1. **Update `.env` with production database credentials**:
   ```env
   DB_HOST=antumanque.db.hostname
   DB_USER=production_user
   DB_PASSWORD=secure_password
   ```

2. **Build and run** (database service not needed):
   ```bash
   docker build -t cen-acceso-abierto .
   docker run --env-file .env cen-acceso-abierto
   ```

3. **Set up cron** on the server for periodic execution

## Troubleshooting

### Database Connection Failed

- Ensure the database service is healthy: `docker-compose ps`
- Check database logs: `docker-compose logs cen_db`
- Verify credentials in `.env` match docker-compose.yml

### No Data Fetched

- Verify CEN API configuration in `.env` (`CEN_API_BASE_URL`, `CEN_YEARS`)
- Test API accessibility: `curl "https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public?tipo=6&anio=2025&tipo_solicitud_id=0&solicitud_id=null"`
- Check application logs for error messages

### API Request Timeout

- Increase `REQUEST_TIMEOUT` in `.env`
- Check network connectivity to API endpoints
- Verify the API endpoints are responding

## Future Extensions

This template can be extended for:

- **Web Scraping**: Add `src/scraper.py` with BeautifulSoup/Playwright
- **PDF Parsing**: Add `src/pdf_parser.py` with PyPDF2/pdfplumber
- **New CEN Endpoints**: Create new extractors in `src/extractors/` following the existing pattern
- **Data Transformation**: Add parsers in `src/parsers/` for custom transformations

## License

*(Add your license here)*

## Contributing

*(Add contribution guidelines here)*
