# SEA SEIA - Extractor de Proyectos de Evaluación Ambiental

Extractor de datos del Sistema de Evaluación de Impacto Ambiental (SEA) de Chile. Este servicio extrae información de proyectos de evaluación ambiental desde la API pública del SEA y los almacena en MariaDB.

## Características

- 🌐 **Extracción desde API REST**: Consume la API de búsqueda de proyectos del SEA
- 📄 **Paginación Inteligente**: Usa `totalRegistros` de la API para determinar el fin exacto de los datos
- 💾 **Guardado Incremental**: Guarda datos cada 50 páginas - no pierdes progreso si falla
- 🔄 **Retry Logic**: Lógica de reintento con backoff exponencial
- 📦 **Append-Only Storage**: Estrategia de almacenamiento que preserva auditoría completa
- 🐳 **Docker-Ready**: Completamente contenedorizado
- ⚙️ **Type-Safe Config**: Configuración con pydantic-settings
- 📊 **MariaDB 10.11**: Almacenamiento confiable con soporte JSON
- 🎯 **Datos Históricos**: Nunca actualiza ni elimina registros (append-only)
- 🔧 **Encoding Correcto**: Maneja ISO-8859-1 (Latin-1) para caracteres especiales

## Datos Extraídos

### Proyectos del SEA

La API del SEA contiene **29,886 proyectos** de evaluación ambiental con información completa:

- Información básica del proyecto (nombre, tipo, descripción)
- Ubicación geográfica (región, comuna, coordenadas)
- Titular del proyecto
- Inversión (en millones de USD)
- Fechas (presentación, plazo)
- Estado actual del proceso
- Tipo de evaluación (DIA o EIA)
- Enlaces a documentos y expedientes

## Quick Start

### Prerequisites

- Docker y Docker Compose instalados
- Git

### Setup

1. **Clonar el repositorio**
   ```bash
   cd fuentes/sea
   ```

2. **Crear archivo de configuración**
   ```bash
   cp .env.example .env
   ```

3. **Configurar parámetros de búsqueda** (opcional)

   El archivo `.env` viene pre-configurado para extraer todos los proyectos.
   Opcionalmente puedes filtrar por:
   ```env
   # Filtrar por región
   SEA_SELECT_REGION=Metropolitana de Santiago

   # Filtrar por tipo de evaluación
   SEA_TIPO_PRESENTACION=DIA

   # Filtrar por estado
   SEA_PROJECT_STATUS=Aprobados

   # Filtrar por fechas
   SEA_PRESENTACION_MIN=01-01-2024
   SEA_PRESENTACION_MAX=31-12-2024
   ```

4. **Iniciar la base de datos**
   ```bash
   docker-compose up -d sea_db
   ```

   Esperar que la base de datos esté saludable (~30 segundos):
   ```bash
   docker-compose ps
   ```

5. **Ejecutar la extracción**
   ```bash
   docker-compose run --rm sea_app
   ```

## Uso

### Ejecución Manual

Ejecutar una extracción única:
```bash
docker-compose run --rm sea_app
```

### Programación con Cron

Agregar a crontab del sistema para ejecución periódica:

```bash
# Ejecutar semanalmente (domingos a las 2 AM)
0 2 * * 0 cd /path/to/fuentes/sea && docker-compose run --rm sea_app

# Ejecutar mensualmente (primer día del mes a las 3 AM)
0 3 1 * * cd /path/to/fuentes/sea && docker-compose run --rm sea_app
```

### Ver Datos

Conectarse a la base de datos:

```bash
docker-compose exec sea_db mysql -u sea_user -psea_password sea_seia
```

Queries de ejemplo:
```sql
-- Ver proyectos recientes
SELECT * FROM proyectos ORDER BY fecha_presentacion DESC LIMIT 10;

-- Ver estadísticas generales
SELECT * FROM estadisticas_generales;

-- Proyectos por región
SELECT * FROM proyectos_por_region ORDER BY total_proyectos DESC;

-- Proyectos por tipo de evaluación
SELECT * FROM proyectos_por_tipo;

-- Contar extracciones por estado
SELECT status_code, COUNT(*) as count
FROM raw_data
GROUP BY status_code;
```

## Estructura del Proyecto

