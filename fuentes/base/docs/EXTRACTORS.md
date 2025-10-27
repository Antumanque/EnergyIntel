# Guía de Extractores

Esta guía describe todos los extractores disponibles en Fuentes Base y cómo usarlos y extenderlos.

## Tabla de Contenidos

- [Conceptos Básicos](#conceptos-básicos)
- [BaseExtractor](#baseextractor)
- [APIRestExtractor](#apirestextractor)
- [WebStaticExtractor](#webstaticextractor)
- [WebDynamicExtractor](#webdynamicextractor)
- [FileDownloadExtractor](#filedownloadextractor)
- [Crear Extractor Personalizado](#crear-extractor-personalizado)
- [Best Practices](#best-practices)

---

## Conceptos Básicos

### ¿Qué es un Extractor?

Un **extractor** es un componente responsable de obtener datos crudos desde una fuente externa:
- APIs REST
- Páginas web (HTML estático o dinámico)
- Archivos descargables

### Contrato del Extractor

Todos los extractores deben:
1. Heredar de `BaseExtractor`
2. Implementar el método `extract()`
3. Retornar lista de dicts con formato estandarizado

**Formato de retorno**:
```python
[
    {
        "source_url": str,         # URL o identificador de la fuente
        "status_code": int,        # HTTP status o código custom (0 = fallo total)
        "data": Any,               # Datos extraídos (dict, str, bytes, etc.)
        "error_message": str | None,  # Error si hubo fallo
        "extracted_at": str        # Timestamp ISO format
    },
    ...
]
```

### Principios de Diseño

1. **Independencia**: Cada extractor es autónomo
2. **Resiliencia**: Errores individuales no detienen el proceso completo
3. **Idempotencia**: Mismo input → mismo output
4. **No Side Effects**: No escriben a BD directamente

---

## BaseExtractor

Clase base abstracta que define la interfaz común.

### Ubicación
```python
from src.extractors.base import BaseExtractor
```

### Interfaz

```python
class BaseExtractor(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.results: list[dict[str, Any]] = []

    @abstractmethod
    def extract(self) -> list[dict[str, Any]]:
        """Extraer datos desde la fuente."""
        pass

    def validate_result(self, result: dict[str, Any]) -> bool:
        """Validar formato del resultado."""
        pass

    def log_summary(self) -> None:
        """Loggear resumen de extracción."""
        pass
```

### Métodos Utilitarios

**`validate_result(result)`**
- Valida que un resultado tenga todos los campos requeridos
- Retorna `True` si es válido, `False` sino

**`log_summary()`**
- Imprime resumen de extracciones (total, exitosas, fallidas)
- Llamar al final de `extract()`

---

## APIRestExtractor

Extractor para APIs REST con soporte para JSON.

### Ubicación
```python
from src.extractors.api_rest import APIRestExtractor
```

### Características

- Cliente HTTP con retry automático (3 intentos por default)
- Exponential backoff entre retries (2s, 4s, 8s)
- Timeout configurable
- Parseo automático de JSON
- Manejo de errores HTTP

### Uso Básico

```python
from src.extractors.api_rest import APIRestExtractor
from src.settings import get_settings

settings = get_settings()
extractor = APIRestExtractor(settings)
results = extractor.extract()
```

### Configuración (.env)

```env
SOURCE_TYPE=api_rest
API_URL_1=https://api.example.com/endpoint1
API_URL_2=https://api.example.com/endpoint2
REQUEST_TIMEOUT=30
MAX_RETRIES=3
```

### URLs desde Código

```python
# Pasar URLs directamente (ignora settings.api_urls)
urls = [
    "https://api.example.com/users",
    "https://api.example.com/posts"
]
extractor = APIRestExtractor(settings, urls=urls)
results = extractor.extract()
```

### Ejemplo: API con Paginación

```python
from src.extractors.api_rest import APIRestExtractor

class PaginatedAPIExtractor(APIRestExtractor):
    def __init__(self, settings, base_url, max_pages=10):
        self.base_url = base_url
        self.max_pages = max_pages
        # Generar URLs paginadas
        urls = [f"{base_url}?page={i}" for i in range(1, max_pages + 1)]
        super().__init__(settings, urls=urls)
```

Uso:
```python
extractor = PaginatedAPIExtractor(
    settings,
    base_url="https://api.example.com/items",
    max_pages=5
)
results = extractor.extract()
```

### Ejemplo: API con Autenticación

```python
from src.extractors.api_rest import APIRestExtractor
from src.core.http_client import HTTPClient

class AuthenticatedAPIExtractor(APIRestExtractor):
    def __init__(self, settings, urls=None, token=None):
        super().__init__(settings, urls)
        self.token = token

    def _extract_single_url(self, url: str) -> dict:
        # Agregar header de autorización
        status_code, data, error_message = self.http_client.fetch_url(
            url,
            headers={"Authorization": f"Bearer {self.token}"}
        )

        return {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
```

### Métodos HTTP Personalizados

Para POST, PUT, etc., usa el http_client directamente:

```python
class PostAPIExtractor(APIRestExtractor):
    def _extract_single_url(self, url: str) -> dict:
        status_code, data, error_message = self.http_client.fetch_url(
            url,
            method="POST",
            json={"key": "value"},  # Body del POST
            headers={"Content-Type": "application/json"}
        )
        # ... resto del código
```

---

## WebStaticExtractor

Extractor para web scraping de HTML estático (server-side rendered) usando BeautifulSoup.

### Ubicación
```python
from src.extractors.web_static import WebStaticExtractor
```

### Características

- Scraping de HTML puro (sin JavaScript)
- Parseo automático con BeautifulSoup
- Extracción de estructura básica (title, meta, headings, links)
- Customizable via herencia

### Uso Básico

```python
from src.extractors.web_static import WebStaticExtractor

settings = get_settings()
extractor = WebStaticExtractor(settings)
results = extractor.extract()
```

### Configuración (.env)

```env
SOURCE_TYPE=web_static
WEB_URL_1=https://example.com/page1
WEB_URL_2=https://example.com/page2
```

### Deshabilitar Parseo HTML

```python
# Solo descargar HTML sin parsearlo
extractor = WebStaticExtractor(settings, parse_html=False)
results = extractor.extract()

# results[0]["data"] será el HTML crudo (string)
```

### Personalizar Parseo

El método `_parse_html_content()` es donde ocurre la extracción. Sobrescríbelo:

```python
from bs4 import BeautifulSoup
from src.extractors.web_static import WebStaticExtractor

class CustomWebExtractor(WebStaticExtractor):
    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        # Extracción personalizada
        articles = []
        for article in soup.find_all("article", class_="news-item"):
            articles.append({
                "title": article.find("h2").get_text(strip=True),
                "date": article.find("time")["datetime"],
                "author": article.find("span", class_="author").get_text(strip=True),
                "summary": article.find("p", class_="summary").get_text(strip=True),
            })

        return {
            "page_title": soup.title.string if soup.title else None,
            "articles": articles,
            "num_articles": len(articles),
        }
```

### Ejemplo: Extraer Tabla HTML

```python
class TableExtractor(WebStaticExtractor):
    def __init__(self, settings, urls=None, table_selector="table"):
        super().__init__(settings, urls, parse_html=True)
        self.table_selector = table_selector

    def _parse_html_content(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "lxml")

        table = soup.select_one(self.table_selector)
        if not table:
            return {"error": "Table not found"}

        # Extraer headers
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        # Extraer rows
        rows = []
        for tr in table.find_all("tr")[1:]:  # Skip header row
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                rows.append(dict(zip(headers, cells)))

        return {
            "headers": headers,
            "rows": rows,
            "num_rows": len(rows),
        }
```

---

## WebDynamicExtractor

Extractor para sitios con JavaScript usando Playwright (Chrome headless).

### Ubicación
```python
from src.extractors.web_dynamic import WebDynamicExtractor
```

### Características

- Carga completa de JavaScript
- Espera por selectores específicos
- Interacción con página (clicks, scrolls, input)
- Screenshots
- Manejo de SPAs (React, Vue, Angular)

### Uso Básico

```python
from src.extractors.web_dynamic import WebDynamicExtractor

settings = get_settings()
extractor = WebDynamicExtractor(settings)
results = extractor.extract()
```

### Configuración (.env)

```env
SOURCE_TYPE=web_dynamic
WEB_URL_1=https://example.com/dynamic-page

# Playwright config
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_SLOW_MO=0
PLAYWRIGHT_TIMEOUT=30000
```

### Esperar por Selector

```python
# Esperar hasta que un elemento específico aparezca
extractor = WebDynamicExtractor(
    settings,
    urls=["https://example.com"],
    wait_selector="div.content-loaded"
)
results = extractor.extract()
```

### Interacciones Avanzadas

```python
from playwright.sync_api import Browser
from src.extractors.web_dynamic import WebDynamicExtractor

class InteractiveExtractor(WebDynamicExtractor):
    def _extract_single_url(self, browser: Browser, url: str) -> dict:
        page = browser.new_page()
        error_message = None
        data = None

        try:
            # Navigate
            page.goto(url, wait_until="networkidle")

            # Click button to load more content
            page.click("button#load-more")
            page.wait_for_selector("div.new-content")

            # Fill form
            page.fill("input#search", "query text")
            page.click("button#submit")
            page.wait_for_url("**/results")

            # Scroll to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Extract data
            data = {
                "html": page.content(),
                "text": page.inner_text("body"),
                "title": page.title(),
                "items": page.eval_on_selector_all(
                    "div.item",
                    "elements => elements.map(e => e.textContent)"
                ),
            }

        except Exception as e:
            error_message = str(e)

        finally:
            page.close()

        return {
            "source_url": url,
            "status_code": 200 if data else 0,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
```

### Modo Headful (Debugging)

```env
PLAYWRIGHT_HEADLESS=false  # Ver el browser
PLAYWRIGHT_SLOW_MO=1000    # Ralentizar acciones
```

---

## FileDownloadExtractor

Extractor para descargar archivos desde URLs.

### Ubicación
```python
from src.extractors.file_download import FileDownloadExtractor
```

### Características

- Descarga de archivos (PDF, XLSX, CSV, ZIP, etc.)
- Organización en directorios
- Nombres de archivo personalizables
- Metadata de archivos (tamaño, content-type)

### Uso Básico

```python
from src.extractors.file_download import FileDownloadExtractor

settings = get_settings()
extractor = FileDownloadExtractor(settings)
results = extractor.extract()

# Archivos en downloads/
```

### Configuración (.env)

```env
SOURCE_TYPE=file_download
FILE_URL_1=https://example.com/file.pdf
FILE_URL_2=https://example.com/data.xlsx
DOWNLOAD_DIR=downloads
```

### Nombres de Archivo Custom

```python
extractor = FileDownloadExtractor(
    settings,
    urls=[
        "https://example.com/file1",
        "https://example.com/file2"
    ],
    file_names=[
        "report_2025.pdf",
        "data_january.xlsx"
    ]
)
results = extractor.extract()
```

### Directorio Custom

```python
extractor = FileDownloadExtractor(
    settings,
    download_dir="downloads/2025-10-24"
)
results = extractor.extract()
```

---

## Crear Extractor Personalizado

### Paso 1: Crear Archivo

```bash
touch src/extractors/mi_extractor.py
```

### Paso 2: Implementar Clase

```python
# src/extractors/mi_extractor.py
import logging
from datetime import datetime, timezone
from typing import Any

from src.extractors.base import BaseExtractor
from src.settings import Settings

logger = logging.getLogger(__name__)


class MiExtractor(BaseExtractor):
    """
    Descripción de tu extractor.
    """

    def __init__(self, settings: Settings, **kwargs):
        super().__init__(settings)
        # Inicializar parámetros específicos
        self.param1 = kwargs.get("param1")
        self.param2 = kwargs.get("param2")

    def extract(self) -> list[dict[str, Any]]:
        """
        Método principal de extracción.
        """
        logger.info(f"Starting extraction with {self.__class__.__name__}")

        self.results = []

        # Tu lógica de extracción aquí
        for source in self.sources:
            result = self._extract_single_source(source)
            self.results.append(result)

        self.log_summary()
        return self.results

    def _extract_single_source(self, source: Any) -> dict[str, Any]:
        """
        Extraer datos desde una sola fuente.
        """
        try:
            # Tu lógica aquí
            data = self._do_extraction(source)

            return {
                "source_url": str(source),
                "status_code": 200,
                "data": data,
                "error_message": None,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error extracting from {source}: {e}")

            return {
                "source_url": str(source),
                "status_code": 0,
                "data": None,
                "error_message": str(e),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

    def _do_extraction(self, source: Any) -> Any:
        """
        Lógica específica de extracción.
        """
        # Implementar aquí
        pass
```

### Paso 3: Registrar en main.py

```python
# src/main.py
from src.extractors.mi_extractor import MiExtractor

# En el método run_extraction()
elif source_type == "mi_tipo":
    extractor = MiExtractor(self.settings)
    self.extraction_results = extractor.extract()
```

### Paso 4: Agregar a settings.py

```python
# src/settings.py
source_type: Literal["api_rest", "web_static", "web_dynamic", "file_download", "mi_tipo"] | None
```

---

## Best Practices

### 1. Manejo de Errores

**DO**: Captura excepciones por fuente individual
```python
for url in urls:
    try:
        result = self._extract_single(url)
    except Exception as e:
        result = {"error_message": str(e), ...}
    results.append(result)
```

**DON'T**: Dejar que una excepción detenga todo
```python
for url in urls:
    result = self._extract_single(url)  # Si falla, se detiene todo
    results.append(result)
```

### 2. Logging

```python
# Level apropiado
logger.info("Starting extraction")      # Progreso normal
logger.warning("Unusual condition")     # Algo raro pero no crítico
logger.error("Failed to extract")       # Fallo que requiere atención
```

### 3. Timeouts

Siempre configura timeouts:
```python
response = client.get(url, timeout=30)
```

### 4. Rate Limiting

Para APIs con rate limits:
```python
import time

for url in urls:
    result = self._extract_single(url)
    results.append(result)
    time.sleep(1)  # Esperar 1 segundo entre requests
```

### 5. Validación de Datos

```python
def _extract_single(self, url):
    # ... extraction logic ...

    # Validar antes de retornar
    if not self.validate_result(result):
        logger.warning(f"Invalid result format for {url}")

    return result
```

### 6. Documentación

Documenta parámetros y comportamiento:
```python
class MiExtractor(BaseExtractor):
    """
    Extractor para [descripción].

    Args:
        settings: Configuración de la aplicación
        param1: Descripción de param1
        param2: Descripción de param2

    Example:
        >>> extractor = MiExtractor(settings, param1="value")
        >>> results = extractor.extract()
    """
```

### 7. Testing

Crea tests para tu extractor:
```python
# tests/test_mi_extractor.py
def test_mi_extractor():
    settings = Settings()
    extractor = MiExtractor(settings)
    results = extractor.extract()

    assert len(results) > 0
    assert all(r["source_url"] for r in results)
    assert all(r["status_code"] for r in results)
```

---

## Troubleshooting Común

**"Connection timeout"**
- Aumenta `REQUEST_TIMEOUT` en .env
- Verifica conectividad de red

**"Too many redirects"**
- La URL puede estar mal
- Verifica que `follow_redirects=True` esté configurado

**"403 Forbidden"**
- El sitio puede estar bloqueando scrapers
- Intenta con User-Agent diferente
- Considera usar Playwright (web_dynamic)

**"Rate limit exceeded"**
- Agrega delays entre requests
- Reduce número de URLs simultáneas

**"Memory issues"**
- No cargues todos los resultados en memoria
- Procesa y almacena en batches
- Cierra recursos (páginas, conexiones) explícitamente
