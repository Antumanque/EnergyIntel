# Ejemplo: Descarga y Procesamiento de Archivos

Este ejemplo muestra cómo descargar y procesar archivos (PDF, XLSX, CSV) desde URLs.

## Caso de Uso

Descargar archivos desde:
- URLs públicas de reportes (PDF)
- Datasets en Excel/CSV
- Archivos desde S3 con URLs prefirmadas
- Documentos gubernamentales

## Configuración

### Descarga Simple

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=base_user
DB_PASSWORD=base_password
DB_NAME=fuentes_base

# Source type
SOURCE_TYPE=file_download

# URLs de archivos para descargar
FILE_URL_1=https://example.com/report.pdf
FILE_URL_2=https://example.com/data.xlsx
FILE_URL_3=https://example.com/dataset.csv

# Download directory
DOWNLOAD_DIR=downloads

# HTTP Configuration
REQUEST_TIMEOUT=60  # Mayor timeout para archivos grandes
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Ejecución

```bash
# Copiar configuración
cp examples/file_processing/.env.example .env

# Iniciar BD
docker-compose up -d base_db
sleep 30

# Ejecutar descarga
docker-compose run --rm base_app
```

## Resultado Esperado

```
2025-10-24 12:00:00 - INFO - Starting file download for 3 file(s)
2025-10-24 12:00:01 - INFO - Successfully downloaded report.pdf (245678 bytes)
2025-10-24 12:00:03 - INFO - Successfully downloaded data.xlsx (123456 bytes)
2025-10-24 12:00:04 - INFO - Successfully downloaded dataset.csv (89012 bytes)
2025-10-24 12:00:05 - INFO - Successfully stored 3 records in database

======================================================================
INGESTION SUMMARY
======================================================================
Source type: file_download
Total extractions: 3
Successful: 3
Failed: 0
======================================================================
```

Los archivos estarán en `downloads/`:
```
downloads/
├── report.pdf
├── data.xlsx
└── dataset.csv
```

## Verificar Datos en BD

```sql
-- Ver archivos descargados
SELECT
    id,
    source_url,
    JSON_EXTRACT(data, '$.file_name') as file_name,
    JSON_EXTRACT(data, '$.file_size_bytes') as size_bytes,
    JSON_EXTRACT(data, '$.content_type') as content_type,
    extracted_at
FROM raw_data
WHERE source_type = 'file_download'
ORDER BY extracted_at DESC;

-- Ver metadata completa de un archivo
SELECT JSON_PRETTY(data)
FROM raw_data
WHERE source_url LIKE '%report.pdf%';
```

## Parseo Automático de Archivos

### 1. Parsear PDFs

Después de descargar, parsea el PDF:

```python
from src.parsers.pdf_parser import PDFParser
from pathlib import Path

# Obtener ruta del archivo descargado desde raw_data
file_path = "downloads/report.pdf"

# Parsear
parser = PDFParser()
result = parser.parse(file_path)

if result["parsing_successful"]:
    print(f"Text: {result['parsed_data']['text'][:500]}")
    print(f"Tables: {len(result['parsed_data']['tables'])}")
    print(f"Pages: {result['metadata']['num_pages']}")
```

### 2. Parsear XLSX

```python
from src.parsers.xlsx_parser import XLSXParser

parser = XLSXParser(sheet_name="Sheet1")
result = parser.parse("downloads/data.xlsx")

if result["parsing_successful"]:
    rows = result["parsed_data"]["rows"]
    print(f"Rows: {len(rows)}")
    print(f"First row: {rows[0]}")
```

### 3. Parsear CSV

```python
from src.parsers.csv_parser import CSVParser

parser = CSVParser(delimiter=",", has_header=True)
result = parser.parse("downloads/dataset.csv")

if result["parsing_successful"]:
    rows = result["parsed_data"]["rows"]
    print(f"Rows: {len(rows)}")
    # Rows son dicts con headers como keys
    print(f"First row: {rows[0]}")
```

## Pipeline Completo: Descarga + Parseo

Crea un script que descargue y parsee automáticamente:

