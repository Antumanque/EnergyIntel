# Instalación de Tesseract OCR

Para ejecutar la competencia con OCR, necesitas instalar Tesseract en el sistema.

## Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-spa poppler-utils
```

## macOS

```bash
brew install tesseract tesseract-lang poppler
```

## Windows

1. Descargar instalador desde: https://github.com/UB-Mannheim/tesseract/wiki
2. Instalar y agregar al PATH
3. Descargar datos de idioma español (spa.traineddata)

## Verificar Instalación

```bash
tesseract --version
```

Debería mostrar algo como:
```
tesseract 5.x.x
```

## Ejecutar Competencia

Una vez instalado Tesseract:

```bash
uv run python scripts/pdf_parsing_competition.py
```

El script comparará automáticamente:
- 🔵 Método Actual (pdfplumber + pypdf + hermanos)
- 🟢 Tesseract OCR

Con los 28 PDFs que fallaron con "No se detectaron tablas".
