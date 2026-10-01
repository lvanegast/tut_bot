# =========================================================================
# Dockerfile para tut_bot - Compatible con x86_64 y ARM64 (Jetson Nano)
# =========================================================================

FROM python:3.10-slim

# Evitar prompts interactivos y buffering de logs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Instalar dependencias del sistema necesarias para Azure Speech SDK (ALSA, SSL, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    libasound2 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv para gestión de paquetes ultrarrápida
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copiar archivos de configuración del proyecto
COPY pyproject.toml .
COPY uv.lock* ./

# Sincronizar dependencias usando uv
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Copiar código fuente
COPY src/ /app/src/
COPY README.md /app/README.md

EXPOSE 8000

# Ejecutar aplicación usando el entorno virtual gestionado por uv
CMD ["uv", "run", "uvicorn", "tut_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
