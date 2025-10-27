# Fuentes Base - Plantilla Multi-Fuente de Datos

Plantilla base reutilizable en Python para ingesta de datos desde múltiples tipos de fuentes: APIs REST, scraping web (estático y dinámico con JavaScript), descarga y parseo de archivos (PDF, XLSX, CSV), con almacenamiento en MariaDB.

## Características

- 🌐 **Multi-Fuente**: Soporte para APIs REST, scraping web estático/dinámico, descarga de archivos
- 📄 **Multi-Formato**: Parseo de JSON, PDF, XLSX, CSV, HTML
- 🏗️ **Arquitectura Modular**: Extractores y parsers separados y extensibles
- 🔄 **Retry Logic**: Lógica de reintento con backoff exponencial
- 📦 **Append-Only Storage**: Estrategia de almacenamiento que preserva auditoría completa
- 🐳 **Docker-Ready**: Completamente contenedorizado
- ⚙️ **Type-Safe Config**: Configuración con pydantic-settings
- 📊 **MariaDB 10.11**: Almacenamiento confiable con soporte JSON
- 🎯 **Extensible**: Fácil agregar nuevos extractores y parsers

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│              Fuentes de Datos                            │
│  (APIs REST, Páginas Web, Archivos PDF/XLSX/CSV)        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    main.py Orchestrator      │
            │  (Pipeline configurable)     │
            └──────────────────────────────┘
                    ↙   ↓   ↘
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │Extractors│ │Parsers   │ │Repositories  │
        │(multi-   │ │(multi-   │ │(Database)    │
        │source)   │ │format)   │ │              │
        └──────────┘ └──────────┘ └──────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    MariaDB (10.11)           │
            │   raw_data (auditoría)       │
            │   extracted_data (parsed)    │
            └──────────────────────────────┘
```

## Tipos de Extractores Soportados

### 1. API REST (`api_rest`)
Extracción desde APIs REST con retry logic y manejo de JSON.

**Ejemplo**:
```python
from src.extractors.api_rest import APIRestExtractor

extractor = APIRestExtractor(urls=["https://api.example.com/data"])
results = extractor.extract()
```

### 2. Web Scraping Estático (`web_static`)
Scraping de páginas HTML server-side rendered usando BeautifulSoup.

**Ejemplo**:
```python
from src.extractors.web_static import WebStaticExtractor

extractor = WebStaticExtractor(urls=["https://example.com/page"])
results = extractor.extract()
```

### 3. Web Scraping Dinámico (`web_dynamic`)
Scraping de páginas con JavaScript usando Playwright (Chrome headless).

**Ejemplo**:
```python
from src.extractors.web_dynamic import WebDynamicExtractor

extractor = WebDynamicExtractor(
    urls=["https://example.com/dynamic"],
    wait_selector="div.content"
)
results = extractor.extract()
```

### 4. Descarga de Archivos (`file_download`)
Descarga de archivos (PDF, XLSX, CSV) desde URLs o S3.

**Ejemplo**:
```python
from src.extractors.file_download import FileDownloadExtractor

