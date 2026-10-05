# =========================================================================
# Script de Despliegue de tut_bot (Proyecto B) hacia NVIDIA Jetson Nano
# Destino: lvant@192.168.10.10:/home/lvant/Documents/proyecto_b
# =========================================================================

param (
    [string]$JetsonHost = "192.168.10.10",
    [string]$JetsonUser = "lvant",
    [string]$RemoteDir  = "/home/lvant/Documents/proyecto_b"
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  Despliegue Seguro de tut_bot en NVIDIA Jetson Nano" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

# 1. Comprobación preliminar de salud del Bot de Trading preexistente
Write-Host "`n[1/5] Verificando salud del sistema de trading en http://${JetsonHost}:8080..." -ForegroundColor Yellow
try {
    $preStatus = Invoke-WebRequest -Uri "http://${JetsonHost}:8080/api/status" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  -> Trading Bot responde correctamente (HTTP $($preStatus.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  -> [AVISO] No se pudo obtener respuesta directa en 8080/api/status desde este host ($($_.Exception.Message)). Continuando con precaución..." -ForegroundColor Yellow
}

# 2. Creación del directorio remoto en la Jetson
Write-Host "`n[2/5] Creando directorio remoto aislado ($RemoteDir)..." -ForegroundColor Yellow
ssh "${JetsonUser}@${JetsonHost}" "mkdir -p ${RemoteDir}/data"

# 3. Transferencia de archivos esenciales (excluyendo .git, .venv, tests, caches)
Write-Host "`n[3/5] Transfiriendo archivos del proyecto a la Jetson..." -ForegroundColor Yellow
$tarArchive = "$env:TEMP\tutbot_deploy.tar"
if (Test-Path $tarArchive) { Remove-Item $tarArchive -Force }

# Empaquetar con tar nativo de Windows excluyendo carpetas pesadas
tar -cf $tarArchive `
    --exclude=".git" `
    --exclude=".venv" `
    --exclude="__pycache__" `
    --exclude=".pytest_cache" `
    --exclude="tests" `
    --exclude="*.wav" `
    -C "C:\Proyectos\tut_bot" .

# Enviar y desempaquetar en la Jetson
scp $tarArchive "${JetsonUser}@${JetsonHost}:${RemoteDir}/tutbot_deploy.tar"
ssh "${JetsonUser}@${JetsonHost}" "cd ${RemoteDir} && tar -xf tutbot_deploy.tar && rm tutbot_deploy.tar"
Remove-Item $tarArchive -Force -ErrorAction SilentlyContinue

Write-Host "  -> Archivos sincronizados en ${RemoteDir}" -ForegroundColor Green

# 4. Construcción y levantamiento del contenedor con límites de recursos
Write-Host "`n[4/5] Levantando contenedor con Docker Compose (ARM64, límite 768MB RAM, 1.5 CPUs)..." -ForegroundColor Yellow
ssh "${JetsonUser}@${JetsonHost}" @"
cd ${RemoteDir}
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build
else
    docker compose up -d --build
fi
"@

# 5. Verificación post-despliegue
Write-Host "`n[5/5] Ejecutando verificaciones post-despliegue..." -ForegroundColor Yellow
ssh "${JetsonUser}@${JetsonHost}" @"
echo '--- Estado de Contenedores ---'
docker ps --filter name=tutbot

echo '--- Uso de Recursos (RAM / CPU) ---'
docker stats --no-stream

echo '--- Prueba de Salud tut_bot (Puerto 8000) ---'
curl -s -I http://localhost:8000/api/health || true

echo '--- Comprobación de Trading Bot (Puerto 8080) ---'
curl -s -I http://localhost:8080/api/status || true
"@

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "  Despliegue finalizado con éxito!" -ForegroundColor Green
Write-Host "  tut_bot corriendo en http://${JetsonHost}:8000" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
