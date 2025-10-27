##  Arquitectura de Fuentes Base

Este documento describe la arquitectura y diseño del sistema Fuentes Base.

## Visión General

Fuentes Base es una plantilla reutilizable para ingesta de datos multi-fuente diseñada con:
- **Modularidad**: Componentes independientes y reutilizables
- **Extensibilidad**: Fácil agregar nuevos tipos de extractores y parsers
- **Type-Safety**: Uso de type hints y pydantic para configuración
- **Append-Only**: Estrategia que preserva auditoría completa
- **Docker-Ready**: Contenedorización completa para portabilidad

## Capas de Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                 main.py (Orchestrator)                   │
│  - Coordina flujo completo                              │
│  - No contiene lógica de negocio                        │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
┌──────────────┬─────────────┬──────────────┐
│  Extractors  │   Parsers   │ Repositories │
│              │             │              │
│ - api_rest   │ - json      │ - raw_data   │
│ - web_static │ - pdf       │ - parsed_data│
│ - web_dynamic│ - xlsx      │              │
│ - file_dl    │ - csv/html  │              │
└──────┬───────┴──────┬──────┴──────┬───────┘
       │              │             │
       └──────────────┼─────────────┘
                      ↓
         ┌────────────────────────┐
         │    Core Utilities      │
         │                        │
         │ - http_client          │
         │ - database             │
         │ - logging              │
         └────────┬───────────────┘
                  ↓
         ┌────────────────────────┐
         │      MariaDB           │
         │  - raw_data            │
         │  - parsed_data         │
         └────────────────────────┘
```

### 1. Capa de Orquestación (main.py)

**Responsabilidad**: Coordinar el flujo completo sin lógica de negocio.

**Flujo**:
1. Cargar configuración (settings.py)
2. Inicializar base de datos
3. Ejecutar extractor apropiado según `source_type`
4. Almacenar resultados en BD via repositories
5. Reportar resumen

**Principio**: Un único punto de entrada, delegación a componentes especializados.

### 2. Capa de Extracción (extractors/)

**Responsabilidad**: Extraer datos crudos desde fuentes externas.

**Componentes**:
- `BaseExtractor` (ABC): Define interfaz común
- `APIRestExtractor`: APIs REST con httpx
- `WebStaticExtractor`: HTML estático con BeautifulSoup
- `WebDynamicExtractor`: JavaScript dinámico con Playwright
- `FileDownloadExtractor`: Descarga de archivos

**Contrato**:
```python
def extract(self) -> list[dict[str, Any]]:
    """
    Returns:
        [
            {
                "source_url": str,
                "status_code": int,
                "data": Any,
                "error_message": str | None,
                "extracted_at": str (ISO format)
            },
            ...
        ]
    """
```

**Principios**:
- Cada extractor es independiente
- Errores por fuente no detienen el proceso completo
- Resultados siempre en formato estandarizado
- No escriben a BD directamente (separation of concerns)

### 3. Capa de Parseo (parsers/)

**Responsabilidad**: Transformar datos crudos a formato estructurado.

**Componentes**:
- `BaseParser` (ABC): Define interfaz común
- `JSONParser`: Parseo y transformación de JSON
- `PDFParser`: Extracción de texto y tablas con pdfplumber
- `XLSXParser`: Lectura de Excel con openpyxl
- `CSVParser`: Parseo de archivos CSV
- `HTMLParser`: Extracción estructurada de HTML

**Contrato**:
```python
def parse(self, data: Any) -> dict[str, Any]:
    """
    Returns:
        {
            "parsing_successful": bool,
            "parsed_data": dict | None,
            "error_message": str | None,
            "metadata": dict
        }
    """
