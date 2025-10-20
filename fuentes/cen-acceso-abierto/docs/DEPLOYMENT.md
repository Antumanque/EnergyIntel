# Guía de Deployment - CEN Acceso Abierto

## Resumen Ejecutivo

Este proyecto **NO requiere Docker en producción**. Es una aplicación Python simple que:
- Extrae datos de la API del CEN
- Los guarda en MariaDB
- Se ejecuta periódicamente vía cron

**TL;DR**: Apunta a tu MariaDB de producción, crea la base de datos, y ejecuta `uv run python -m src.main`. ¡Listo!

---

## Deployment en Servidor de Producción

### Pre-requisitos

1. **Servidor con**:
   - Python 3.12+
   - Acceso a servidor MariaDB/MySQL existente
   - Git instalado

2. **MariaDB/MySQL Server**:
   - Ya debe estar corriendo (servidor existente de Antumanque)
   - Usuario con permisos para crear bases de datos
   - Puerto 3306 accesible desde el servidor de aplicación

---

## Instalación Paso a Paso

### 1. Clonar el Repositorio

```bash
# En el servidor de producción
cd /opt  # o tu directorio preferido
git clone <url-del-repo> cen-acceso-abierto
cd cen-acceso-abierto
```

### 2. Instalar UV (Gestor de Dependencias)

```bash
# Instalar uv (si no está instalado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Recargar el shell
source ~/.bashrc  # o ~/.zshrc según tu shell
```

### 3. Instalar Dependencias

```bash
# Instalar todas las dependencias del proyecto
uv sync
```

### 4. Crear Base de Datos

```bash
# Conectarse al servidor MariaDB de producción
mysql -h TU_HOST_PRODUCCION -u TU_USUARIO -p

# Dentro de MySQL, crear la base de datos
CREATE DATABASE IF NOT EXISTS cen_acceso_abierto
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

# Verificar que se creó
SHOW DATABASES LIKE 'cen_acceso_abierto';

# Salir
exit;
```

### 5. Configurar Variables de Entorno

```bash
# Crear archivo .env en el directorio del proyecto
cat > .env << 'EOF'
# =============================================================================
# CONFIGURACIÓN DE BASE DE DATOS - PRODUCCIÓN
# =============================================================================

# Host del servidor MariaDB de producción
DB_HOST=tu.servidor.mariadb.produccion

# Puerto (usualmente 3306)
DB_PORT=3306

# Nombre de la base de datos
DB_NAME=cen_acceso_abierto

# Credenciales de acceso
DB_USER=tu_usuario_produccion
DB_PASSWORD=tu_password_seguro

# =============================================================================
# CONFIGURACIÓN API CEN
# =============================================================================

# URL base de la API del CEN (no cambiar)
CEN_API_BASE_URL=https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public

# Años a extraer (comma-separated, sin espacios)
# Para producción: extraer todos los años disponibles
CEN_YEARS=2020,2021,2022,2023,2024,2025

# Tipos de documento a filtrar (IMPORTANTE: case-sensitive!)
# - "Formulario SUCTD" (con espacio, SUCTD en mayúsculas)
# - "Formulario SAC" (con espacio, SAC en mayúsculas)
# - "Formulario_proyecto_fehaciente" (con underscores, lowercase)
CEN_DOCUMENT_TYPES=Formulario SUCTD,Formulario SAC,Formulario_proyecto_fehaciente

# =============================================================================
# CONFIGURACIÓN HTTP CLIENT
# =============================================================================

# Timeout para requests HTTP (en segundos)
REQUEST_TIMEOUT=30

# Número máximo de reintentos en caso de fallo
MAX_RETRIES=3
EOF

# Ajustar permisos (importante para seguridad)
chmod 600 .env
```

### 6. Primera Ejecución (Prueba Manual)

