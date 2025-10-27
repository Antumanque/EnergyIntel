# Web Scraping Dinámico (JavaScript)

Este documento describe cómo usar el extractor `web_dynamic` para sitios con JavaScript.

## Cuándo Usar Web Dynamic

Usa `web_dynamic` cuando:
- El contenido se carga con JavaScript después del page load
- La página es una SPA (Single Page Application)
- Necesitas esperar a que elementos específicos aparezcan
- El sitio usa frameworks como React, Vue, Angular

## Configuración

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=base_user
DB_PASSWORD=base_password
DB_NAME=fuentes_base

# Source type
SOURCE_TYPE=web_dynamic

# URLs con contenido dinámico
WEB_URL_1=https://example.com/dynamic-page

# Playwright Configuration
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_SLOW_MO=0
PLAYWRIGHT_TIMEOUT=30000

# HTTP Configuration
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Ejemplo Básico

El extractor `web_dynamic` usa Playwright para cargar páginas completas:

```bash
# Ejecutar con la configuración dynamic
docker-compose run --rm base_app
```

## Esperar por Selector Específico

Si necesitas esperar a que un elemento específico aparezca:

```python
from src.extractors.web_dynamic import WebDynamicExtractor

# Esperar por un selector específico
extractor = WebDynamicExtractor(
    settings,
    urls=["https://example.com/page"],
    wait_selector="div.content-loaded"  # Espera este selector
)
results = extractor.extract()
```

## Ejemplo Avanzado: Custom Dynamic Extractor

Para interacciones más complejas, hereda de `WebDynamicExtractor`:

```python
# examples/web_scraping/advanced_dynamic.py
from src.extractors.web_dynamic import WebDynamicExtractor
from playwright.sync_api import Browser

class AdvancedDynamicExtractor(WebDynamicExtractor):
    """Extractor con interacciones avanzadas."""

    def _extract_single_url(self, browser: Browser, url: str) -> dict:
        logger.info(f"Extracting from: {url}")

        page = browser.new_page()
        error_message = None
        data = None
        status_code = 0

        try:
            # Navigate
            response = page.goto(url, wait_until="networkidle")
            if response:
                status_code = response.status

            # Esperar por elemento específico
            page.wait_for_selector("button#load-more", timeout=10000)

            # Click en botón para cargar más contenido
            page.click("button#load-more")

            # Esperar a que cargue nuevo contenido
            page.wait_for_selector("div.new-content", timeout=10000)

            # Scroll down para cargar lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)  # Esperar 2 segundos

            # Extraer datos
            data = {
                "html": page.content(),
                "text": page.inner_text("body"),
                "title": page.title(),
                "url": page.url,
                # Custom extractions
                "items": page.eval_on_selector_all(
                    "div.item",
                    "elements => elements.map(e => e.textContent)"
                ),
            }

        except Exception as e:
            error_message = f"Extraction error: {str(e)}"
            logger.error(f"Error: {e}", exc_info=True)

        finally:
            page.close()

        return {
            "source_url": url,
            "status_code": status_code,
            "data": data,
            "error_message": error_message,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
```

## Casos de Uso Comunes

### 1. Scraping con Login

```python
def _extract_single_url(self, browser: Browser, url: str) -> dict:
    page = browser.new_page()

    # Login first
    page.goto("https://example.com/login")
    page.fill("input#username", "your_username")
    page.fill("input#password", "your_password")
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard")  # Esperar redirect

    # Ahora ir a la página target
    page.goto(url)
    # ... resto de la extracción
```

### 2. Infinite Scroll

```python
def _extract_single_url(self, browser: Browser, url: str) -> dict:
    page = browser.new_page()
    page.goto(url)

    # Scroll multiple times
    for _ in range(5):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

    data = {
        "html": page.content(),
        # ... extraer datos
    }
```

### 3. Tomar Screenshots

```python
def _extract_single_url(self, browser: Browser, url: str) -> dict:
    page = browser.new_page()
    page.goto(url)

    # Tomar screenshot
    screenshot_path = f"screenshots/{url.split('//')[-1]}.png"
    page.screenshot(path=screenshot_path)

    data = {
        "html": page.content(),
        "screenshot": screenshot_path,
    }
```

### 4. Manejar Popups/Modals

```python
def _extract_single_url(self, browser: Browser, url: str) -> dict:
    page = browser.new_page()
    page.goto(url)

    # Cerrar modal si aparece
    try:
        page.wait_for_selector("button.close-modal", timeout=5000)
        page.click("button.close-modal")
    except:
        pass  # No apareció modal

    # Continuar con extracción
    data = {"html": page.content()}
```

## Debugging

### Modo Headful (ver el browser)

```env
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_SLOW_MO=1000  # Slow down por 1 segundo por acción
```

### Capturar Eventos

```python
page = browser.new_page()

# Log console messages
page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))

# Log network requests
page.on("request", lambda request: print(f"REQUEST: {request.url}"))

# Log responses
page.on("response", lambda response: print(f"RESPONSE: {response.url} {response.status}"))

page.goto(url)
```

## Performance

Playwright es más lento que scraping estático. Tips para mejorar:

### 1. Block Recursos Innecesarios

```python
page = browser.new_page()

# Block images, fonts, etc.
page.route("**/*", lambda route: route.abort()
    if route.request.resource_type in ["image", "font", "stylesheet"]
    else route.continue_()
)

page.goto(url)
```

### 2. Usar Browser Context Pool

```python
# Reusar mismo browser para múltiples páginas
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)

    for url in urls:
        context = browser.new_context()  # Nuevo context (aislado)
        page = context.new_page()
        # ... extracción
        context.close()

    browser.close()
```

## Limitaciones

- **Más lento**: ~3-5 segundos por página vs. <1 segundo con static
- **Más recursos**: Usa Chrome headless (más memoria/CPU)
- **Complejidad**: Más difícil debuggear que static scraping

## Cuándo NO usar Web Dynamic

- Si el sitio funciona sin JavaScript → usa `web_static`
- Si hay API disponible → usa `api_rest`
- Si solo necesitas descargar archivos → usa `file_download`