```

**Principios**:
- Parsers son funciones puras (sin side effects)
- No dependen de BD o HTTP
- Fácilmente testeables en aislamiento
- Extensibles via herencia

### 4. Capa de Repositorios (repositories/)

**Responsabilidad**: Interactuar con la base de datos.

**Componentes**:
- `BaseRepository`: Funcionalidad común (transactions)
- `RawDataRepository`: Operaciones sobre `raw_data` table
- `ParsedDataRepository`: Operaciones sobre `parsed_data` table

**Principios**:
- Única capa que accede a BD
- Encapsula queries SQL
- Provee API type-safe
- Maneja conversiones JSON ↔ Python

### 5. Capa Core (core/)

**Responsabilidad**: Utilidades fundamentales compartidas.

**Componentes**:
- `http_client.py`: Cliente HTTP con retries y timeout
- `database.py`: Gestor de conexiones y queries
- `logging.py`: Setup centralizado de logging

**Principios**:
- Sin dependencias entre core modules
- Configurables via Settings
- Reusables en cualquier capa superior

## Modelo de Datos

### Tabla: raw_data

Almacena TODOS los datos extraídos (append-only).

```sql
CREATE TABLE raw_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_url VARCHAR(2000),
    source_type ENUM(...),
    status_code INT,
    data JSON,
    error_message TEXT,
    extracted_at DATETIME,
    ...
)
```

**Características**:
- Nunca UPDATE/DELETE (preserva auditoría)
- Columna `data` es JSON (flexible)
- Índices en source_url, source_type, extracted_at
- Vistas pre-computadas (successful_extractions, latest_extractions)

### Tabla: parsed_data

Almacena resultados de parseo.

```sql
CREATE TABLE parsed_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    raw_data_id INT FK,
    parser_type ENUM(...),
    parsing_successful BOOLEAN,
    parsed_content JSON,
    error_message TEXT,
    parsed_at DATETIME,
    metadata JSON,
    ...
)
```

**Características**:
- 1:N relación con raw_data (un raw puede tener múltiples parseos)
- Permite re-parsear datos con diferentes parsers
- Metadata almacena info del parser (tipo, versión, etc.)

## Flujo de Datos

```
1. EXTRACCIÓN
   Fuente Externa → Extractor → List[ExtractionResult]

2. ALMACENAMIENTO
   List[ExtractionResult] → Repository → raw_data table

3. PARSEO (opcional)
   raw_data.data → Parser → ParseResult → parsed_data table

4. ANÁLISIS
   raw_data + parsed_data → SQL Queries → Insights
```

## Patrones de Diseño

### 1. Abstract Base Class (ABC)

**Uso**: BaseExtractor, BaseParser, BaseRepository

**Beneficio**: Garantiza interfaz consistente, facilita testing con mocks.

```python
class BaseExtractor(ABC):
    @abstractmethod
    def extract(self) -> list[dict]: ...
```

### 2. Factory Functions

**Uso**: `get_settings()`, `get_database_manager()`, `get_http_client()`

**Beneficio**: Encapsula creación de objetos, facilita dependency injection.

```python
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### 3. Repository Pattern

**Uso**: RawDataRepository, ParsedDataRepository

**Beneficio**: Abstrae acceso a datos, facilita cambio de BD.

```python
class RawDataRepository:
    def insert(self, source_url, ...) -> int: ...
    def get_by_id(self, id) -> dict: ...
```

### 4. Singleton Pattern

**Uso**: Settings

**Beneficio**: Configuración cargada una sola vez, reutilizada en toda la app.

## Configuración (settings.py)

**Approach**: Type-safe configuration con pydantic-settings.

```python
class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    ...

    # Source type
    source_type: Literal["api_rest", ...] | None = None

    # URLs (cargadas desde API_URL_1, API_URL_2, etc.)
    api_urls: list[str] = Field(default_factory=list)
    ...
```

**Beneficios**:
- Validación automática de tipos
- Valores default sensibles
- Carga desde .env o env vars
- Documentación inline

## Extensibilidad

### Agregar Nuevo Extractor