```bash
# Ejecutar extracción manualmente para verificar que todo funciona
uv run python -m src.main

# Esto hará:
# 1. Crear automáticamente todas las tablas necesarias
# 2. Crear las vistas de analytics
# 3. Extraer datos de interesados
# 4. Extraer solicitudes de los años configurados
# 5. Extraer documentos importantes

# Duración estimada:
# - Con CEN_YEARS=2025: ~15-30 minutos
# - Con CEN_YEARS=2020,2021,2022,2023,2024,2025: ~2-4 horas
```

### 7. Verificar Datos en Base de Datos

```bash
# Conectarse a la base de datos
mysql -h TU_HOST_PRODUCCION -u TU_USUARIO -p cen_acceso_abierto

# Verificar tablas creadas
SHOW TABLES;
# Deberías ver:
# - raw_api_data (respuestas crudas del API)
# - interesados (stakeholders normalizados)
# - solicitudes (proyectos)
# - documentos (archivos importantes)
# - documentos_importantes (vista)
# - estadisticas_extraccion (vista)
# - latest_fetches (vista)
# - solicitudes_con_documentos (vista)
# - successful_fetches (vista)

# Ver estadísticas
SELECT
    'raw_api_data' as tabla, COUNT(*) as registros FROM raw_api_data
UNION ALL
SELECT 'interesados', COUNT(*) FROM interesados
UNION ALL
SELECT 'solicitudes', COUNT(*) FROM solicitudes
UNION ALL
SELECT 'documentos', COUNT(*) FROM documentos;

# Salir
exit;
```

---

## Automatización con Cron

### Configurar Ejecución Diaria

```bash
# Editar crontab del usuario
crontab -e

# Agregar línea para ejecutar todos los días a las 2 AM
0 2 * * * cd /opt/cen-acceso-abierto && /home/TU_USUARIO/.local/bin/uv run python -m src.main >> /var/log/cen-extraction.log 2>&1

# IMPORTANTE: Ajustar las rutas según tu instalación:
# - /opt/cen-acceso-abierto: directorio del proyecto
# - /home/TU_USUARIO/.local/bin/uv: ruta completa a uv
# - /var/log/cen-extraction.log: archivo de log (crear si no existe)
```

### Crear Archivo de Log

```bash
# Crear archivo de log con permisos apropiados
sudo touch /var/log/cen-extraction.log
sudo chown TU_USUARIO:TU_USUARIO /var/log/cen-extraction.log
sudo chmod 644 /var/log/cen-extraction.log
```

### Verificar Cron Está Funcionando

```bash
# Ver últimas ejecuciones en el log
tail -100 /var/log/cen-extraction.log

# Ver líneas con errores
grep -i "error\|failed" /var/log/cen-extraction.log

# Ver resumen de última ejecución
grep "RESUMEN FINAL" /var/log/cen-extraction.log | tail -1
```

---

## Actualizaciones del Código

### Actualizar a Nueva Versión

```bash
# Ir al directorio del proyecto
cd /opt/cen-acceso-abierto

# Descargar última versión
git pull origin main

# Actualizar dependencias (si cambiaron)
uv sync

# Ejecutar manualmente para verificar
uv run python -m src.main
```

---

## Troubleshooting

### Error: "Can't connect to MySQL server"

**Problema**: No puede conectarse a la base de datos.

**Solución**:
```bash
# Verificar que el servidor MariaDB está corriendo
mysql -h TU_HOST -u TU_USUARIO -p -e "SELECT 1"

# Verificar credenciales en .env
cat .env | grep DB_

# Verificar firewall permite conexión al puerto 3306
telnet TU_HOST 3306
```

### Error: "Database 'cen_acceso_abierto' doesn't exist"

**Problema**: Base de datos no fue creada.

**Solución**:
```bash
# Crear la base de datos manualmente
mysql -h TU_HOST -u TU_USUARIO -p -e "CREATE DATABASE cen_acceso_abierto"
```

### Error: "No module named 'src'"

**Problema**: Python no encuentra el módulo.

**Solución**:
```bash
# Asegurarse de ejecutar desde el directorio del proyecto
cd /opt/cen-acceso-abierto
uv run python -m src.main
```

