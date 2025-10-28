FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para MySQL connector
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv (gestor de paquetes Python ultra-rápido)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copiar archivos de dependencias
COPY pyproject.toml ./

# Instalar dependencias con uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Copiar código fuente
COPY src/ ./src/

# Crear directorios de salida
RUN mkdir -p /app/downloads /app/logs

# Comando por defecto
CMD ["python", "-m", "src.main"]