```python
# examples/file_processing/download_and_parse.py
from src.core.database import get_database_manager
from src.extractors.file_download import FileDownloadExtractor
from src.parsers.pdf_parser import PDFParser
from src.parsers.xlsx_parser import XLSXParser
from src.parsers.csv_parser import CSVParser
from src.repositories.raw_data import get_raw_data_repository, get_parsed_data_repository
from src.settings import get_settings
from pathlib import Path

def download_and_parse():
    settings = get_settings()
    db_manager = get_database_manager(settings)

    # 1. Download files
    extractor = FileDownloadExtractor(settings)
    results = extractor.extract()

    # 2. Store raw data
    raw_repo = get_raw_data_repository(db_manager)
    ids = []
    for result in results:
        row_id = raw_repo.insert(
            source_url=result["source_url"],
            source_type="file_download",
            status_code=result["status_code"],
            data=result["data"],
            error_message=result.get("error_message"),
        )
        ids.append(row_id)

    # 3. Parse each downloaded file
    parsed_repo = get_parsed_data_repository(db_manager)

    for i, result in enumerate(results):
        if result.get("error_message"):
            continue  # Skip failed downloads

        file_path = Path(result["data"]["file_path"])

        # Determinar parser según extensión
        if file_path.suffix == ".pdf":
            parser = PDFParser()
            parser_type = "pdf"
        elif file_path.suffix in [".xlsx", ".xls"]:
            parser = XLSXParser()
            parser_type = "xlsx"
        elif file_path.suffix == ".csv":
            parser = CSVParser()
            parser_type = "csv"
        else:
            continue  # Tipo no soportado

        # Parse
        parse_result = parser.parse_safe(file_path)

        # Store parsed data
        parsed_repo.insert(
            raw_data_id=ids[i],
            parser_type=parser_type,
            parsing_successful=parse_result["parsing_successful"],
            parsed_content=parse_result.get("parsed_data"),
            error_message=parse_result.get("error_message"),
            metadata=parse_result.get("metadata"),
        )

    print(f"Downloaded and parsed {len(results)} files")

if __name__ == "__main__":
    download_and_parse()
```

Ejecutar:
```bash
python examples/file_processing/download_and_parse.py
```

## Descargas desde S3 con URLs Prefirmadas

Si tienes URLs prefirmadas de S3:

```env
FILE_URL_1=https://my-bucket.s3.amazonaws.com/file.pdf?AWSAccessKeyId=...&Signature=...&Expires=...
FILE_URL_2=https://my-bucket.s3.amazonaws.com/data.xlsx?AWSAccessKeyId=...&Signature=...&Expires=...
```

El extractor funciona igual, las URLs prefirmadas son URLs normales.

## Custom File Names

Si quieres controlar los nombres de archivo:

```python
from src.extractors.file_download import FileDownloadExtractor

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

## Descarga con Autenticación

Si las URLs requieren autenticación:

```python
# Modificar src/extractors/file_download.py
class FileDownloadExtractor(BaseExtractor):
    def __init__(self, settings, urls=None, download_dir=None, file_names=None, headers=None):
        super().__init__(settings)
        self.urls = urls or settings.file_urls
        self.download_dir = Path(download_dir or settings.download_dir)
        self.file_names = file_names or []
        self.custom_headers = headers or {}
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _download_single_file(self, url: str, file_name: str) -> dict:
        # ... existing code ...

        with httpx.Client(timeout=self.settings.request_timeout) as client:
            response = client.get(
                url,
                follow_redirects=True,
                headers=self.custom_headers  # Usar headers custom
            )
```

Uso:
```python
headers = {"Authorization": f"Bearer {token}"}
extractor = FileDownloadExtractor(settings, headers=headers)
```

## Organizar Archivos por Fecha

```python
from datetime import datetime

# Crear subdirectorio con fecha
date_dir = datetime.now().strftime("%Y-%m-%d")
download_dir = f"downloads/{date_dir}"

extractor = FileDownloadExtractor(settings, download_dir=download_dir)
results = extractor.extract()
```

Resultado:
```
downloads/
├── 2025-10-24/
│   ├── report.pdf
│   └── data.xlsx
└── 2025-10-25/
    └── dataset.csv
```

## Troubleshooting

**Error: "Download timeout"**
- Aumenta `REQUEST_TIMEOUT` en .env para archivos grandes
- Verifica que la URL sea accesible

**Archivo corrupto**
- Verifica que la URL sea correcta
- Algunos sitios requieren headers específicos (User-Agent, Referer)

**Sin espacio en disco**
- Verifica espacio disponible: `df -h`
- Limpia archivos antiguos en `downloads/`

**Error al parsear PDF**
- El PDF puede estar protegido o encriptado
- Usa otra librería como PyMuPDF para PDFs complejos

**XLSX no abre**
- Verifica que el archivo esté completo (check file size)
- Puede ser formato XLS antiguo (necesita `xlrd`)

## Datasets Públicos de Ejemplo

### 1. Reportes PDF
```env
# UNESCO Reports
FILE_URL_1=https://unesdoc.unesco.org/ark:/48223/pf0000375950.locale=en

# World Bank Reports
FILE_URL_2=https://openknowledge.worldbank.org/bitstream/handle/10986/example.pdf
```

### 2. Datasets CSV
```env
# Data.gov datasets
FILE_URL_1=https://data.gov/example-dataset.csv

# GitHub datasets
FILE_URL_2=https://raw.githubusercontent.com/user/repo/main/data.csv
```

### 3. Excel Files
```env
# WHO Data
FILE_URL_1=https://www.who.int/data/example-data.xlsx

# IMF Data
FILE_URL_2=https://www.imf.org/external/example.xlsx
```