1. Crear `src/extractors/mi_extractor.py`
2. Heredar de `BaseExtractor`
3. Implementar `extract()`
4. Agregar en `main.py` al switch de `source_type`

```python
class MiExtractor(BaseExtractor):
    def extract(self) -> list[dict[str, Any]]:
        # Tu lógica aquí
        return results
```

### Agregar Nuevo Parser

1. Crear `src/parsers/mi_parser.py`
2. Heredar de `BaseParser`
3. Implementar `parse()`

```python
class MiParser(BaseParser):
    def parse(self, data: Any) -> dict[str, Any]:
        # Tu lógica aquí
        return result
```

### Agregar Nueva Tabla

1. Crear migración en `db/migrations/XXX_descripcion.sql`
2. Crear repository en `src/repositories/mi_tabla.py`
3. Actualizar `main.py` si es necesario

## Manejo de Errores

### Estrategia: "Fail Gracefully"

**Principios**:
- Errores por fuente individual no detienen el proceso completo
- Todos los errores se loggean con nivel apropiado
- Errores se almacenan en BD (columna `error_message`)
- Errores críticos (BD no disponible) sí detienen ejecución

**Ejemplo**:
```python
for url in urls:
    try:
        result = extract_single(url)
    except Exception as e:
        # Log error pero continúa con siguiente URL
        logger.error(f"Failed {url}: {e}")
        result = {"error_message": str(e), ...}

    results.append(result)  # Siempre agregamos resultado
```

## Logging

**Setup**: Centralizado en `core/logging.py`

**Niveles**:
- DEBUG: Detalles de ejecución (queries SQL, etc.)
- INFO: Progreso normal (extracciones exitosas)
- WARNING: Situaciones anómalas pero recuperables
- ERROR: Errores que requieren atención
- CRITICAL: Errores fatales

**Outputs**:
- Consola (stdout): Siempre habilitado
- Archivo: Opcional via `LOG_FILE` en .env

## Testing (futuro)

**Estrategia sugerida**:

1. **Unit Tests**: Parsers (funciones puras, fácil testear)
2. **Integration Tests**: Extractors + HTTP mocks
3. **Database Tests**: Repositories con BD de test

**Estructura**:
```
tests/
├── unit/
│   ├── test_parsers.py
│   └── test_extractors.py
├── integration/
│   └── test_extraction_flow.py
└── fixtures/
    ├── sample.pdf
    └── sample.xlsx
```

## Deployment

**Desarrollo Local**:
```bash
docker-compose up -d base_db
python -m src.main
```

**Producción**:
```bash
docker build -t fuentes-base:latest .
docker run --env-file .env fuentes-base:latest
```

**Scheduling con Cron**:
```cron
0 * * * * cd /path && docker-compose run --rm base_app
```

## Performance Considerations

1. **Batch Operations**: `insert_many()` en repositories
2. **Database Indexes**: En columnas de query frecuente
3. **Connection Pooling**: Reutilizar conexión en mismo proceso
4. **Async Extractors**: Usar `fetch_url_async()` para paralelismo (futuro)

## Seguridad

1. **Credentials**: Nunca hardcodear, siempre via env vars
2. **SQL Injection**: Usar parámetros en queries (`%s` placeholders)
3. **Secrets en Logs**: Evitar loggear passwords, tokens
4. **Docker**: Ejecutar con usuario no-root (best practice)

## Resumen

Fuentes Base implementa una arquitectura en capas con clara separación de responsabilidades:

- **Orchestrator** (main.py): Coordina
- **Extractors**: Obtienen datos
- **Parsers**: Transforman datos
- **Repositories**: Persisten datos
- **Core**: Provee utilidades

Esta arquitectura facilita:
- Mantenibilidad (cada componente es simple)
- Testeabilidad (componentes desacoplados)
- Extensibilidad (agregar nuevos extractores/parsers)
- Escalabilidad (fácil paralelizar extractores)