extractor = FileDownloadExtractor(
    urls=["https://example.com/file.pdf"],
    download_dir="downloads/"
)
results = extractor.extract()
```

## Tipos de Parsers Soportados

### 1. JSON Parser
Parseo y transformación de datos JSON.

### 2. PDF Parser
Extracción de texto y tablas de PDFs usando pdfplumber.

### 3. XLSX Parser
Lectura de archivos Excel con openpyxl.

### 4. CSV Parser
Parseo de archivos CSV.

### 5. HTML Parser
Extracción de datos desde HTML con BeautifulSoup.

## Quick Start

### Prerequisitos

- Docker y Docker Compose instalados
- Python 3.12+ (para desarrollo local)
- Git

### Setup

1. **Clonar o copiar esta plantilla**
   ```bash
   cd fuentes/
   cp -r base mi-nueva-fuente
   cd mi-nueva-fuente
   ```

2. **Crear archivo de configuración**
   ```bash
   cp .env.example .env
   ```

3. **Configurar tu fuente de datos**

   Editar `.env` y configurar según tu tipo de fuente:

   **Para API REST**:
   ```env
   SOURCE_TYPE=api_rest
   API_URL_1=https://api.example.com/v1/data
   API_URL_2=https://api.example.com/v1/users
   ```

   **Para scraping web**:
   ```env
   SOURCE_TYPE=web_static
   WEB_URL_1=https://example.com/page1
   WEB_URL_2=https://example.com/page2
   ```

4. **Iniciar la base de datos**
   ```bash
   docker-compose up -d base_db
   ```

   Esperar que la base de datos esté saludable (~30 segundos):
   ```bash
   docker-compose ps
   ```

5. **Ejecutar la ingesta**
   ```bash
   docker-compose run --rm base_app
   ```

## Estructura del Proyecto

```
fuentes/base/
├── src/
│   ├── main.py                    # Orquestador principal
│   ├── settings.py                # Configuración con pydantic
│   │
│   ├── core/                      # Utilidades core
│   │   ├── http_client.py         # Cliente HTTP con retries
│   │   ├── logging.py             # Setup de logging
│   │   └── database.py            # Gestor de base de datos
│   │
│   ├── extractors/                # Extractores por tipo
│   │   ├── base.py                # BaseExtractor (clase abstracta)
│   │   ├── api_rest.py            # Extractor para APIs REST
│   │   ├── web_static.py          # Scraping HTML estático
│   │   ├── web_dynamic.py         # Scraping JS dinámico (Playwright)
│   │   └── file_download.py       # Descarga de archivos
│   │
│   ├── parsers/                   # Parsers por formato
│   │   ├── base.py                # BaseParser (clase abstracta)
│   │   ├── json_parser.py         # Parser JSON
│   │   ├── pdf_parser.py          # Parser PDF (pdfplumber)
│   │   ├── xlsx_parser.py         # Parser XLSX (openpyxl)
│   │   ├── csv_parser.py          # Parser CSV
│   │   └── html_parser.py         # Parser HTML (BeautifulSoup)
│   │
│   ├── repositories/              # Repositorios de base de datos
│   │   ├── base.py                # BaseRepository
│   │   └── raw_data.py            # RawDataRepository
│   │
│   └── utils/                     # Utilidades
│       ├── retry.py               # Decorador de retry
│       └── helpers.py             # Helper functions
│
├── db/
│   ├── init.sql                   # Schema inicial
│   └── migrations/                # Migraciones de BD
│
├── docs/
│   ├── ARCHITECTURE.md            # Documentación de arquitectura
│   ├── EXTRACTORS.md              # Guía de extractores
│   ├── PARSERS.md                 # Guía de parsers
│   └── EXAMPLES.md                # Ejemplos de uso
│
├── examples/                      # Ejemplos completos
│   ├── rest_api/                  # Ejemplo con API REST
│   ├── web_scraping/              # Ejemplo con scraping
│   └── file_processing/           # Ejemplo con archivos
│
├── .env.example                   # Template de configuración
├── .gitignore
├── docker-compose.yml             # Orquestación de servicios
├── Dockerfile                     # Imagen de la aplicación
├── pyproject.toml                 # Dependencias Python
├── README.md                      # Este archivo
└── CLAUDE.md                      # Guía de desarrollo
```

## Uso

### Ejecución Manual

Ejecutar una ingesta única:
```bash
docker-compose run --rm base_app
```

### Programación con Cron

Agregar a crontab del sistema para ejecución periódica:

```bash
# Cada hora
0 * * * * cd /path/to/fuentes/base && docker-compose run --rm base_app

# Cada 6 horas
0 */6 * * * cd /path/to/fuentes/base && docker-compose run --rm base_app

