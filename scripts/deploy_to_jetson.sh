#!/usr/bin/env bash
# =========================================================================
# Script de Despliegue de tut_bot (Proyecto B) hacia NVIDIA Jetson Nano
# Destino: lvant@192.168.10.10:/home/lvant/Documents/proyecto_b
# =========================================================================

set -euo pipefail

JETSON_HOST="${1:-192.168.10.10}"
JETSON_USER="${2:-lvant}"
REMOTE_DIR="${3:-/home/lvant/Documents/proyecto_b}"

echo "========================================================="
echo "  Despliegue Seguro de tut_bot en NVIDIA Jetson Nano"
echo "========================================================="

# 1. Comprobación preliminar de salud del Bot de Trading preexistente
echo -e "\n[1/5] Verificando salud del sistema de trading en http://${JETSON_HOST}:8080..."
curl -s -I "http://${JETSON_HOST}:8080/api/status" || echo "Aviso: No se pudo verificar 8080 directamente. Continuando..."

# 2. Creación del directorio remoto en la Jetson
echo -e "\n[2/5] Creando directorio remoto aislado (${REMOTE_DIR})..."
ssh "${JETSON_USER}@${JETSON_HOST}" "mkdir -p ${REMOTE_DIR}/data"

# 3. Transferencia de archivos esenciales
echo -e "\n[3/5] Transfiriendo archivos del proyecto a la Jetson..."
tar --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='tests' \
    --exclude='*.wav' \
    -czf /tmp/tutbot_deploy.tar.gz -C . .

scp /tmp/tutbot_deploy.tar.gz "${JETSON_USER}@${JETSON_HOST}:${REMOTE_DIR}/tutbot_deploy.tar.gz"
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${REMOTE_DIR} && tar -xzf tutbot_deploy.tar.gz && rm tutbot_deploy.tar.gz"
rm -f /tmp/tutbot_deploy.tar.gz

echo "  -> Archivos sincronizados en ${REMOTE_DIR}"

# 4. Construcción y levantamiento del contenedor con límites de recursos
echo -e "\n[4/5] Levantando contenedor con Docker Compose (ARM64, límite 768MB RAM, 1.5 CPUs)..."
ssh "${JETSON_USER}@${JETSON_HOST}" "bash -s" << 'EOF'
cd /home/lvant/Documents/proyecto_b
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build
else
    docker compose up -d --build
fi
EOF

# 5. Verificación post-despliegue
echo -e "\n[5/5] Ejecutando verificaciones post-despliegue..."
ssh "${JETSON_USER}@${JETSON_HOST}" "bash -s" << 'EOF'
echo '--- Estado de Contenedores ---'
docker ps --filter name=tutbot

echo '--- Uso de Recursos (RAM / CPU) ---'
docker stats --no-stream

echo '--- Prueba de Salud tut_bot (Puerto 8000) ---'
curl -s -I http://localhost:8000/api/health || true

echo '--- Comprobación de Trading Bot (Puerto 8080) ---'
curl -s -I http://localhost:8080/api/status || true
EOF

echo "========================================================="
echo "  Despliegue finalizado con éxito!"
echo "  tut_bot corriendo en http://${JETSON_HOST}:8000"
echo "========================================================="
