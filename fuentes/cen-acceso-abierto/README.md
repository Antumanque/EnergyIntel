# CEN Acceso Abierto - Pipeline de Extracción y Análisis

Sistema completo de extracción, descarga y parsing de solicitudes de conexión eléctrica desde el [CEN (Coordinador Eléctrico Nacional)](https://www.coordinador.cl/) de Chile.

## Características

- **Entry point único**: Un solo comando ejecuta todo el pipeline
- **Idempotente**: Se puede ejecutar múltiples veces sin duplicar datos
- **Incremental**: Solo procesa datos nuevos o modificados
- **Detección de cambios**: Compara 32 campos para detectar actualizaciones
- **Detección automática**: Si no hay datos, carga desde 0
- **Soporte completo**: SAC, SUCTD, FEHACIENTE (PDFs, XLSX, ZIPs)
- **OCR integrado**: Tesseract para PDFs escaneados
- **Estadísticas completas**: Reporte detallado al final

## Datos Procesados

| Tipo | Descripción | Documentos |
|------|-------------|------------|
| **SAC** | Solicitud de Aprobación de Conexión | 1,154 parseados |
| **SUCTD** | Uso de Capacidad de Transporte Dedicada | 536 parseados |
| **FEHACIENTE** | Proyectos Fehacientes | 185 parseados |

**Total:** 2,455 solicitudes de conexión eléctrica con datos estructurados.

## Instalación Rápida

### Prerrequisitos
- Docker y Docker Compose
- Python 3.12+ (para desarrollo local)
- Git

### Setup

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd cen-acceso-abierto

# 2. Configurar environment
cp .env.example .env

# 3. Iniciar base de datos
docker-compose up -d cen_db

# 4. Esperar a que la DB esté lista (30 seg)
docker-compose ps

# 5. Ejecutar migraciones
python db/setup.py --migrate
```

## Uso del Pipeline

### Entry Point Único

```bash
# Ejecutar TODO el pipeline (extracción + descarga + parsing)
python pipeline.py

# Solo extracción (solicitudes + documentos de la API)
python pipeline.py --solo-fetch

# Solo descarga de documentos
python pipeline.py --solo-download

# Solo parsing de formularios
python pipeline.py --solo-parse

# Procesar solo un tipo de formulario
python pipeline.py --tipos SAC

# Limitar documentos (para testing)
python pipeline.py --limit 100

# Preview: ver qué se insertaría/actualizaría sin escribir a la BD
python pipeline.py --preview

# Preview con reporte JSON detallado
python pipeline.py --preview --output reporte.json
```

### Flujo Completo

El pipeline ejecuta estos pasos automáticamente:

```
1. EXTRACCIÓN (API → BD)
   ├── Solicitudes por año (2020-2025)
   └── Documentos de cada solicitud

2. DESCARGA (S3 → local)
   ├── Formularios SAC
   ├── Formularios SUCTD
   └── Formularios FEHACIENTE

3. PARSING (PDF/XLSX → BD estructurada)
   ├── SAC: 41 campos + metadata
   ├── SUCTD: 35 campos + metadata
   └── FEHACIENTE: 30 campos + metadata

4. REPORTE
   └── Estadísticas completas
```

## Estructura de la Base de Datos

```sql
-- Solicitudes de conexión
solicitudes (id, nombre_proyecto, potencia_nominal, tecnologia, ...)

-- Documentos adjuntos
documentos (id, solicitud_id, nombre, ruta_s3, tipo_documento, ...)

-- Formularios parseados (tracking)
formularios_parseados (id, documento_id, tipo_formulario, parsing_exitoso, ...)

-- Datos estructurados por tipo
formularios_sac_parsed (razon_social, rut, nombre_proyecto, ...)
formularios_suctd_parsed (razon_social, rut, nombre_proyecto, ...)
formularios_fehaciente_parsed (razon_social, rut, nombre_proyecto, ...)
```

**Vistas útiles:**
- `documentos_ultimas_versiones` - Solo versión más reciente de cada documento
- `documentos_listos_para_parsear` - Documentos descargados sin parsear

Ver schema completo en `docs/DATABASE_SCHEMA.md`

## Desarrollo

### Estructura del Proyecto

```
cen-acceso-abierto/
├── pipeline.py              # Entry point único
├── src/
│   ├── extractors/         # Extracción desde API
│   ├── parsers/            # Parsing de PDFs/XLSX
│   ├── repositories/       # Acceso a base de datos
│   ├── utils/              # Utilidades (ZIP handler, etc)
│   ├── batch_download_*.py # Descarga masiva
│   └── batch_parse_*.py    # Parsing masivo
├── db/
│   ├── init.sql            # Schema inicial
│   ├── migrations/         # Migraciones SQL
│   └── setup.py            # Gestor de migraciones
├── downloads/              # Documentos descargados
├── docs/                   # Documentación técnica
└── archive/                # Scripts obsoletos/debug
```

### Ejecutar Localmente

```bash
# Instalar dependencias con uv
uv sync

# Ejecutar pipeline
uv run python pipeline.py

# O usar Python directamente
source .venv/bin/activate
python pipeline.py
```

### Tests

```bash
# Preview (ver qué se insertaría/actualizaría sin escribir)
python pipeline.py --preview

# Preview con reporte JSON
python pipeline.py --preview -o preview_report.json

# Procesar solo 10 documentos de cada tipo
python pipeline.py --limit 10

# Solo SAC con límite
python pipeline.py --tipos SAC --limit 50
```

## Actualizaciones Periódicas

```bash
# Ejecutar cron job diario (ejemplo)
0 2 * * * cd /path/to/project && uv run python pipeline.py

# O ejecutar manualmente cuando haya nuevas solicitudes
python pipeline.py
```

El pipeline detecta automáticamente nuevas solicitudes y solo procesa lo que falta.

## Estadísticas Actuales

**Última ejecución:** 2025-10-28

| Métrica | Valor |
|---------|-------|
| Solicitudes totales | 2,455 |
| Documentos descargados | 3,244 |
| Formularios parseados | 1,875 |
| Tasa de éxito SAC | 72.8% |
| Tasa de éxito SUCTD | 84.3% |
| Tasa de éxito FEHACIENTE | 79.4% |

**Mejoras recientes:**
- Soporte para archivos ZIP (extracción automática)
- OCR con Tesseract para PDFs escaneados
- Columnas expandidas (RUT, giro, tipo_proyecto)
- Extracción progresiva con fallbacks (pdfplumber → pypdf → OCR)

## Solución de Problemas

### Error de Conexión a Base de Datos

```bash
# Verificar que la BD está corriendo
docker-compose ps

# Ver logs
docker-compose logs cen_db

# Reiniciar BD
docker-compose restart cen_db
```

### Errores de Parsing

```bash
# Ver errores en la base de datos
mysql -h localhost -P 3308 -u user -p database

SELECT parsing_error, COUNT(*)
FROM formularios_parseados
WHERE parsing_exitoso = 0
GROUP BY parsing_error
ORDER BY COUNT(*) DESC;
```

### Migraciones

```bash
# Ver estado de migraciones
python db/setup.py --status

# Ejecutar migraciones pendientes
python db/setup.py --migrate

# Reset completo (borra todo)
python db/setup.py --fresh --drop
```

## Documentación

- `docs/API_DOCUMENTATION.md` - Endpoints del CEN
- `docs/DATABASE_SCHEMA.md` - Schema completo de BD
- `docs/PIPELINE_UPSERT.md` - Lógica de upsert, detección de cambios, y modo preview
- `docs/parsers/PARSER_V2_CHANGELOG.md` - Evolución de parsers
- `CLAUDE.md` - Guía para Claude Code

## Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/NuevaCaracteristica`)
3. Commit cambios (`git commit -m 'Agregar NuevaCaracteristica'`)
4. Push a la rama (`git push origin feature/NuevaCaracteristica`)
5. Abrir Pull Request

## Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## Agradecimientos

- [CEN Chile](https://www.coordinador.cl/) por la API pública
- Tesseract OCR para extracción de PDFs escaneados
- pdfplumber, pypdf, openpyxl para parsing de documentos

---

**Última actualización:** 2025-12-09
**Versión:** 2.6.0
