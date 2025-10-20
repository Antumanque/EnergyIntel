# Sistema de Migraciones y Setup de Base de Datos

## 🎯 Filosofía del Sistema

Este proyecto usa un **enfoque híbrido** para manejar el schema de base de datos:

1. **Schemas Base** (`db/*.sql`) - Setup inicial completo
2. **Migraciones** (`db/migrations/*.sql`) - Cambios incrementales

---

## 📂 Estructura de Archivos

```
db/
├── init.sql                          # Schema: raw_api_data (Docker)
├── schema_solicitudes.sql           # Schema: solicitudes + documentos
├── schema_formularios_parsed.sql   # Schema: formularios parseados
├── setup.py                         # ⭐ Script inteligente de setup
├── migrate.py                       # Script de migraciones
└── migrations/                      # Solo CAMBIOS incrementales
    ├── 001_add_download_error_column.sql
    ├── 002_add_documentos_ultimas_versiones_view.sql
    └── 003_add_pdf_metadata_columns.sql
```

---

## 🚀 Cómo Funciona

### Setup Inteligente (Auto-Detecta)

```bash
python db/setup.py  # ← Usa este comando
```

**Qué hace**:
1. Detecta si la BD está vacía
2. **Si está vacía** → Ejecuta schemas base completos (fresh install)
3. **Si ya existe** → Solo ejecuta migraciones pendientes

**Resultado**:
- ✅ Fresh install: Tablas creadas en segundos
- ✅ Update: Solo migraciones nuevas ejecutadas

---

## 📋 Dos Tipos de Archivos SQL

### 1. **Schemas Base** (Setup Inicial)

**Archivos**:
- `db/init.sql` - Tabla `raw_api_data`
- `db/schema_solicitudes.sql` - Tablas `solicitudes`, `documentos` + vistas
- `db/schema_formularios_parsed.sql` - Tablas `formularios_parseados`, `formularios_*_parsed`

**Características**:
- Crean tablas completas con TODAS las columnas
- Se ejecutan solo en fresh install
- Incluyen índices, foreign keys, vistas

**Cuándo se usan**:
- Primera instalación
- Recrear BD desde cero

**Ejemplo** (`schema_formularios_parsed.sql`):
```sql
CREATE TABLE IF NOT EXISTS formularios_parseados (
    id BIGINT PRIMARY KEY,
    documento_id BIGINT UNIQUE,
    tipo_formulario ENUM(...),
    -- ... TODAS las columnas (incluyendo pdf_metadata)
    pdf_producer VARCHAR(255),
    pdf_author VARCHAR(255),
    -- ...
);
```

---

### 2. **Migraciones** (Cambios Incrementales)

**Directorio**: `db/migrations/`

**Nomenclatura**: `NNN_descripcion.sql`
- `NNN` = Número secuencial (001, 002, 003...)
- `descripcion` = Breve descripción en snake_case

**Características**:
- SOLO cambios (ALTER TABLE, CREATE INDEX, etc.)
- Se ejecutan en orden
- Idempotentes (usan `IF NOT EXISTS`)
- Se registran en `schema_migrations`

**Cuándo se usan**:
- Agregar nueva columna
- Crear nuevo índice
- Modificar tabla existente
- Agregar nueva vista

**Ejemplo** (`003_add_pdf_metadata_columns.sql`):
```sql
-- Para bases de datos EXISTENTES que no tienen las columnas
ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_producer VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_pdf_producer ON formularios_parseados(pdf_producer);
```

---

## 🔄 Flujos de Trabajo

### Fresh Install (Primera Vez)

```bash
# Automático
python db/setup.py

# Output:
# 🔍 Auto-detectando...
# 📊 Base de datos VACÍA → Fresh install
# 🔄 Ejecutando: init.sql
# ✅ init.sql ejecutado
# 🔄 Ejecutando: schema_solicitudes.sql
# ✅ schema_solicitudes.sql ejecutado
# 🔄 Ejecutando: schema_formularios_parsed.sql
# ✅ schema_formularios_parsed.sql ejecutado
# ✅ FRESH INSTALL COMPLETADO
```

**Tablas creadas**:
- `raw_api_data`
- `solicitudes`
- `documentos`
- `formularios_parseados` (con TODAS las columnas incluidas)
- `formularios_sac_parsed`
- `formularios_suctd_parsed`
- `formularios_fehaciente_parsed`
- Vistas: `documentos_ultimas_versiones`, etc.

---

### Update (BD Existente)

```bash
# Automático
python db/setup.py

# Output:
# 🔍 Auto-detectando...
# 📊 Base de datos EXISTENTE → Solo migraciones
# 📋 3 migraciones pendientes
# 🔄 Ejecutando: 001_add_download_error_column.sql
# ✅ Migración exitosa
# 🔄 Ejecutando: 002_add_documentos_ultimas_versiones_view.sql
# ✅ Migración exitosa
# 🔄 Ejecutando: 003_add_pdf_metadata_columns.sql
# ✅ Migración exitosa
```

---

