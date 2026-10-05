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

        # Reconstruir contenedor si cambiaron dependencias o reiniciar
        if command -v docker-compose >/dev/null 2>&1; then
            docker-compose up -d --build
        else
            docker compose up -d --build
        fi

        echo "[$(date)] ✅ tut_bot actualizado y reiniciado con éxito."

        # Limpiar imágenes intermedias huérfanas para cuidar el almacenamiento flash
        docker image prune -f >/dev/null 2>&1 || true
    fi

    sleep 30
done