```
fuentes/sea/
├── src/                           # Código fuente
│   ├── main.py                    # Orquestador principal
│   ├── settings.py                # Configuración con pydantic
│   │
│   ├── core/                      # Utilidades core
│   │   ├── http_client.py         # Cliente HTTP con retries
│   │   ├── logging.py             # Setup de logging
│   │   └── database.py            # Gestor de base de datos
│   │
│   ├── extractors/                # Extractores (API → HTML)
│   │   ├── proyectos.py           # Extractor de proyectos
│   │   ├── expediente_documentos.py  # Extractor de documentos
│   │   └── resumen_ejecutivo.py   # Extractor de PDFs
│   │
│   ├── parsers/                   # Parsers (HTML/JSON → Dict)
│   │   ├── proyectos.py           # Parser de proyectos
│   │   ├── expediente_documentos.py  # Parser de documentos
│   │   └── resumen_ejecutivo.py   # Parser de links a PDF
│   │
│   └── repositories/              # Repositorios (Dict → BD)
│       ├── proyectos.py           # Repository de proyectos
│       ├── expediente_documentos.py  # Repository de documentos
│       └── resumen_ejecutivo_links.py # Repository de links
│
├── db/
│   ├── init.sql                   # Schema inicial
│   └── migrations/                # Migraciones de BD
│
├── logs/                          # Logs de ejecución
├── downloads/                     # PDFs descargados (futuro)
│
├── batch_processor.py             # ⭐ Procesamiento por batches
├── error_report.py                # ⭐ Análisis de errores
├── reset_pipeline.py              # ⭐ Limpieza selectiva
├── stats.py                       # ⭐ Estadísticas globales
├── run_sample.py                  # ⭐ Pipeline completo con muestra
│
├── .env.example                   # Template de configuración
├── .gitignore
├── docker-compose.yml             # Orquestación de servicios
├── Dockerfile                     # Imagen de la aplicación
├── pyproject.toml                 # Dependencias Python
│
├── README.md                      # Este archivo
├── CLAUDE.md                      # Guía de desarrollo con Claude
├── FRAMEWORK.md                   # Framework iterativo
└── observaciones.md               # Hallazgos de investigación
```

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│         API del SEA (búsqueda de proyectos)             │
│  https://seia.sea.gob.cl/busqueda/...                   │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    main.py Orchestrator      │
            │  (Pipeline configurable)     │
            └──────────────────────────────┘
                    ↙   ↓   ↘
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │Extractor │ │Parser    │ │Repository    │
        │(API)     │ │(JSON)    │ │(Database)    │
        └──────────┘ └──────────┘ └──────────────┘
                           │
                           ↓
            ┌──────────────────────────────┐
            │    MariaDB (10.11)           │
            │   raw_data (auditoría)       │
            │   proyectos (parseados)      │
            └──────────────────────────────┘
```

## Configuración

Todas las configuraciones se manejan via variables de entorno en `.env`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DB_HOST` | Database hostname | `sea_db` |
| `DB_PORT` | Database port | `3306` |
| `DB_USER` | Database username | `sea_user` |
| `DB_PASSWORD` | Database password | `sea_password` |
| `DB_NAME` | Database name | `sea_seia` |
| `SEA_API_BASE_URL` | URL base de la API | `https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php` |
| `SEA_LIMIT` | Resultados por página | `100` |
| `REQUEST_TIMEOUT` | HTTP timeout en segundos | `30` |
| `MAX_RETRIES` | Max retry attempts | `3` |

Ver `.env.example` para la lista completa de configuraciones disponibles.

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

4. **Iniciar base de datos (Docker)**:
   ```bash
   docker-compose up -d sea_db
   ```

5. **Ejecutar la aplicación**:
   ```bash
   python -m src.main
   ```

## Estrategia Append-Only

El sistema **NUNCA** actualiza ni elimina registros:

- ✅ Solo **inserta** nuevos proyectos que no existan en la BD
- ✅ Seguro ejecutar múltiples veces (deduplicación automática)
- ✅ Preserva historial completo para auditoría
- ✅ Idempotente: ejecutar 10 veces = ejecutar 1 vez

**Cómo funciona:**
1. Antes de insertar, consulta todos los `expediente_id` existentes
2. Filtra los proyectos que ya están en la BD
3. Solo inserta los proyectos nuevos
4. Los datos crudos (raw_data) se guardan siempre para auditoría

## Guardado Incremental por Batches

El sistema guarda datos **cada 50 páginas** (configurable con `BATCH_SIZE` en `main.py`):

✅ **Ventajas**:
- **No pierdes progreso**: Si el proceso falla, los datos ya guardados permanecen en la BD
- **Seguro**: Puedes cancelar con Ctrl+C en cualquier momento
- **Visible**: Ves el progreso de guardado en tiempo real
- **Resiliente**: Si un batch falla, continúa con el siguiente

**Ejemplo de progreso**:
```
PROCESANDO BATCH 1/6 (50 páginas)
  → Guardando datos crudos en raw_data...
  ✓ Guardados 50 registros en raw_data
  → Parseando proyectos...
  ✓ Parseados 5,000 proyectos
  → Guardando proyectos en BD...
  ✓ Proyectos nuevos: 5,000, duplicados: 0
```

**¿Qué pasa si interrumpes?**
- Los batches ya procesados están guardados en la BD
- Al reiniciar, la deduplicación automática evita duplicados
- Simplemente vuelve a ejecutar `python -m src.main`

