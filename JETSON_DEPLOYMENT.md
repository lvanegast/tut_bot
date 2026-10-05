# 🚀 Manual de Despliegue en NVIDIA Jetson Nano — tut_bot

Este documento detalla las directrices operativas, la configuración de contenedores y los procedimientos de verificación para desplegar **tut_bot** en la **NVIDIA Jetson Nano B01**, garantizando convivencia armónica con el bot de trading preexistente (24/7).

---

## 1. Ficha Técnica y Verificación de Compatibilidad

| Parámetro | Host (Jetson Nano) | tut_bot | Estado |
| :--- | :--- | :--- | :--- |
| **Arquitectura CPU** | `ARM64` (`aarch64`) | `python:3.10-slim` (arm64) | ✅ Compatible sin emulación |
| **RAM Asignada** | 4 GB total (~2.2 GB libre) | Límite: **768 MB** (consumo medio: ~220 MB) | ✅ Seguro contra OOM Killer |
| **CPU Cores** | 4 Cores ARM Cortex-A57 | Límite: **1.5 cores** (`cpus: 1.5`) | ✅ Evita saturación de CPU |
| **Puertos Host** | `22` (SSH), `8080` (Trading), `5432` (Postgres) | **`8000`** (FastAPI / Webhook) | ✅ **Cero colisión de puertos** |
| **Red Docker** | Red aislada de trading | `tutbot_network` (bridge independiente) | ✅ Aislamiento de red total |
| **Persistencia** | `/home/lvant/Documents/tut_bot/data` | Montaje `./data:/app/data` (SQLite) | ✅ Datos de usuarios persistentes |
| **Resiliencia** | Reinicios / cortes de energía | `restart: unless-stopped` | ✅ Auto-recuperación activa |

---

## 2. Preparación en la Jetson Nano (Paso a Paso)

Conéctate por SSH a la Jetson:
```bash
ssh lvant@192.168.10.10
```

### Paso 1: Comprobación de Salud del Bot Preexistente (Antes de tocar nada)
```bash
# Verificar que el bot de trading responde perfectamente
curl -I http://localhost:8080/api/status

# Verificar uso actual de memoria y contenedores
docker ps
docker stats --no-stream
```

### Paso 2: Clonar el Repositorio
```bash
cd /home/lvant/Documents
git clone https://github.com/lvanegast/tut_bot.git
cd /home/lvant/Documents/tut_bot
```

---

## 3. Despliegue con Docker Compose

1. **Configurar el archivo `.env`:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   *(Ingresa tus credenciales de Telegram, Gemini y Azure; guarda con `Ctrl+O` y sal con `Ctrl+X`)*.

2. **Construir y levantar el contenedor con Docker Compose:**
   ```bash
   docker-compose up -d --build
   ```
   *(O `docker compose up -d --build` si utilizas Compose v2)*.

---

## 4. Verificación y Monitoreo Post-Despliegue

Inmediatamente después de levantar el contenedor, ejecuta:

```bash
# 1. Verificar estado del contenedor tutbot_service
docker ps --filter name=tutbot_service

# 2. Inspeccionar logs de inicio
docker logs tutbot_service --tail 30

# 3. Comprobar el endpoint de salud de tut_bot en puerto 8000
curl -s http://localhost:8000/api/health

# 4. CRÍTICO: Comprobar que el bot de trading en 8080 sigue respondiendo intacto
curl -I http://localhost:8080/api/status

# 5. Monitorear el consumo de recursos de ambos contenedores
docker stats --no-stream
```

### Limpieza de Espacio en Disco (SSD / eMMC de la Jetson):
Para liberar espacio ocupado por capas intermedias de compilación:
```bash
docker image prune -f
```

---

## 5. Parada o Actualización Segura

Si necesitas actualizar o reiniciar `tut_bot` sin afectar al trading bot:
```bash
cd /home/lvant/Documents/tut_bot

# Actualizar a la última versión de código
git pull origin main

# Reconstruir tras cambios
docker-compose up -d --build

# Reiniciar tut_bot
docker-compose restart

# Detener tut_bot de forma limpia
docker-compose down
```
