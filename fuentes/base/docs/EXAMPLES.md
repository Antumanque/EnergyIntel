# Ejemplos de Uso

Esta guía presenta ejemplos prácticos completos para diferentes casos de uso de Fuentes Base.

## Índice de Ejemplos

- [REST API](#rest-api)
- [Web Scraping Estático](#web-scraping-estático)
- [Web Scraping Dinámico](#web-scraping-dinámico)
- [Descarga y Parseo de Archivos](#descarga-y-parseo-de-archivos)
- [Casos de Uso Completos](#casos-de-uso-completos)

---

## REST API

### Ejemplo 1: API Pública Simple

**Caso de uso**: Extraer datos desde JSONPlaceholder.

**Configuración** (`examples/rest_api/.env.example`):
```env
SOURCE_TYPE=api_rest
API_URL_1=https://jsonplaceholder.typicode.com/posts
API_URL_2=https://jsonplaceholder.typicode.com/users
```

**Ejecución**:
```bash
cp examples/rest_api/.env.example .env
docker-compose up -d base_db
sleep 30
docker-compose run --rm base_app
```

**Referencia**: `examples/rest_api/README.md`

### Ejemplo 2: API con Paginación

**Escenario**: API que retorna datos en páginas.

```python
from src.extractors.api_rest import APIRestExtractor

class PaginatedAPIExtractor(APIRestExtractor):
    def __init__(self, settings, base_url, max_pages=10):
        urls = [f"{base_url}?page={i}" for i in range(1, max_pages + 1)]
        super().__init__(settings, urls=urls)

# Uso
extractor = PaginatedAPIExtractor(
    settings,
    base_url="https://api.example.com/items",
    max_pages=5
)
results = extractor.extract()
```

### Ejemplo 3: API con Autenticación Bearer

```python
import os
from src.extractors.api_rest import APIRestExtractor
from src.core.http_client import HTTPClient

class AuthAPIExtractor(APIRestExtractor):
    def _extract_single_url(self, url: str) -> dict:
        token = os.getenv("API_TOKEN")
        status_code, data, error = self.http_client.fetch_url(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        return {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
```

### Ejemplo 4: Rate Limiting

```python
import time
from src.extractors.api_rest import APIRestExtractor

class RateLimitedExtractor(APIRestExtractor):
    def __init__(self, settings, urls=None, delay_seconds=1):
        super().__init__(settings, urls)
        self.delay = delay_seconds

    def extract(self):
        results = []
        for url in self.urls:
            result = self._extract_single_url(url)
            results.append(result)
            time.sleep(self.delay)  # Esperar entre requests

        self.results = results
        self.log_summary()
        return results
```

---

## Web Scraping Estático

### Ejemplo 1: Wikipedia Scraping

**Caso de uso**: Extraer información de páginas de Wikipedia.

**Configuración**:
```env
SOURCE_TYPE=web_static
WEB_URL_1=https://en.wikipedia.org/wiki/Python_(programming_language)
WEB_URL_2=https://en.wikipedia.org/wiki/Data_science
```

**Ejecución**:
```bash
cp examples/web_scraping/.env.example .env
docker-compose run --rm base_app
```

**Referencia**: `examples/web_scraping/README.md`

### Ejemplo 2: Extractor de Noticias

```python
from src.extractors.web_static import WebStaticExtractor
from bs4 import BeautifulSoup

class NewsExtractor(WebStaticExtractor):
    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        articles = []
        for article in soup.find_all("article"):
            title = article.find("h2")
            date = article.find("time")
            summary = article.find("p", class_="summary")

            if title:
                articles.append({
                    "title": title.get_text(strip=True),
                    "date": date["datetime"] if date else None,
                    "summary": summary.get_text(strip=True) if summary else None,
                })

        return {
            "site_name": soup.find("title").string if soup.title else None,
            "articles": articles,
            "num_articles": len(articles),
        }
```

### Ejemplo 3: Extraer Tabla HTML

```python
from src.extractors.web_static import WebStaticExtractor
from bs4 import BeautifulSoup

class TableExtractor(WebStaticExtractor):
    def __init__(self, settings, urls=None, table_selector="table"):
        super().__init__(settings, urls, parse_html=True)
        self.table_selector = table_selector

    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        table = soup.select_one(self.table_selector)
        if not table:
            return {"error": "Table not found"}

        # Headers
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        # Rows
        rows = []
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                rows.append(dict(zip(headers, cells)))

        return {
            "headers": headers,
            "rows": rows,
            "num_rows": len(rows),
        }

# Uso
extractor = TableExtractor(
    settings,
    urls=["https://example.com/data-table"],
    table_selector="table.data-table"
)
```

---

## Web Scraping Dinámico

### Ejemplo 1: Página con JavaScript

**Referencia**: `examples/web_scraping/dynamic_example.md`

**Configuración**:
```env
SOURCE_TYPE=web_dynamic
WEB_URL_1=https://example.com/spa-page
PLAYWRIGHT_HEADLESS=true
```

### Ejemplo 2: Click + Scroll

```python
from src.extractors.web_dynamic import WebDynamicExtractor
from playwright.sync_api import Browser

class InteractiveExtractor(WebDynamicExtractor):
    def _extract_single_url(self, browser: Browser, url: str) -> dict:
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        # Click "Load More" button
        page.click("button#load-more")
        page.wait_for_selector("div.new-content", timeout=10000)

        # Scroll para lazy-loading
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

        data = {
            "html": page.content(),
            "items": page.eval_on_selector_all(
                "div.item",
                "elements => elements.map(e => e.textContent)"
            ),
        }

        page.close()

        return {
            "source_url": url,
            "status_code": 200,
            "data": data,
            "error_message": None,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
```

### Ejemplo 3: Login + Scraping

```python
from src.extractors.web_dynamic import WebDynamicExtractor

class AuthenticatedScraper(WebDynamicExtractor):
    def __init__(self, settings, username, password, **kwargs):
        super().__init__(settings, **kwargs)
        self.username = username
        self.password = password

    def extract(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.settings.playwright_headless)
            page = browser.new_page()

            # Login
            page.goto("https://example.com/login")
            page.fill("input#username", self.username)
            page.fill("input#password", self.password)
            page.click("button[type='submit']")
            page.wait_for_url("**/dashboard")

            # Scrape authenticated pages
            results = []
            for url in self.urls:
                page.goto(url)
                # ... extracción
                results.append(result)

            browser.close()

        self.results = results
        self.log_summary()
        return results
```

---

## Descarga y Parseo de Archivos

### Ejemplo 1: Descarga Simple

**Configuración**:
```env
SOURCE_TYPE=file_download
FILE_URL_1=https://example.com/report.pdf
FILE_URL_2=https://example.com/data.xlsx
DOWNLOAD_DIR=downloads
```

**Referencia**: `examples/file_processing/README.md`

### Ejemplo 2: Pipeline Completo (Descarga + Parseo)

```python
from src.extractors.file_download import FileDownloadExtractor
from src.parsers.pdf_parser import PDFParser
from src.parsers.xlsx_parser import XLSXParser
from src.repositories.raw_data import get_raw_data_repository, get_parsed_data_repository
from pathlib import Path

def download_and_parse_pipeline():
    settings = get_settings()
    db_manager = get_database_manager(settings)

    # 1. Download
    downloader = FileDownloadExtractor(settings)
    download_results = downloader.extract()

    # 2. Store raw data
    raw_repo = get_raw_data_repository(db_manager)
    raw_ids = []
    for result in download_results:
        row_id = raw_repo.insert(
            source_url=result["source_url"],
            source_type="file_download",
            status_code=result["status_code"],
            data=result["data"],
            error_message=result.get("error_message"),
        )
        raw_ids.append(row_id)

    # 3. Parse each file
    parsed_repo = get_parsed_data_repository(db_manager)

    for i, result in enumerate(download_results):
        if result.get("error_message"):
            continue

        file_path = Path(result["data"]["file_path"])
        extension = file_path.suffix

        # Select parser
        if extension == ".pdf":
            parser = PDFParser()
            parser_type = "pdf"
        elif extension in [".xlsx", ".xls"]:
            parser = XLSXParser()
            parser_type = "xlsx"
        else:
            continue

        # Parse
        parse_result = parser.parse_safe(file_path)

        # Store parsed data
        parsed_repo.insert(
            raw_data_id=raw_ids[i],
            parser_type=parser_type,
            parsing_successful=parse_result["parsing_successful"],
            parsed_content=parse_result.get("parsed_data"),
            error_message=parse_result.get("error_message"),
            metadata=parse_result.get("metadata"),
        )

    print(f"Downloaded and parsed {len(download_results)} files")
```

### Ejemplo 3: Parseo Customizado de PDF

```python
from src.parsers.pdf_parser import PDFParser
import pdfplumber
import re

class FormularioPDFParser(PDFParser):
    """Parser para formularios PDF específicos."""

    def parse(self, data):
        file_path = Path(data)

        try:
            with pdfplumber.open(file_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()

                # Extraer campos específicos con regex
                parsed_data = {
                    "razon_social": self._extract_field(text, r"Razón Social:\s*(.+)"),
                    "rut": self._extract_field(text, r"RUT:\s*([\d\.-kK]+)"),
                    "proyecto": self._extract_field(text, r"Proyecto:\s*(.+)"),
                }

                return {
                    "parsing_successful": True,
                    "parsed_data": parsed_data,
                    "error_message": None,
                    "metadata": {"parser_type": "formulario_pdf"},
                }

        except Exception as e:
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "formulario_pdf"},
            }

    def _extract_field(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None
```

---

## Casos de Uso Completos

### Caso 1: Monitoreo de APIs Gubernamentales

**Escenario**: Extraer datos diarios de APIs de datos abiertos del gobierno.

**Setup**:
```env
SOURCE_TYPE=api_rest
API_URL_1=https://api.datos.gob.cl/energy/consumption
API_URL_2=https://api.datos.gob.cl/energy/generation
LOG_LEVEL=INFO
```

**Cron** (ejecutar diariamente a las 2 AM):
```cron
0 2 * * * cd /path/fuentes/base && docker-compose run --rm base_app
```

**Consultas de Análisis**:
```sql
-- Últimos datos extraídos
SELECT
    source_url,
    JSON_EXTRACT(data, '$.consumption') as consumption,
    extracted_at
FROM raw_data
WHERE source_type = 'api_rest'
ORDER BY extracted_at DESC
LIMIT 10;

-- Tendencia semanal
SELECT
    DATE(extracted_at) as date,
    AVG(JSON_EXTRACT(data, '$.consumption')) as avg_consumption
FROM raw_data
WHERE source_url LIKE '%consumption%'
  AND extracted_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE(extracted_at);
```

### Caso 2: Scraping de Reportes Regulatorios

**Escenario**: Descargar y parsear reportes PDF publicados mensualmente.

**Step 1 - Scraping**: Encontrar enlaces de reportes
```python
from src.extractors.web_static import WebStaticExtractor

class ReportLinksExtractor(WebStaticExtractor):
    def _parse_html_content(self, html_content):
        soup = BeautifulSoup(html_content, "lxml")

        report_links = []
        for link in soup.select("a.report-download"):
            href = link.get("href")
            if href and href.endswith(".pdf"):
                report_links.append(href)

        return {"report_urls": report_links}

# Ejecutar
extractor = ReportLinksExtractor(settings, urls=["https://regulator.gov/reports"])
results = extractor.extract()
report_urls = results[0]["data"]["report_urls"]
```

**Step 2 - Descarga**: Descargar PDFs
```python
from src.extractors.file_download import FileDownloadExtractor

downloader = FileDownloadExtractor(settings, urls=report_urls)
download_results = downloader.extract()
```

**Step 3 - Parseo**: Extraer datos de PDFs
```python
from src.parsers.pdf_parser import PDFParser

parser = PDFParser()
for result in download_results:
    if result["error_message"]:
        continue

    file_path = result["data"]["file_path"]
    parse_result = parser.parse_safe(file_path)

    # Store in parsed_data table
    # ...
```

### Caso 3: Agregación Multi-Fuente

**Escenario**: Combinar datos de API, web scraping y archivos.

**Arquitectura**:
1. API REST → Datos en tiempo real
2. Web Static → Metadatos desde sitio web
3. File Download → Reportes históricos

**Implementación**:
```python
from src.extractors.api_rest import APIRestExtractor
from src.extractors.web_static import WebStaticExtractor
from src.extractors.file_download import FileDownloadExtractor

def multi_source_extraction():
    settings = get_settings()

    # Fuente 1: API
    api_extractor = APIRestExtractor(settings, urls=["https://api.example.com/realtime"])
    api_results = api_extractor.extract()

    # Fuente 2: Web
    web_extractor = WebStaticExtractor(settings, urls=["https://example.com/metadata"])
    web_results = web_extractor.extract()

    # Fuente 3: Files
    file_extractor = FileDownloadExtractor(settings, urls=["https://example.com/report.pdf"])
    file_results = file_extractor.extract()

    # Almacenar todos los resultados
    all_results = api_results + web_results + file_results

    return all_results
```

### Caso 4: ETL con Transformación

**Escenario**: Extract → Transform → Load con parsers personalizados.

```python
from src.extractors.api_rest import APIRestExtractor
from src.parsers.json_parser import JSONParser

# Transform function
def transform_energy_data(raw_data):
    """Transformar y limpiar datos de energía."""
    return {
        "date": raw_data.get("fecha"),
        "consumption_mwh": float(raw_data.get("consumo", 0)),
        "generation_mwh": float(raw_data.get("generacion", 0)),
        "renewable_pct": float(raw_data.get("renovable_pct", 0)),
        # Calcular campo adicional
        "net_import": float(raw_data.get("consumo", 0)) - float(raw_data.get("generacion", 0)),
    }

# Pipeline
extractor = APIRestExtractor(settings)
raw_results = extractor.extract()

parser = JSONParser(transform_fn=transform_energy_data)

transformed_results = []
for result in raw_results:
    if result["error_message"]:
        continue

    parse_result = parser.parse(result["data"])
    if parse_result["parsing_successful"]:
        transformed_results.append(parse_result["parsed_data"])

# Store transformed data
# ...
```

---

## Recursos Adicionales

### Documentación

- **Extractores**: `docs/EXTRACTORS.md` - Guía completa de extractores
- **Parsers**: `docs/PARSERS.md` - Guía completa de parsers
- **Arquitectura**: `docs/ARCHITECTURE.md` - Diseño del sistema
- **Desarrollo**: `CLAUDE.md` - Guía de desarrollo con Claude Code

### Ejemplos en Código

- **REST API**: `examples/rest_api/`
- **Web Scraping**: `examples/web_scraping/`
- **File Processing**: `examples/file_processing/`

### APIs Públicas para Practicar

- JSONPlaceholder: https://jsonplaceholder.typicode.com
- REST Countries: https://restcountries.com
- CoinGecko: https://www.coingecko.com/en/api
- GitHub API: https://docs.github.com/en/rest

### Sitios para Scraping de Práctica

- Quotes to Scrape: http://quotes.toscrape.com
- Books to Scrape: http://books.toscrape.com
- Wikipedia: https://en.wikipedia.org

---

**¿Necesitas ayuda?** Consulta la documentación completa o revisa los ejemplos en el directorio `examples/`.