## Base de Datos

### Tablas Principales

#### `raw_data`
Almacena todas las respuestas de la API en formato JSON:
- `id`: ID autoincremental
- `source_url`: URL con parámetros de la request
- `status_code`: HTTP status code
- `data`: Response completo en JSON
- `extracted_at`: Timestamp de extracción

#### `proyectos`
Almacena proyectos parseados con campos normalizados:
- `expediente_id`: ID único del expediente (PK)
- `expediente_nombre`: Nombre del proyecto
- `workflow_descripcion`: Tipo de evaluación (DIA/EIA)
- `region_nombre`: Región del proyecto
- `titular`: Empresa/persona titular
- `inversion_mm`: Inversión en millones de USD
- `estado_proyecto`: Estado actual
- Y muchos campos más...

### Vistas Útiles

- `proyectos_por_region`: Estadísticas de proyectos agrupados por región
- `proyectos_por_tipo`: Estadísticas por tipo de evaluación (DIA/EIA)
- `proyectos_recientes`: Proyectos presentados en los últimos 30 días
- `estadisticas_generales`: Dashboard de estadísticas generales

## Scripts de Producción

### run_sample.py - Pipeline Completo de Inicio a Fin

Script que ejecuta el pipeline completo con una muestra de 50 proyectos, demostrando las 3 etapas:

```bash
# Ejecutar pipeline completo con muestra
python run_sample.py

# Con limpieza previa de BD
python run_sample.py --clean
```

**Etapas del pipeline**:
1. **Extracción de proyectos** (50 proyectos de muestra)
2. **Extracción de documentos del expediente** (EIA/DIA)
3. **Extracción de links a PDF resumen ejecutivo** (Capítulo 20)
4. **Estadísticas finales** con conversión global

### batch_processor.py - Procesamiento por Lotes

Procesa proyectos en batches y trackea errores detalladamente:

```bash
# Procesar batch de documentos (Etapa 2)
python batch_processor.py --batch-size 1000 --stage 2

# Procesar batch de links a PDF (Etapa 3)
python batch_processor.py --batch-size 500 --stage 3
```

### error_report.py - Análisis de Errores

Muestra estadísticas detalladas de qué está fallando y por qué:

```bash
# Ver reporte de errores de Etapa 2
python error_report.py --stage 2

# Ver top 20 errores de Etapa 3
python error_report.py --stage 3 --top 20
```

### reset_pipeline.py - Limpieza Selectiva

Limpia selectivamente etapas del pipeline para re-procesar:

```bash
# Ver qué se va a borrar (dry-run)
python reset_pipeline.py --stage 3 --dry-run

# Limpiar solo Etapa 3
python reset_pipeline.py --stage 3

# Limpiar TODO (precaución)
python reset_pipeline.py --all
```

### stats.py - Estadísticas Globales

Ver estadísticas completas del pipeline:

```bash
python stats.py
```

## Framework Iterativo

El proyecto implementa un **framework iterativo data-driven** para mejorar el pipeline incrementalmente:

1. ✅ Procesar un **batch pequeño** (1,000 proyectos)
2. ✅ Ver qué **falló y por qué**
3. ✅ Arreglar el **error más común**
4. ✅ Limpiar y **re-ejecutar**
5. ✅ Medir **mejora**
6. 🔁 **Repetir** hasta maximizar conversión

Ver [FRAMEWORK.md](FRAMEWORK.md) para documentación completa del framework iterativo.

## Próximos Pasos

1. ✅ **Extracción de Documentos**: Implementado (Etapa 2)
2. ✅ **Extracción de Links a PDFs**: Implementado (Etapa 3)
3. **Descarga de PDFs**: Descargar PDFs del Capítulo 20
4. **Parseo de PDFs**: Extraer información estructurada de PDFs
5. **Análisis de Datos**: Crear dashboard de visualizaciones

## Troubleshooting

### Error: "Table 'proyectos' does not exist"

**Causa**: La base de datos no está inicializada.

**Solución**:
```bash
docker-compose exec sea_db mysql -u sea_user -psea_password sea_seia < db/init.sql
```

### Error: "Connection refused"

**Causa**: La base de datos no está corriendo.

**Solución**:
```bash
docker-compose up -d sea_db
# Esperar ~30 segundos
docker-compose ps
```

### No se extraen proyectos

**Causa**: Posible problema con la API del SEA o parámetros de búsqueda muy restrictivos.

**Solución**:
1. Verificar que la API esté disponible: `curl -X POST https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php`
2. Revisar filtros en `.env` (dejarlos vacíos extrae todo)
3. Revisar logs: `docker-compose logs sea_app`

## Licencia

*(Agregar licencia aquí)*

## Contribuciones

*(Agregar guías de contribución aquí)*
