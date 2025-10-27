# Guía de Parsers

Esta guía describe todos los parsers disponibles en Fuentes Base y cómo usarlos y extenderlos.

## Tabla de Contenidos

- [Conceptos Básicos](#conceptos-básicos)
- [BaseParser](#baseparser)
- [JSONParser](#jsonparser)
- [PDFParser](#pdfparser)
- [XLSXParser](#xlsxparser)
- [CSVParser](#csvparser)
- [HTMLParser](#htmlparser)
- [Crear Parser Personalizado](#crear-parser-personalizado)
- [Best Practices](#best-practices)

---

## Conceptos Básicos

### ¿Qué es un Parser?

Un **parser** es un componente responsable de transformar datos crudos a formato estructurado:
- JSON → Python dict con transformaciones
- PDF → Texto + Tablas extraídas
- XLSX → Rows como dicts
- CSV → Rows como dicts
- HTML → Datos estructurados extraídos

### Contrato del Parser

Todos los parsers deben:
1. Heredar de `BaseParser`
2. Implementar el método `parse(data)`
3. Retornar dict con formato estandarizado

**Formato de retorno**:
```python
{
    "parsing_successful": bool,     # True si parseo exitoso
    "parsed_data": dict | None,     # Datos parseados (si exitoso)
    "error_message": str | None,    # Mensaje de error (si falló)
    "metadata": dict                # Metadata adicional
}
```

### Principios de Diseño

1. **Pureza**: Parsers son funciones puras (sin side effects)
2. **No I/O**: No hacen requests HTTP ni escriben a BD
3. **Idempotencia**: Mismo input → mismo output
4. **Error Handling**: Nunca lanzan excepciones sin capturar

---

## BaseParser

Clase base abstracta que define la interfaz común.

### Ubicación
```python
from src.parsers.base import BaseParser
```

### Interfaz

```python
class BaseParser(ABC):
    @abstractmethod
    def parse(self, data: Any) -> dict[str, Any]:
        """Parsear datos desde formato crudo."""
        pass

    def validate_result(self, result: dict[str, Any]) -> bool:
        """Validar formato del resultado."""
        pass

    def parse_safe(self, data: Any) -> dict[str, Any]:
        """Parse con manejo de errores incorporado."""
        pass
```

### Métodos Utilitarios

**`parse_safe(data)`**
- Wrapper de `parse()` que captura excepciones
- Siempre retorna resultado en formato válido
- Usa este método en producción

**`validate_result(result)`**
- Valida que un resultado tenga campos requeridos
- Retorna `True` si es válido, `False` sino

---

## JSONParser

Parser para datos JSON con transformaciones opcionales.

### Ubicación
```python
from src.parsers.json_parser import JSONParser
```

### Características

- Parseo de strings JSON a Python dicts
- Soporte para transformaciones custom
- Manejo de JSON malformado

### Uso Básico

```python
from src.parsers.json_parser import JSONParser

# JSON como string
json_str = '{"name": "John", "age": 30}'

parser = JSONParser()
result = parser.parse(json_str)

if result["parsing_successful"]:
    data = result["parsed_data"]
    print(data["name"])  # "John"
```

### Con Transformación

```python
def transform_user(data):
    """Transformar datos de usuario."""
    return {
        "full_name": data.get("name", "Unknown"),
        "age_years": data.get("age", 0),
        "is_adult": data.get("age", 0) >= 18,
    }

parser = JSONParser(transform_fn=transform_user)
result = parser.parse(json_str)

# result["parsed_data"] = {
#     "full_name": "John",
#     "age_years": 30,
#     "is_adult": True
# }
```

### Entrada Flexible

```python
# Acepta diferentes tipos de entrada
parser = JSONParser()

# String JSON
result = parser.parse('{"key": "value"}')

# Dict (pasa directamente)
result = parser.parse({"key": "value"})

# Bytes
result = parser.parse(b'{"key": "value"}')
```

### Transformación de Arrays

```python
def transform_users_list(data):
    """Filtrar y transformar lista de usuarios."""
    if not isinstance(data, list):
        return data

    # Solo adultos
    adults = [u for u in data if u.get("age", 0) >= 18]

    # Extraer solo campos relevantes
    return [
        {"name": u["name"], "email": u["email"]}
        for u in adults
    ]

parser = JSONParser(transform_fn=transform_users_list)
```

---

## PDFParser

Parser para archivos PDF usando pdfplumber.

### Ubicación
```python
from src.parsers.pdf_parser import PDFParser
```

### Características

- Extracción de texto de todas las páginas
- Extracción de tablas
- Metadata del PDF (número de páginas)
- Basado en pdfplumber (robusto para la mayoría de PDFs)

### Uso Básico

```python
from src.parsers.pdf_parser import PDFParser
from pathlib import Path

file_path = Path("downloads/report.pdf")

parser = PDFParser()
result = parser.parse(file_path)

if result["parsing_successful"]:
    data = result["parsed_data"]

    # Texto extraído
    print(data["text"][:500])

    # Tablas extraídas
    for i, table in enumerate(data["tables"]):
        print(f"Table {i}: {len(table)} rows")

    # Metadata
    print(f"Pages: {result['metadata']['num_pages']}")
```

### Personalizar Extracción

Para PDFs con estructura específica, hereda del parser:

```python
from src.parsers.pdf_parser import PDFParser
import pdfplumber

class CustomPDFParser(PDFParser):
    """Parser para formularios PDF específicos."""

    def parse(self, data):
        file_path = Path(data)

        try:
            with pdfplumber.open(file_path) as pdf:
                # Parsear solo primera página
                first_page = pdf.pages[0]

                # Extraer tabla específica
                tables = first_page.extract_tables()

                # Procesar tabla (asumiendo estructura conocida)
                parsed_table = self._parse_form_table(tables[0])

                return {
                    "parsing_successful": True,
                    "parsed_data": parsed_table,
                    "error_message": None,
                    "metadata": {
                        "parser_type": "custom_pdf",
                        "num_pages": len(pdf.pages),
                    },
                }

        except Exception as e:
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "custom_pdf"},
            }

    def _parse_form_table(self, table):
        """Parsear tabla de formulario."""
        data = {}
        for row in table:
            if len(row) >= 2:
                label = row[0]
                value = row[1]
                if label and value:
                    data[label.strip()] = value.strip()
        return data
```

### Extraer Texto de Página Específica

```python
import pdfplumber

def parse_page_3(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[2]  # 0-indexed (página 3)
        text = page.extract_text()
        return text
```

### Buscar Patrones en PDF

```python
import re
import pdfplumber

def find_rut_numbers(pdf_path):
    """Buscar RUTs chilenos en PDF."""
    pattern = r'\d{1,2}\.\d{3}\.\d{3}-[\dkK]'

    ruts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                found = re.findall(pattern, text)
                ruts.extend(found)

    return list(set(ruts))  # Únicos
```

---

## XLSXParser

Parser para archivos Excel usando openpyxl.

### Ubicación
```python
from src.parsers.xlsx_parser import XLSXParser
```

### Características

- Lectura de hojas de Excel
- Extracción de todas las rows
- Soporte para hojas específicas
- Opción data_only (valores vs. fórmulas)

### Uso Básico

```python
from src.parsers.xlsx_parser import XLSXParser

file_path = "downloads/data.xlsx"

parser = XLSXParser()
result = parser.parse(file_path)

if result["parsing_successful"]:
    data = result["parsed_data"]

    # Todas las rows
    rows = data["rows"]
    print(f"Total rows: {len(rows)}")

    # Primera row (usualmente headers)
    headers = rows[0]
    print(f"Headers: {headers}")

    # Data rows
    for row in rows[1:]:
        print(row)
```

### Leer Hoja Específica

```python
# Por nombre
parser = XLSXParser(sheet_name="Data")
result = parser.parse(file_path)

# Por índice (primera hoja = 0)
parser = XLSXParser(sheet_name="Sheet1")
```

### Leer Fórmulas en Lugar de Valores

```python
# data_only=False para ver fórmulas
parser = XLSXParser(data_only=False)
result = parser.parse(file_path)

# Verás "=SUM(A1:A10)" en lugar del resultado
```

### Parser Personalizado con Headers

```python
from src.parsers.xlsx_parser import XLSXParser
from openpyxl import load_workbook

class XLSXWithHeadersParser(XLSXParser):
    """Parser que retorna rows como dicts usando headers."""

    def parse(self, data):
        file_path = Path(data)

        try:
            workbook = load_workbook(file_path, data_only=self.data_only)
            sheet = workbook.active

            rows = list(sheet.iter_rows(values_only=True))

            # Primera row = headers
            headers = rows[0]

            # Convertir rows a dicts
            data_rows = []
            for row in rows[1:]:
                data_rows.append(dict(zip(headers, row)))

            workbook.close()

            return {
                "parsing_successful": True,
                "parsed_data": {
                    "headers": headers,
                    "rows": data_rows,  # Lista de dicts
                    "num_rows": len(data_rows),
                },
                "error_message": None,
                "metadata": {
                    "parser_type": "xlsx_with_headers",
                    "num_rows": len(data_rows),
                },
            }

        except Exception as e:
            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "xlsx_with_headers"},
            }
```

### Leer Múltiples Hojas

```python
from openpyxl import load_workbook

def parse_all_sheets(file_path):
    workbook = load_workbook(file_path, data_only=True)

    all_sheets_data = {}

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        all_sheets_data[sheet_name] = rows

    workbook.close()
    return all_sheets_data
```

---

## CSVParser

Parser para archivos CSV.

### Ubicación
```python
from src.parsers.csv_parser import CSVParser
```

### Características

- Lectura de CSV con delimitadores configurables
- Conversión automática a dicts (si hay header)
- Soporte para archivos y strings

### Uso Básico

```python
from src.parsers.csv_parser import CSVParser

file_path = "downloads/data.csv"

parser = CSVParser(delimiter=",", has_header=True)
result = parser.parse(file_path)

if result["parsing_successful"]:
    rows = result["parsed_data"]["rows"]

    # Si has_header=True, rows son dicts
    for row in rows:
        print(row["column_name"])
```

### CSV sin Header

```python
parser = CSVParser(delimiter=",", has_header=False)
result = parser.parse(file_path)

# Rows son listas, no dicts
rows = result["parsed_data"]["rows"]
for row in rows:
    print(row[0], row[1], row[2])  # Acceso por índice
```

### Delimitador Custom

```python
# Tab-separated values
parser = CSVParser(delimiter="\t")

# Punto y coma (común en Europa)
parser = CSVParser(delimiter=";")

# Pipe-separated
parser = CSVParser(delimiter="|")
```

### Parsear String CSV

```python
csv_content = """name,age,city
John,30,NYC
Jane,25,LA"""

parser = CSVParser()
result = parser.parse(csv_content)
```

---

## HTMLParser

Parser para contenido HTML usando BeautifulSoup.

### Ubicación
```python
from src.parsers.html_parser import HTMLParser
```

### Características

- Extracción estructurada desde HTML
- Parseo de meta tags, headings, links, images
- Texto plano extraído
- Personalizable via herencia

### Uso Básico

```python
from src.parsers.html_parser import HTMLParser

html_content = """
<html>
<head><title>My Page</title></head>
<body>
    <h1>Welcome</h1>
    <p>Content here</p>
</body>
</html>
"""

parser = HTMLParser()
result = parser.parse(html_content)

if result["parsing_successful"]:
    data = result["parsed_data"]

    print(data["title"])       # "My Page"
    print(data["headings"])    # {"h1": ["Welcome"]}
    print(data["text"])        # Texto plano extraído
```

### Parsear HTML desde Dict

```python
# Si el extractor retornó dict con key 'html'
data_from_extractor = {
    "html": "<html>...</html>",
    "url": "https://example.com",
}

parser = HTMLParser()
result = parser.parse(data_from_extractor)
```

### Parser Personalizado

```python
from src.parsers.html_parser import HTMLParser
from bs4 import BeautifulSoup

class NewsArticleParser(HTMLParser):
    """Parser específico para artículos de noticias."""

    def parse(self, data):
        # Extraer HTML
        if isinstance(data, dict) and "html" in data:
            html_content = data["html"]
        elif isinstance(data, str):
            html_content = data
        else:
            return self._error_result("Invalid input type")

        try:
            soup = BeautifulSoup(html_content, self.parser)

            # Extraer campos específicos
            article = soup.find("article")
            if not article:
                return self._error_result("Article not found")

            parsed_data = {
                "title": self._extract_title(article),
                "author": self._extract_author(article),
                "date": self._extract_date(article),
                "content": self._extract_content(article),
                "tags": self._extract_tags(article),
            }

            return {
                "parsing_successful": True,
                "parsed_data": parsed_data,
                "error_message": None,
                "metadata": {"parser_type": "news_article"},
            }

        except Exception as e:
            return self._error_result(str(e))

    def _extract_title(self, article):
        title_tag = article.find("h1", class_="article-title")
        return title_tag.get_text(strip=True) if title_tag else None

    def _extract_author(self, article):
        author_tag = article.find("span", class_="author")
        return author_tag.get_text(strip=True) if author_tag else None

    # ... más métodos de extracción

    def _error_result(self, message):
        return {
            "parsing_successful": False,
            "parsed_data": None,
            "error_message": message,
            "metadata": {"parser_type": "news_article"},
        }
```

---

## Crear Parser Personalizado

### Paso 1: Crear Archivo

```bash
touch src/parsers/mi_parser.py
```

### Paso 2: Implementar Clase

```python
# src/parsers/mi_parser.py
import logging
from typing import Any

from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class MiParser(BaseParser):
    """
    Descripción del parser.
    """

    def __init__(self, **kwargs):
        super().__init__()
        # Parámetros de configuración
        self.param1 = kwargs.get("param1")

    def parse(self, data: Any) -> dict[str, Any]:
        """
        Parsear datos.

        Args:
            data: Datos crudos a parsear

        Returns:
            Dict con resultado del parseo
        """
        try:
            # Tu lógica de parseo aquí
            parsed = self._parse_logic(data)

            return {
                "parsing_successful": True,
                "parsed_data": parsed,
                "error_message": None,
                "metadata": {
                    "parser_type": "mi_formato",
                    # Agregar metadata relevante
                },
            }

        except Exception as e:
            logger.error(f"Error parsing: {e}", exc_info=True)

            return {
                "parsing_successful": False,
                "parsed_data": None,
                "error_message": str(e),
                "metadata": {"parser_type": "mi_formato"},
            }

    def _parse_logic(self, data: Any) -> dict:
        """
        Lógica específica de parseo.
        """
        # Implementar aquí
        pass
```

### Paso 3: Usar el Parser

```python
from src.parsers.mi_parser import MiParser

parser = MiParser(param1="value")
result = parser.parse_safe(data)  # Usa parse_safe en producción

if result["parsing_successful"]:
    print(result["parsed_data"])
else:
    print(f"Error: {result['error_message']}")
```

---

## Best Practices

### 1. Usar parse_safe() en Producción

```python
# DO
result = parser.parse_safe(data)

# DON'T (puede lanzar excepción)
result = parser.parse(data)
```

### 2. Validar Input

```python
def parse(self, data):
    # Validar tipo de input
    if not isinstance(data, (str, Path)):
        return {
            "parsing_successful": False,
            "parsed_data": None,
            "error_message": f"Invalid input type: {type(data)}",
            "metadata": {},
        }

    # Continuar con parseo
    ...
```

### 3. Metadata Útil

```python
return {
    "parsing_successful": True,
    "parsed_data": data,
    "error_message": None,
    "metadata": {
        "parser_type": "my_parser",
        "parser_version": "1.0",
        "num_records": len(data),
        "parsing_duration_ms": duration,
        "warnings": warnings_list,
    },
}
```

### 4. Logging Apropiado

```python
# Info para éxito
logger.info(f"Successfully parsed {len(records)} records")

# Warning para situaciones anómalas
logger.warning("Unexpected format, using fallback parser")

# Error para fallos
logger.error(f"Failed to parse: {e}", exc_info=True)
```

### 5. Parsers Reutilizables

```python
# Parametriza comportamiento
class FlexibleCSVParser(CSVParser):
    def __init__(self, delimiter=",", has_header=True, skip_rows=0):
        super().__init__(delimiter, has_header)
        self.skip_rows = skip_rows

    def parse(self, data):
        # Skip initial rows si es necesario
        # ... parseo
```

### 6. Testing

```python
# tests/test_mi_parser.py
def test_parser_valid_input():
    parser = MiParser()
    result = parser.parse("valid input")

    assert result["parsing_successful"] == True
    assert result["parsed_data"] is not None
    assert result["error_message"] is None


def test_parser_invalid_input():
    parser = MiParser()
    result = parser.parse(None)

    assert result["parsing_successful"] == False
    assert result["error_message"] is not None
```

---

## Troubleshooting Común

**"PDF parsing failed"**
- PDF puede estar encriptado o protegido
- Prueba con PyMuPDF en lugar de pdfplumber
- Verifica que el archivo no esté corrupto

**"XLSX file cannot be opened"**
- Puede ser formato XLS antiguo (necesita xlrd)
- Archivo puede estar corrupto
- Verifica que la descarga sea completa

**"CSV parsing error: unexpected end of data"**
- Archivo puede estar truncado
- Verifica formato de comillas y escapes

**"HTML parsing returns empty data"**
- Los selectores CSS pueden ser incorrectos
- El HTML puede estar malformado
- Usa `soup.prettify()` para inspeccionar estructura

**"Memory error on large files"**
- Procesa en chunks en lugar de todo en memoria
- Usa generadores para iterar sobre datos
- Considera streaming parsers para archivos muy grandes
