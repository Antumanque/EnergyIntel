# Ejemplo: Extracción desde API REST

Este ejemplo muestra cómo extraer datos desde APIs REST públicas.

## Caso de Uso

Extraer datos de la API JSONPlaceholder (API de prueba pública):
- Posts: https://jsonplaceholder.typicode.com/posts
- Users: https://jsonplaceholder.typicode.com/users
- Comments: https://jsonplaceholder.typicode.com/comments

## Configuración

### 1. Crear archivo `.env`

```bash
cd fuentes/base
cp .env.example .env
```

### 2. Editar `.env` con la configuración del ejemplo

```env
# Database (usar defaults o tu config)
DB_HOST=localhost
DB_PORT=3306
DB_USER=base_user
DB_PASSWORD=base_password
DB_NAME=fuentes_base

# Configuración de fuente
SOURCE_TYPE=api_rest

# URLs de la API JSONPlaceholder
API_URL_1=https://jsonplaceholder.typicode.com/posts
API_URL_2=https://jsonplaceholder.typicode.com/users
API_URL_3=https://jsonplaceholder.typicode.com/comments

# HTTP Config
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Ejecución

### Opción 1: Con Docker

```bash
# Iniciar base de datos
docker-compose up -d base_db

# Esperar ~30 segundos para que la BD esté ready
sleep 30

# Ejecutar extracción
docker-compose run --rm base_app
```

### Opción 2: Local (sin Docker)

```bash
# Iniciar solo la BD
docker-compose up -d base_db

# Instalar dependencias
uv sync
source .venv/bin/activate

# Ejecutar
python -m src.main
```

## Resultado Esperado

La aplicación extraerá datos desde las 3 URLs y los almacenará en `raw_data`:

```
2025-10-24 12:00:00 - INFO - Starting API REST extraction for 3 URL(s)
2025-10-24 12:00:01 - INFO - Successfully extracted from https://jsonplaceholder.typicode.com/posts
2025-10-24 12:00:02 - INFO - Successfully extracted from https://jsonplaceholder.typicode.com/users
2025-10-24 12:00:03 - INFO - Successfully extracted from https://jsonplaceholder.typicode.com/comments
2025-10-24 12:00:04 - INFO - Successfully stored 3 records in database

======================================================================
INGESTION SUMMARY
======================================================================
Source type: api_rest
Total extractions: 3
Successful: 3
Failed: 0
======================================================================
```

## Verificar Datos en Base de Datos

```bash
docker-compose exec base_db mysql -u base_user -pbase_password fuentes_base
```

```sql
-- Ver todos los datos extraídos
SELECT id, source_url, status_code, extracted_at
FROM raw_data
ORDER BY extracted_at DESC;

-- Ver datos de posts (primer URL)
SELECT JSON_PRETTY(data)
FROM raw_data
WHERE source_url LIKE '%posts%'
LIMIT 1;

-- Ver estadísticas
SELECT * FROM extraction_statistics;
```

## Personalización

### Agregar más URLs

Simplemente agrega más URLs en el `.env`:

```env
API_URL_4=https://jsonplaceholder.typicode.com/albums
API_URL_5=https://jsonplaceholder.typicode.com/photos
```

### Agregar autenticación

Si tu API requiere autenticación, modifica `src/extractors/api_rest.py`:

```python
class APIRestExtractor(BaseExtractor):
    def __init__(self, settings: Settings, urls: list[str] | None = None, headers: dict | None = None):
        super().__init__(settings)
        self.urls = urls or settings.api_urls
        self.http_client = get_http_client(settings)
        self.custom_headers = headers or {}

    def _extract_single_url(self, url: str) -> dict[str, Any]:
        # Pasar headers custom al http_client
        status_code, data, error_message = self.http_client.fetch_url(
            url,
            headers={**self.http_client.default_headers, **self.custom_headers}
        )
        ...
```

Luego en `main.py`:

```python
if source_type == "api_rest":
    # Agregar token de autorización
    headers = {"Authorization": f"Bearer {os.getenv('API_TOKEN')}"}
    extractor = APIRestExtractor(self.settings, headers=headers)
    self.extraction_results = extractor.extract()
```

### Transformar datos antes de almacenar

Usa el `JSONParser` para transformar los datos:

```python
from src.parsers.json_parser import JSONParser

# Definir función de transformación
def transform_posts(data):
    if isinstance(data, list):
        return [{"id": p["id"], "title": p["title"]} for p in data]
    return data

# Usar parser con transformación
parser = JSONParser(transform_fn=transform_posts)
result = parser.parse(raw_data)
```

## APIs Reales de Ejemplo

Aquí hay algunas APIs públicas que puedes usar:

### 1. REST Countries
```env
API_URL_1=https://restcountries.com/v3.1/all
API_URL_2=https://restcountries.com/v3.1/region/americas
```

### 2. OpenWeather (requiere API key)
```env
API_URL_1=https://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_API_KEY
```

### 3. GitHub Public API
```env
API_URL_1=https://api.github.com/repos/python/cpython
API_URL_2=https://api.github.com/users/torvalds
```

### 4. CoinGecko (crypto prices)
```env
API_URL_1=https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd
```

## Troubleshooting

**Error: "Connection refused"**
- Asegúrate de que la BD esté corriendo: `docker-compose ps`
- Espera más tiempo para que la BD esté lista

**Error: "No API URLs configured"**
- Verifica que `API_URL_1`, `API_URL_2`, etc. estén en `.env`
- Verifica que `SOURCE_TYPE=api_rest` esté configurado

**Error: HTTP 429 (Too Many Requests)**
- La API tiene rate limiting
- Agrega `time.sleep(1)` entre requests en el extractor

**Datos vacíos en la BD**
- Verifica que las URLs sean correctas
- Revisa los logs para ver errores específicos
