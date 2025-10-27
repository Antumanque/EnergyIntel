# Ejemplo: Web Scraping Estático

Este ejemplo muestra cómo extraer datos desde páginas HTML server-side rendered usando BeautifulSoup.

## Caso de Uso

Extraer información de sitios web estáticos (HTML puro, sin JavaScript):
- Páginas de noticias
- Sitios gubernamentales
- Directorios públicos
- Páginas informativas

## Ejemplo 1: Scraping de Wikipedia

### Configuración

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=base_user
DB_PASSWORD=base_password
DB_NAME=fuentes_base

# Source type
SOURCE_TYPE=web_static

# URLs de Wikipedia para scraping
WEB_URL_1=https://en.wikipedia.org/wiki/Python_(programming_language)
WEB_URL_2=https://en.wikipedia.org/wiki/Web_scraping
WEB_URL_3=https://en.wikipedia.org/wiki/Data_science

# HTTP Configuration
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

### Ejecución

```bash
# Copiar configuración
cp examples/web_scraping/.env.example .env

# Iniciar BD
docker-compose up -d base_db
sleep 30

# Ejecutar scraping
docker-compose run --rm base_app
```

### Resultado Esperado

```
2025-10-24 12:00:00 - INFO - Starting web static extraction for 3 URL(s)
2025-10-24 12:00:01 - INFO - Successfully parsed HTML from https://en.wikipedia.org/wiki/Python...
2025-10-24 12:00:02 - INFO - Successfully extracted from https://en.wikipedia.org/wiki/Python...
...
======================================================================
INGESTION SUMMARY
======================================================================
Source type: web_static
Total extractions: 3
Successful: 3
Failed: 0
======================================================================
```

### Verificar Datos

```sql
-- Ver datos extraídos
SELECT
    id,
    source_url,
    JSON_EXTRACT(data, '$.title') as page_title,
    JSON_LENGTH(data, '$.links') as num_links,
    extracted_at
FROM raw_data
WHERE source_type = 'web_static'
ORDER BY extracted_at DESC;

-- Ver headings de una página
SELECT JSON_PRETTY(JSON_EXTRACT(data, '$.headings'))
FROM raw_data
WHERE source_url LIKE '%Python%'
LIMIT 1;

-- Ver links extraídos
SELECT JSON_PRETTY(JSON_EXTRACT(data, '$.links'))
FROM raw_data
WHERE source_url LIKE '%Web_scraping%'
LIMIT 1;
```

## Ejemplo 2: Scraping Customizado

Para scraping más específico, hereda de `WebStaticExtractor` y sobrescribe `_parse_html_content()`:

### 1. Crear extractor personalizado

```python
# examples/web_scraping/custom_extractor.py
from src.extractors.web_static import WebStaticExtractor
from bs4 import BeautifulSoup

class NewsExtractor(WebStaticExtractor):
    """Extractor customizado para sitios de noticias."""

    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        # Extraer datos específicos del sitio de noticias
        articles = []
        for article in soup.find_all("article"):
            title_tag = article.find("h2")
            summary_tag = article.find("p", class_="summary")
            date_tag = article.find("time")

            articles.append({
                "title": title_tag.get_text(strip=True) if title_tag else None,
                "summary": summary_tag.get_text(strip=True) if summary_tag else None,
                "date": date_tag.get("datetime") if date_tag else None,
            })

        return {
            "site_name": soup.find("meta", property="og:site_name")["content"]
                         if soup.find("meta", property="og:site_name") else None,
            "articles": articles,
            "num_articles": len(articles),
        }
```

### 2. Usar el extractor personalizado

```python
# Modificar src/main.py temporalmente para testing
from examples.web_scraping.custom_extractor import NewsExtractor

# En run_extraction()
elif source_type == "web_static":
    # Usar extractor customizado
    extractor = NewsExtractor(self.settings)
    self.extraction_results = extractor.extract()
```

