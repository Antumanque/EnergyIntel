#!/bin/bash
#
# Script de deployment para producción (servidor Antumanque).
#
# Este script se ejecuta después de git pull y:
# 1. Instala/actualiza dependencias con uv
# 2. Ejecuta migraciones pendientes de base de datos
# 3. Verifica que todo esté OK
#
# Uso:
#   ./deploy.sh                 # Deployment completo
#   ./deploy.sh --migrations    # Solo migraciones
#   ./deploy.sh --status        # Ver estado sin ejecutar

set -e  # Exit on error

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Funciones helper
log_info() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "pyproject.toml" ]; then
    log_error "Debe ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Parsear argumentos
ONLY_MIGRATIONS=false
SHOW_STATUS=false
FORCE_FRESH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --migrations)
            ONLY_MIGRATIONS=true
            shift
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --fresh)
            FORCE_FRESH=true
            shift
            ;;
        *)
            log_error "Argumento desconocido: $1"
            echo "Uso: $0 [--migrations] [--status] [--fresh]"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================================================"
echo "🚀 DEPLOYMENT: CEN Acceso Abierto"
echo "========================================================================"
echo ""

# Solo mostrar status
if [ "$SHOW_STATUS" = true ]; then
    log_info "Mostrando estado de migraciones..."
    uv run python db/migrate.py --status
    exit 0
fi

# Paso 1: Git pull (actualizar código)
if [ "$ONLY_MIGRATIONS" = false ]; then
    log_info "Paso 1/4: Actualizando código desde Git..."

    # Verificar si hay cambios sin commitear
    if ! git diff-index --quiet HEAD --; then
        log_warn "Hay cambios sin commitear en el repositorio"
        read -p "¿Continuar de todas formas? Esto podría causar conflictos (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Deployment cancelado"
            exit 1
        fi
    fi

    # Guardar branch actual
    CURRENT_BRANCH=$(git branch --show-current)
    log_info "Branch actual: $CURRENT_BRANCH"

    # Git pull
    git pull origin "$CURRENT_BRANCH"

    if [ $? -eq 0 ]; then
        log_info "Código actualizado correctamente"
    else
        log_error "Error al hacer git pull"
        exit 1
    fi
else
    log_warn "Saltando git pull (--migrations)"
fi

echo ""

# Paso 2: Instalar/actualizar dependencias (skip si solo migraciones)
if [ "$ONLY_MIGRATIONS" = false ]; then
    log_info "Paso 2/4: Instalando dependencias..."
    uv sync --frozen

    if [ $? -eq 0 ]; then
        log_info "Dependencias actualizadas correctamente"
    else
        log_error "Error al instalar dependencias"
        exit 1
    fi
else
    log_warn "Saltando instalación de dependencias (--migrations)"
fi

echo ""

# Paso 3: Setup de base de datos (auto-detecta fresh install vs migraciones)
log_info "Paso 3/4: Configurando base de datos..."

# Forzar fresh install si se especificó --fresh
if [ "$FORCE_FRESH" = true ]; then
    log_warn "Forzando FRESH INSTALL completo (--fresh)"
    log_warn "⚠️  ADVERTENCIA: Esto BORRARÁ y recreará TODAS las tablas"
    read -p "¿Estás seguro? Esto eliminará TODOS los datos existentes (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Deployment cancelado"
        exit 1
    fi

    uv run python db/setup.py --fresh --drop
else
    # Auto-setup: detecta si es fresh install o solo migraciones
    uv run python db/setup.py
fi

if [ $? -eq 0 ]; then
    log_info "Base de datos configurada correctamente"
else
    log_error "Error al configurar base de datos"
    exit 1
fi

echo ""

# Paso 4: Verificación post-deployment
if [ "$ONLY_MIGRATIONS" = false ]; then
    log_info "Paso 4/4: Verificando configuración..."

    # Verificar que la base de datos esté accesible
    uv run python -c "
from src.repositories.cen import get_cen_db_manager
db = get_cen_db_manager()
if db.test_connection():
    print('✅ Conexión a base de datos OK')
else:
    print('❌ Error de conexión a base de datos')
    exit(1)
"

    if [ $? -eq 0 ]; then
        log_info "Verificación completada"
    else
        log_error "Error en verificación"
        exit 1
    fi
else
    log_warn "Saltando verificación (--migrations)"
fi

echo ""
echo "========================================================================"
echo "🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE"
echo "========================================================================"
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar extracción completa: python -m src.main"
echo "  2. Verificar logs: tail -f /var/log/cen-ingestion.log"
echo "  3. Ver estado de migraciones: ./deploy.sh --status"
echo ""
echo "Opciones de deployment:"
echo "  ./deploy.sh              # Auto-detecta fresh install vs migraciones"
echo "  ./deploy.sh --fresh      # Forzar recreación completa de BD"
echo "  ./deploy.sh --status     # Ver estado sin ejecutar"
echo ""

exit 0