## 🆕 Agregar Nuevo Cambio de Schema

### Paso 1: Decidir Si Es Migración o Schema Base

**¿Es una nueva tabla completa?**
- ✅ Agregar a schema base correspondiente
- ✅ Crear migración para BD existentes

**¿Es modificación a tabla existente?**
- ✅ Solo crear migración

---

### Paso 2: Crear Migración

```bash
# 1. Crear archivo con número secuencial
cat > db/migrations/004_add_new_index.sql << 'EOF'
-- Descripción del cambio
CREATE INDEX IF NOT EXISTS idx_solicitud_rut
ON solicitudes(rut_empresa);
EOF

# 2. Probar localmente
DB_HOST=localhost uv run python db/setup.py

# 3. Commit y push
git add db/migrations/004_add_new_index.sql
git commit -m "perf: add index on rut_empresa"
git push
```

---

### Paso 3: Actualizar Schema Base (Si Aplica)

Si creaste tabla nueva, agrégala también al schema base:

```bash
# Editar schema correspondiente
nano db/schema_solicitudes.sql

# Agregar nueva tabla al final
CREATE TABLE IF NOT EXISTS nueva_tabla (
    ...
);
```

**¿Por qué ambos?**
- Schema base: Para fresh installs futuros
- Migración: Para BDs existentes

---

## 🛠️ Comandos Útiles

### Ver Estado de Migraciones

```bash
python db/setup.py --status  # No implementado aún
# O usar:
python db/migrate.py --status
```

---

### Forzar Fresh Install

```bash
python db/setup.py --fresh
```

**⚠️ Advertencia**: Solo úsalo si sabes que la BD está vacía o quieres recrearla.

---

### Solo Ejecutar Migraciones

```bash
python db/setup.py --migrate
# O directamente:
python db/migrate.py
```

---

## 📊 Tabla de Tracking: `schema_migrations`

El sistema crea automáticamente esta tabla para registrar migraciones ejecutadas:

```sql
CREATE TABLE schema_migrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    migration_file VARCHAR(255) UNIQUE,  -- "001_add_column.sql"
    executed_at TIMESTAMP
);
```

**Queries útiles**:

```sql
-- Ver migraciones ejecutadas
SELECT * FROM schema_migrations ORDER BY executed_at DESC;

-- Ver última migración
SELECT migration_file, executed_at
FROM schema_migrations
ORDER BY executed_at DESC
LIMIT 1;
```

---

## 🔍 Diferencias: Schema Base vs Migración

### Schema Base (`schema_formularios_parsed.sql`)

```sql
-- Crea tabla COMPLETA con TODAS las columnas
CREATE TABLE IF NOT EXISTS formularios_parseados (
    id BIGINT PRIMARY KEY,
    documento_id BIGINT UNIQUE,
    tipo_formulario ENUM('SAC', 'SUCTD', 'FEHACIENTE'),

    -- Columnas originales
    parsing_exitoso BOOLEAN,
    parser_version VARCHAR(50),

    -- Columnas agregadas después (metadata)
    pdf_producer VARCHAR(255),     -- ← Ya incluida
    pdf_author VARCHAR(255),       -- ← Ya incluida
    pdf_title VARCHAR(500),        -- ← Ya incluida
    pdf_creation_date DATETIME,    -- ← Ya incluida

    INDEX idx_pdf_producer (pdf_producer)  -- ← Ya incluido
);
```

**Se ejecuta**: Solo en fresh install.

---

### Migración (`003_add_pdf_metadata_columns.sql`)

```sql
-- Solo AGREGA columnas que no existen
ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_producer VARCHAR(255);

ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_author VARCHAR(255);

-- ...

CREATE INDEX IF NOT EXISTS idx_pdf_producer ON formularios_parseados(pdf_producer);
```

**Se ejecuta**: Solo en BDs existentes (update).

---

## ⚠️ Importante

### Mantener Sincronizados

Cuando agregues cambios:

1. **Actualiza schema base** (para fresh installs futuros)
2. **Crea migración** (para BDs existentes)

**Ejemplo**: Agregar columna `pdf_size`

```bash
# 1. Editar schema base
nano db/schema_formularios_parsed.sql
# Agregar: pdf_size BIGINT COMMENT 'Tamaño del PDF en bytes'

# 2. Crear migración
cat > db/migrations/004_add_pdf_size.sql << 'EOF'
ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_size BIGINT COMMENT 'Tamaño del PDF en bytes';
EOF

# 3. Commit ambos
git add db/schema_formularios_parsed.sql db/migrations/004_add_pdf_size.sql
git commit -m "feat: add pdf_size column"
```

---

## 🎯 Beneficios del Enfoque Híbrido

✅ **Fresh installs rápidos**: Un solo script crea todo
✅ **Updates seguros**: Solo migraciones pendientes
✅ **Auto-detección**: No necesitas saber si es fresh o update
✅ **Historial claro**: Migraciones muestran evolución del schema
✅ **Idempotente**: Puedes correr múltiples veces sin problemas

---

**Última actualización**: 2025-10-20
