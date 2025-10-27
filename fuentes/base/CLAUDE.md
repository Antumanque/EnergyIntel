# Guía de Desarrollo con Claude Code

Esta guía describe cómo trabajar con este proyecto usando Claude Code.

## Contexto del Proyecto

**Fuentes Base** es una plantilla reutilizable para ingesta de datos multi-fuente:
- APIs REST
- Web scraping (estático y dinámico)
- Descarga y parseo de archivos (PDF, XLSX, CSV)
- Almacenamiento append-only en MariaDB

## Estructura del Proyecto

```
fuentes/base/
├── src/
│   ├── main.py              # Orquestador principal - PUNTO DE ENTRADA
│   ├── settings.py          # Configuración type-safe con pydantic
│   ├── core/                # Utilidades fundamentales
│   │   ├── http_client.py   # Cliente HTTP con retries
│   │   ├── database.py      # Gestor de BD
│   │   └── logging.py       # Setup de logging
│   ├── extractors/          # Extractores por tipo de fuente
│   │   ├── base.py          # BaseExtractor (ABC)
│   │   ├── api_rest.py
│   │   ├── web_static.py
│   │   ├── web_dynamic.py
│   │   └── file_download.py
│   ├── parsers/             # Parsers por formato
│   │   ├── base.py          # BaseParser (ABC)
│   │   ├── json_parser.py
│   │   ├── pdf_parser.py
│   │   ├── xlsx_parser.py
│   │   ├── csv_parser.py
│   │   └── html_parser.py
│   ├── repositories/        # Acceso a base de datos
│   │   ├── base.py
│   │   └── raw_data.py
│   └── utils/               # Utilidades varias
├── db/
│   ├── init.sql             # Schema inicial
│   └── migrations/          # Migraciones versionadas
├── docs/
│   ├── ARCHITECTURE.md      # Documentación de arquitectura
│   └── ...
├── examples/                # Ejemplos de uso
├── .env.example             # Template de configuración
├── docker-compose.yml       # Orquestación de servicios
├── Dockerfile
└── pyproject.toml          # Dependencias
```

## Arquitectura en Capas

```
main.py (Orquestador)
    ↓
extractors/ + parsers/ + repositories/
    ↓
core/ (http_client, database, logging)
    ↓
MariaDB
```

**Principio clave**: Separación de responsabilidades - cada capa tiene un propósito único.

## Tareas Comunes

### 1. Agregar Nuevo Extractor

**Escenario**: Necesito extraer datos desde un nuevo tipo de fuente (ej. GraphQL API, FTP, S3).

**Pasos**:

1. Crear archivo en `src/extractors/mi_extractor.py`
2. Heredar de `BaseExtractor`
3. Implementar método `extract()` que retorne:
   ```python
   list[dict[str, Any]]  # Con keys: source_url, status_code, data, error_message, extracted_at
   ```
4. Agregar nuevo source_type en `settings.py` (Literal)
5. Agregar case en `main.py` método `run_extraction()`

**Template**:
```python
# src/extractors/mi_extractor.py
from src.extractors.base import BaseExtractor
from datetime import datetime, timezone

class MiExtractor(BaseExtractor):
    def extract(self) -> list[dict[str, Any]]:
        results = []
        for source in self.sources:
            try:
                data = self._extract_single(source)
                results.append({
                    "source_url": source,
                    "status_code": 200,
                    "data": data,
                    "error_message": None,
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                results.append({
                    "source_url": source,
                    "status_code": 0,
                    "data": None,
                    "error_message": str(e),
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
        return results
```

### 2. Agregar Nuevo Parser

**Escenario**: Necesito parsear un nuevo formato de archivo (ej. XML, YAML, Parquet).

**Pasos**:

1. Crear archivo en `src/parsers/mi_parser.py`
2. Heredar de `BaseParser`
3. Implementar método `parse()` que retorne:
   ```python
   dict[str, Any]  # Con keys: parsing_successful, parsed_data, error_message, metadata
   ```