### Verificar Logs de Errores

```bash
# Ver últimas 50 líneas del log
tail -50 /var/log/cen-extraction.log

# Buscar errores específicos
grep -i "error" /var/log/cen-extraction.log | tail -20

# Ver solo errores de hoy
grep "$(date +%Y-%m-%d)" /var/log/cen-extraction.log | grep -i error
```

---

## Monitoreo y Mantenimiento

### Verificar Última Extracción

```bash
# Conectarse a la base de datos
mysql -h TU_HOST -u TU_USUARIO -p cen_acceso_abierto

# Ver última extracción exitosa
SELECT source_url, fetched_at, status_code
FROM raw_api_data
ORDER BY fetched_at DESC
LIMIT 10;

# Ver estadísticas usando la vista
SELECT * FROM estadisticas_extraccion;
```

### Limpiar Datos Antiguos (Opcional)

```bash
# Si necesitas limpiar datos de hace más de 6 meses
mysql -h TU_HOST -u TU_USUARIO -p cen_acceso_abierto

# Ver cuántos registros tienes
SELECT COUNT(*) FROM raw_api_data;

# Borrar registros antiguos (CUIDADO - esto es permanente!)
DELETE FROM raw_api_data
WHERE fetched_at < DATE_SUB(NOW(), INTERVAL 6 MONTH);
```

---

## Diferencias: Desarrollo vs Producción

| Aspecto | Desarrollo (Local) | Producción (Servidor) |
|---------|-------------------|----------------------|
| **Base de datos** | Docker container MariaDB | Servidor MariaDB existente |
| **Ejecución** | Manual con `docker-compose` | Cron automatizado |
| **Host DB** | `localhost` o `cen_db` | IP/hostname del servidor |
| **Años a extraer** | Solo 2025 (rápido) | Todos los años disponibles |
| **Logs** | Consola | Archivo `/var/log/cen-extraction.log` |
| **Docker** | ✅ Usado para DB local | ❌ NO necesario |

---

## Preguntas Frecuentes

### ¿Por qué NO usar Docker en producción?

**Respuesta**: Para esta aplicación simple, Docker no agrega valor:

- ✅ **UV ya maneja dependencias** de forma reproducible
- ✅ **Ya tienes MariaDB** corriendo en producción
- ✅ **Es un solo script** que se ejecuta y termina (no un servicio permanente)
- ✅ **Cron es más simple** que orquestar containers

Docker es útil para desarrollo local (base de datos temporal), pero en producción es overhead innecesario.

### ¿Cada cuánto se debe ejecutar la extracción?

**Recomendación**: Una vez al día (madrugada).

- Los datos del CEN no cambian cada hora
- La extracción completa toma 2-4 horas
- Ejecutar de madrugada evita impacto en horas laborales

### ¿Qué pasa si falla una extracción?

**Respuesta**: La próxima ejecución automática lo intentará de nuevo.

- El sistema usa **estrategia append-only**: solo inserta datos nuevos
- Los datos ya extraídos **no se duplican** (unique constraints)
- Los errores se registran en `raw_api_data` con `status_code != 200`

### ¿Cómo agregar más años?

**Respuesta**: Editar `.env` y agregar el año:

```bash
# Antes
CEN_YEARS=2020,2021,2022,2023,2024,2025

# Después (agregando 2026)
CEN_YEARS=2020,2021,2022,2023,2024,2025,2026
```

La próxima ejecución automáticamente extraerá el año nuevo.

---

## Soporte

Si encuentras problemas:

1. **Revisar logs**: `/var/log/cen-extraction.log`
2. **Verificar base de datos**: Conectarse y revisar tablas
3. **Ejecutar manualmente**: `uv run python -m src.main` para ver errores en consola
4. **Revisar documentación**: Este archivo y `docs/DATABASE_SCHEMA.md`

---

**Última actualización**: 2025-10-19
**Versión del sistema**: 1.0.0
