#!/usr/bin/env bash
# =========================================================================
# Instalador automático del servicio systemd de auto-deploy para tut_bot
# Ejecutar en la Jetson Nano: sudo bash scripts/setup_autodeploy_service.sh
# =========================================================================

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Este script debe ejecutarse con privilegios sudo: sudo bash $0"
    exit 1
fi

PROJECT_DIR="/home/lvant/Documents/tut_bot"
SERVICE_SRC="${PROJECT_DIR}/scripts/tutbot-autodeploy.service"
SERVICE_DEST="/etc/systemd/system/tutbot-autodeploy.service"
SCRIPT_PATH="${PROJECT_DIR}/scripts/auto_deploy.sh"

echo "=== Configurando CI/CD Auto-Deploy para tut_bot ==="

# 1. Permisos de ejecución al script
chmod +x "$SCRIPT_PATH"
chown lvant:lvant "$SCRIPT_PATH"
echo "✅ Permisos asignados a $SCRIPT_PATH"

# 2. Copiar definición del servicio a systemd
cp "$SERVICE_SRC" "$SERVICE_DEST"
chmod 644 "$SERVICE_DEST"
echo "✅ Servicio copiado a $SERVICE_DEST"

# 3. Recargar y activar systemd
systemctl daemon-reload
systemctl enable tutbot-autodeploy.service
systemctl restart tutbot-autodeploy.service
echo "✅ Servicio tutbot-autodeploy habilitado e iniciado!"

# 4. Mostrar estado de ambos servicios
echo ""
echo "=== Estado de los Servicios de Auto-Deploy en la Jetson ==="
systemctl status bot-autodeploy.service tutbot-autodeploy.service --no-pager || true