**Template**:
```python
# src/parsers/mi_parser.py
from src.parsers.base import BaseParser

class MiParser(BaseParser):
    def parse(self, data: Any) -> dict[str, Any]:
        try:
            # Tu lógica de parseo aquí
            parsed = self._parse_logic(data)

            return {
                "parsing_successful": True,
                "parsed_data": parsed,
                "error_message": None,
                "metadata": {"parser_type": "mi_formato"}
            }
        except Exception as e:
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "mi_formato"}
            }
```

### 3. Modificar Schema de Base de Datos

**Escenario**: Necesito agregar una nueva tabla o columna.

**Pasos**:

1. Crear migración en `db/migrations/XXX_descripcion.sql`
2. Número de migración debe ser secuencial (ej. 001, 002, 003)
3. Agregar INSERT a `schema_migrations` al final del archivo
4. Si necesitas repository, crear en `src/repositories/`

**Template de migración**:
```sql
-- db/migrations/001_add_nueva_tabla.sql

CREATE TABLE IF NOT EXISTS nueva_tabla (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campo1 VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_campo1 (campo1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Track migration
INSERT INTO schema_migrations (migration_name)
VALUES ('001_add_nueva_tabla.sql')
ON DUPLICATE KEY UPDATE migration_name=migration_name;
```

### 4. Debugging

**Escenario**: Algo no funciona y necesito entender qué está pasando.

**Acciones**:

1. **Revisar logs**: Los logs tienen toda la info de ejecución
   ```bash
   # Ver logs en tiempo real
   docker-compose logs -f base_app

   # Ver logs de BD
   docker-compose logs base_db
   ```

2. **Aumentar nivel de logging**: Editar `.env`
   ```env
   LOG_LEVEL=DEBUG  # En vez de INFO
   ```

3. **Probar query en BD directamente**:
   ```bash
   docker-compose exec base_db mysql -u base_user -pbase_password fuentes_base

   # Luego ejecutar queries:
   SELECT * FROM raw_data ORDER BY extracted_at DESC LIMIT 5;
   SELECT * FROM extraction_statistics;
   ```

4. **Ejecutar sin Docker** (más fácil para debug):
   ```bash
   # Iniciar solo la BD
   docker-compose up -d base_db

   # Ejecutar app localmente
   uv sync
   source .venv/bin/activate
   python -m src.main
   ```

### 5. Testing

**Escenario**: Quiero testear un parser o extractor de forma aislada.

**Approach**:

1. Para parsers (funciones puras, sin dependencias):
   ```python
   # test_mi_parser.py
   from src.parsers.mi_parser import MiParser

   def test_parse_valid_data():
       parser = MiParser()
       result = parser.parse("valid data")
       assert result["parsing_successful"] == True
       assert result["parsed_data"] is not None
   ```

2. Para extractors (con dependencias):
   ```python
   # test_mi_extractor.py
   from src.extractors.mi_extractor import MiExtractor
   from src.settings import Settings

   def test_extract():
       settings = Settings()  # Carga desde .env.test
       extractor = MiExtractor(settings)
       results = extractor.extract()
       assert len(results) > 0
   ```

## Convenciones de Código

### Naming

- **Archivos**: `snake_case.py`
- **Clases**: `PascalCase`
- **Funciones/variables**: `snake_case`
- **Constantes**: `SCREAMING_SNAKE_CASE`

### Imports

```python
# Standard library
import logging
from datetime import datetime

# Third-party
import httpx
from bs4 import BeautifulSoup

# Local
from src.core.http_client import HTTPClient
from src.settings import Settings
```

### Type Hints

Usar type hints en todos los métodos públicos:

```python
def fetch_url(self, url: str) -> tuple[int, Any | None, str | None]:
    ...
```

### Docstrings

Usar docstrings estilo Google para clases y métodos públicos:

```python
def insert(self, data: dict) -> int:
    """
    Insertar un registro en la tabla.

    Args:
        data: Diccionario con los datos a insertar

    Returns:
        ID del registro insertado

    Raises:
        MySQLError: Si falla la inserción
    """
```

## Configuración

**Archivo**: `.env` (copiar desde `.env.example`)

**Variables principales**:

```env
# Base de datos
DB_HOST=localhost
DB_PORT=3306
DB_USER=base_user
DB_PASSWORD=base_password
DB_NAME=fuentes_base

# Tipo de fuente
SOURCE_TYPE=api_rest  # o web_static, web_dynamic, file_download

# URLs (según tipo de fuente)
API_URL_1=https://api.example.com/data
API_URL_2=https://api.example.com/users

# Configuración HTTP
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Workflow de Desarrollo

### Setup Inicial

```bash
# 1. Copiar template de config
cp .env.example .env

# 2. Editar .env con tu configuración
vim .env

# 3. Iniciar BD
docker-compose up -d base_db

# 4. Esperar que BD esté ready
docker-compose ps

# 5. Instalar dependencias
uv sync

# 6. Activar venv
source .venv/bin/activate

# 7. Ejecutar aplicación
python -m src.main
```

### Desarrollo Iterativo

```bash
# 1. Hacer cambios en código

# 2. Ejecutar para probar
python -m src.main

# 3. Revisar logs y resultados

# 4. Repetir
```

### Deployment

```bash
# 1. Construir imagen
docker build -t fuentes-base:latest .

# 2. Probar localmente
docker-compose up

# 3. Push a registry (si aplica)
docker push mi-registry/fuentes-base:latest

# 4. Deploy en servidor
docker run --env-file .env fuentes-base:latest
```

## Troubleshooting

### Error: "Table 'raw_data' does not exist"

**Causa**: Schema de BD no inicializado.

**Solución**:
```bash
docker-compose exec base_db mysql -u base_user -pbase_password fuentes_base < db/init.sql
```

### Error: "Connection refused" o "Can't connect to MySQL"

**Causa**: BD no está corriendo o no está ready.

**Solución**:
```bash
# Verificar estado
docker-compose ps

# Si no está corriendo, iniciar
docker-compose up -d base_db

# Esperar ~30 segundos y retry
```

### Error: "No source_type configured"

**Causa**: Variable `SOURCE_TYPE` no está en `.env`.

**Solución**:
```bash
# Editar .env y agregar:
SOURCE_TYPE=api_rest  # o el tipo que necesites
```

### Playwright no funciona en Docker

**Causa**: Falta instalación de browsers.

**Solución**: El Dockerfile ya incluye `playwright install chromium`. Si falla, verificar que el build sea reciente:
```bash
docker-compose build --no-cache base_app
```

## Best Practices

1. **Siempre usar .env**: Nunca hardcodear credenciales
2. **Loggear apropiadamente**: INFO para progreso, ERROR para fallos
3. **Validar entrada**: Usar type hints y pydantic
4. **Manejar errores**: Try/except en extractors, retornar error en result
5. **Documentar código**: Docstrings en métodos públicos
6. **Append-only**: Nunca UPDATE/DELETE en raw_data
7. **Índices en BD**: Agregar índices en columnas de query frecuente

## Recursos

- **Documentación detallada**: `docs/ARCHITECTURE.md`
- **Schema de BD**: `db/init.sql`
- **Ejemplos**: `examples/` (cuando estén disponibles)
- **Issues**: GitHub issues del proyecto

## Preguntas Frecuentes

**Q: ¿Cómo agrego soporte para autenticación en APIs?**

A: Modifica `APIRestExtractor` para aceptar headers custom:
```python
extractor = APIRestExtractor(
    settings,
    headers={"Authorization": f"Bearer {token}"}
)
```

**Q: ¿Puedo usar múltiples tipos de fuentes simultáneamente?**

A: No en el flujo default. Cada ejecución procesa un `source_type`. Para múltiples fuentes, ejecuta múltiples veces con diferentes configs o modifica `main.py` para soportar múltiples extractors.

**Q: ¿Cómo parseo automáticamente archivos descargados?**

A: Agrega lógica en `main.py` después de `store_results()`:
```python
if self.settings.auto_parse:
    self.parse_downloaded_files()
```

**Q: ¿Soporte para APIs con paginación?**

A: Hereda de `APIRestExtractor` y sobrescribe `extract()` con lógica de paginación.

---

**Happy coding with Claude!** 🚀