## Ejemplo 3: Scraping de Tabla HTML

Si necesitas extraer tablas específicas:

```python
# examples/web_scraping/table_extractor.py
from src.extractors.web_static import WebStaticExtractor
from bs4 import BeautifulSoup

class TableExtractor(WebStaticExtractor):
    """Extractor para tablas HTML."""

    def __init__(self, settings, urls=None, table_selector=None):
        super().__init__(settings, urls, parse_html=True)
        self.table_selector = table_selector or "table"

    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        tables_data = []
        for table in soup.select(self.table_selector):
            # Extraer headers
            headers = []
            header_row = table.find("thead")
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all("th")]

            # Extraer rows
            rows = []
            tbody = table.find("tbody") or table
            for tr in tbody.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)

            tables_data.append({
                "headers": headers,
                "rows": rows,
                "num_rows": len(rows),
            })

        return {
            "tables": tables_data,
            "num_tables": len(tables_data),
        }
```

**Uso**:
```python
from examples.web_scraping.table_extractor import TableExtractor

extractor = TableExtractor(
    settings,
    urls=["https://example.com/data-table"],
    table_selector="table.data-table"  # Selector CSS específico
)
results = extractor.extract()
```

## Sitios Recomendados para Scraping

### Sitios Públicos con Datos Estructurados

1. **Wikipedia**
   ```env
   WEB_URL_1=https://en.wikipedia.org/wiki/List_of_countries_by_population
   ```

2. **Quotes to Scrape** (sitio de práctica)
   ```env
   WEB_URL_1=http://quotes.toscrape.com/
   WEB_URL_2=http://quotes.toscrape.com/page/2/
   ```

3. **Books to Scrape** (sitio de práctica)
   ```env
   WEB_URL_1=http://books.toscrape.com/
   ```

4. **Hacker News**
   ```env
   WEB_URL_1=https://news.ycombinator.com/
   ```

## Buenas Prácticas

### 1. Respetar robots.txt

Siempre revisa el archivo `robots.txt` del sitio:
```
https://example.com/robots.txt
```

### 2. Rate Limiting

No hagas requests muy rápido. Agrega delays:

```python
# En _extract_single_url
import time
result = self._extract_single_url(url)
time.sleep(1)  # Esperar 1 segundo entre requests
```

### 3. User-Agent

Usa un User-Agent descriptivo (ya configurado en http_client.py):
```python
headers = {
    "User-Agent": "FuentesBase/1.0 (Educational Purpose; contact@example.com)"
}
```

### 4. Manejo de Errores

El extractor ya maneja errores HTTP, pero para sitios específicos puedes agregar lógica:

```python
def _extract_single_url(self, url: str) -> dict:
    result = super()._extract_single_url(url)

    # Verificar si el sitio bloqueó el request
    if result["status_code"] == 403:
        logger.warning(f"Access forbidden to {url} - site may be blocking scrapers")

    return result
```

## Limitaciones del Scraping Estático

**Web Static NO funciona para**:
- Sitios con contenido cargado via JavaScript
- SPAs (Single Page Applications) como React/Vue/Angular
- Sitios que requieren interacción (clicks, scrolls)
- Contenido detrás de login

Para estos casos, usa `web_dynamic` con Playwright (ver ejemplo siguiente).

## Troubleshooting

**Error: "HTML parsing failed"**
- El HTML puede estar malformado
- Prueba con parser diferente: `BeautifulSoup(html, "html.parser")`

**Datos vacíos extraídos**
- Los selectores CSS pueden haber cambiado
- Usa `print(soup.prettify())` para inspeccionar el HTML

**Error: 403 Forbidden**
- El sitio está bloqueando scrapers
- Intenta con User-Agent diferente
- Considera usar Playwright (web_dynamic)

**Contenido no aparece**
- El contenido puede estar cargado con JavaScript
- Usa `web_dynamic` en vez de `web_static`
