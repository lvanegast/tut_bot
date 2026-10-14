#!/usr/bin/env bash
# =========================================================================
# CD Auto-Deploy Daemon para tut_bot (Proyecto B) en NVIDIA Jetson Nano
# Ubicación en Jetson: /home/lvant/Documents/tut_bot/scripts/auto_deploy.sh
# =========================================================================

REPO_DIR="/home/lvant/Documents/tut_bot"
BRANCH="main"

cd "$REPO_DIR" || exit 1

echo "[$(date)] Auto-deploy service iniciado para tut_bot ($BRANCH)"

while true; do
    git fetch origin "$BRANCH" --quiet 2>/dev/null
    LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null || true)
    REMOTE_HASH=$(git rev-parse origin/"$BRANCH" 2>/dev/null || true)

    if [ -n "$REMOTE_HASH" ] && [ -n "$LOCAL_HASH" ] && [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
        echo "[$(date)] 🚀 Nuevo push detectado ($REMOTE_HASH). Actualizando tut_bot..."
        git pull origin "$BRANCH"

        # Detectar si cambiaron archivos de infraestructura/dependencias que requieran rebuild
        BUILD_FILES_CHANGED=$(git diff --name-only "$LOCAL_HASH" "$REMOTE_HASH" 2>/dev/null | grep -E '^(Dockerfile|docker-compose\.yml|pyproject\.toml|uv\.lock)' || true)

        git pull origin "$BRANCH"

        if [ -n "$BUILD_FILES_CHANGED" ]; then
            echo "[$(date)] 📦 Cambios en dependencias detectados ($BUILD_FILES_CHANGED). Reconstruyendo con baja prioridad (nice)..."
            if command -v docker-compose >/dev/null 2>&1; then
                nice -n 15 docker-compose up -d --build
            else
                nice -n 15 docker compose up -d --build
            fi
            # Limpiar imágenes intermedias huérfanas para cuidar el almacenamiento flash
            docker image prune -f >/dev/null 2>&1 || true
        else
            echo "[$(date)] ⚡ Solo cambios de código en caliente (volumen montado). Reiniciando contenedor tutbot_service..."
            if command -v docker-compose >/dev/null 2>&1; then
                docker-compose restart tutbot_service
            else
                docker compose restart tutbot_service
            fi
        fi

        echo "[$(date)] ✅ tut_bot actualizado y reiniciado con éxito."

    fi

    sleep 30
done
