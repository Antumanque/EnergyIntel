# API Data Ingestion Template

A reusable Python-based template for consuming REST APIs from public sources and storing raw responses in MariaDB. This template is designed to be simple, maintainable, and easily extensible for various data ingestion tasks including web scraping and PDF parsing.

## Features

- 🚀 Simple, maintainable architecture
- 🔄 Automatic retry logic with exponential backoff
- 📦 Raw data storage in JSON format for maximum flexibility
- 🐳 Fully containerized with Docker and Docker Compose
- ⚙️ Environment-based configuration with sensible defaults
- 📊 MariaDB 10.11 for reliable data storage
- 🔧 Built with modern Python tools (httpx, pydantic-settings, uv)
- 📝 Numbered URL configuration for easy management
- 🎯 Template-ready: just add your APIs and go!

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git

### Setup

1. **Clone or use this template**
   ```bash
   # Clone the repository
   git clone <your-repo-url>
   cd api-data-ingestion-template
   ```

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure your API URLs**

   Edit `.env` and add your API endpoints (one per line):
   ```env
   API_URL_1=https://api.yourservice.com/v1/data
   API_URL_2=https://api.yourservice.com/v1/users
   API_URL_3=https://api.anotherservice.com/endpoint
   ```

4. **Start the database**
   ```bash
   docker-compose up -d api_db
   ```

   Wait for the database to be healthy (about 30 seconds):
   ```bash
   docker-compose ps
   ```

5. **Run the data ingestion**
   ```bash
   docker-compose run --rm api_app
   ```

## Usage

### Running Manually

Execute a single ingestion run:
```bash
docker-compose run --rm api_app
```

### Running on a Schedule

Add to your system crontab for periodic execution:

```bash
# Run every hour
0 * * * * cd /path/to/api-data-ingestion-template && docker-compose run --rm api_app

# Run every 6 hours
0 */6 * * * cd /path/to/api-data-ingestion-template && docker-compose run --rm api_app

# Run daily at 2 AM
0 2 * * * cd /path/to/api-data-ingestion-template && docker-compose run --rm api_app
```

### Viewing Data

Connect to the database to view stored data:

```bash
docker-compose exec api_db mysql -u api_user -papi_password api_ingestion
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
api-data-ingestion-template/
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
| `DB_HOST` | Database hostname | `api_db` |
| `DB_PORT` | Database port | `3306` |
| `DB_USER` | Database username | `api_user` |
| `DB_PASSWORD` | Database password | `api_password` |
| `DB_NAME` | Database name | `api_ingestion` |
| `API_URL_1`, `API_URL_2`, etc. | API endpoints (numbered list) | (empty) |
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

For production deployment:

1. **Update `.env` with production database credentials**:
   ```env
   DB_HOST=production.db.hostname
   DB_USER=production_user
   DB_PASSWORD=secure_password
   ```

2. **Build and run** (database service not needed if using external DB):
   ```bash
   docker build -t api-data-ingestion:latest .
   docker run --env-file .env api-data-ingestion:latest
   ```

3. **Set up cron** on the server for periodic execution

## Troubleshooting

### Database Connection Failed

- Ensure the database service is healthy: `docker-compose ps`
- Check database logs: `docker-compose logs api_db`
- Verify credentials in `.env` match docker-compose.yml

### No Data Fetched

- Check that `API_URL_1` (and others) are set in `.env`
- Verify API endpoints are accessible: `curl <API_URL>`
- Check application logs for error messages

### API Request Timeout

- Increase `REQUEST_TIMEOUT` in `.env`
- Check network connectivity to API endpoints
- Verify the API endpoints are responding

## Extending the Template

This template is designed to be extended for:

### Web Scraping
Add `src/scraper.py` with BeautifulSoup/Playwright for HTML parsing

### PDF Parsing
Add `src/pdf_parser.py` with PyPDF2/pdfplumber for PDF extraction

### Data Transformation
Add `src/transformers.py` to normalize raw JSON into structured tables

### Multiple Data Sources
Simply add more `API_URL_N` entries to your `.env` file

## Use Cases

Perfect for:
- 📊 Open data initiatives
- 🏛️ Government API consumption
- 📈 Financial data collection
- 🌐 Multi-source data aggregation
- 🔄 Regular data synchronization tasks
- 📦 Building data lakes from APIs

## Architecture

Raw data dump approach:
1. Fetch complete API response
2. Store as single JSON blob in `raw_api_data` table
3. Optionally transform/normalize later

This provides maximum flexibility and preserves historical data exactly as received.

## License

*(Add your license here)*

## Contributing

*(Add contribution guidelines here)*