# Diario a las 2 AM
0 2 * * * cd /path/to/fuentes/base && docker-compose run --rm base_app
```

### Ver Datos

Conectarse a la base de datos:

```bash
docker-compose exec base_db mysql -u base_user -pbase_password fuentes_base
```

Queries de ejemplo:
```sql
-- Ver todos los datos extraídos
SELECT * FROM raw_data ORDER BY fetched_at DESC LIMIT 10;

-- Ver extracciones exitosas únicamente
SELECT * FROM successful_extractions LIMIT 10;

-- Ver última extracción por URL
SELECT * FROM latest_extractions;

-- Contar extracciones por fuente
SELECT source_url, COUNT(*) as count
FROM raw_data
GROUP BY source_url;
```

## Desarrollo

### Desarrollo Local sin Docker

1. **Instalar uv** (si no está instalado):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Crear entorno virtual e instalar dependencias**:
   ```bash
   uv sync
   ```

3. **Activar entorno virtual**:
   ```bash
   source .venv/bin/activate  # Unix/macOS
   ```

4. **Ejecutar la aplicación**:
   ```bash
   python -m src.main
   ```

### Agregar Nuevo Extractor

1. Crear archivo en `src/extractors/mi_extractor.py`
2. Heredar de `BaseExtractor`
3. Implementar método `extract()`
4. Registrar en `settings.py` si es necesario

**Ejemplo**:
```python
from src.extractors.base import BaseExtractor

class MiExtractor(BaseExtractor):
    def extract(self) -> list[dict]:
        # Tu lógica aquí
        return results
```

### Agregar Nuevo Parser

1. Crear archivo en `src/parsers/mi_parser.py`
2. Heredar de `BaseParser`
3. Implementar método `parse()`
4. Registrar en configuración

**Ejemplo**:
```python
from src.parsers.base import BaseParser

class MiParser(BaseParser):
    def parse(self, data: Any) -> dict:
        # Tu lógica aquí
        return parsed_data
```

## Despliegue en Producción

Para despliegue en producción:

1. **Actualizar `.env` con credenciales de producción**:
   ```env
   DB_HOST=production.db.hostname
   DB_USER=production_user
   DB_PASSWORD=secure_password
   ```

2. **Build y run** (servicio de BD no necesario si usas BD externa):
   ```bash
   docker build -t fuentes-base:latest .
   docker run --env-file .env fuentes-base:latest
   ```

3. **Configurar cron** en el servidor para ejecución periódica

## Patrones y Convenciones

### Convenciones de Nombres
- **Base de datos**: `snake_case` (raw_data, source_url)
- **Archivos Python**: `snake_case` (http_client.py, api_rest.py)
- **Clases Python**: `PascalCase` (BaseExtractor, APIRestExtractor)
- **Constantes**: `SCREAMING_SNAKE_CASE` (MAX_RETRIES)

### Estrategia Append-Only
- Nunca UPDATE o DELETE de registros históricos
- Cada extracción crea nueva fila en `raw_data`
- Preserva auditoría completa de todas las operaciones

### Manejo de Errores
- Errores por URL no detienen la ejecución completa
- Errores de conexión a BD fallan rápido
- Todos los errores loggeados con niveles apropiados
- Operaciones batch trackean fallos separadamente

## Casos de Uso

Perfecto para:
- 📊 Iniciativas de datos abiertos
- 🏛️ Consumo de APIs gubernamentales
- 📈 Recolección de datos financieros
- 🌐 Agregación de datos multi-fuente
- 🔄 Sincronización regular de datos
- 📦 Construcción de data lakes desde APIs/web/archivos
- ⚡ Extracción de datos de la industria energética

## Documentación Adicional

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Documentación detallada de arquitectura
- [EXTRACTORS.md](docs/EXTRACTORS.md) - Guía completa de extractores
- [PARSERS.md](docs/PARSERS.md) - Guía completa de parsers
- [EXAMPLES.md](docs/EXAMPLES.md) - Ejemplos prácticos de uso

## Licencia

*(Agregar licencia aquí)*

## Contribuciones

*(Agregar guías de contribución aquí)*
