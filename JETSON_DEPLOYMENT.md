# 🚀 Manual de Despliegue en NVIDIA Jetson Nano — Proyecto B (tut_bot)

Este documento detalla las directrices operativas, la configuración de contenedores y los procedimientos de verificación para desplegar **tut_bot** en la **NVIDIA Jetson Nano B01**, garantizando convivencia armónica con el bot de trading preexistente (24/7).

---

## 1. Ficha Técnica y Verificación de Compatibilidad

| Parámetro | Host (Jetson Nano) | Proyecto B (tut_bot) | Estado |
| :--- | :--- | :--- | :--- |
| **Arquitectura CPU** | `ARM64` (`aarch64`) | `python:3.10-slim` (arm64) | ✅ Compatible sin emulación |
| **RAM Asignada** | 4 GB total (~2.2 GB libre) | Límite: **768 MB** (consumo medio: ~220 MB) | ✅ Seguro contra OOM Killer |
| **CPU Cores** | 4 Cores ARM Cortex-A57 | Límite: **1.5 cores** (`cpus: 1.5`) | ✅ Evita saturación de CPU |
| **Puertos Host** | `22` (SSH), `8080` (Trading), `5432` (Postgres) | **`8000`** (FastAPI / Webhook) | ✅ **Cero colisión de puertos** |
| **Red Docker** | Red aislada de trading | `tutbot_network` (bridge independiente) | ✅ Aislamiento de red total |
| **Persistencia** | `/home/lvant/Documents/proyecto_b/data` | Montaje `./data:/app/data` (SQLite) | ✅ Datos de usuarios persistentes |
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

### Paso 2: Clonar el Repositorio en la Carpeta Aislada
```bash
cd /home/lvant/Documents
git clone https://github.com/lvanegast/tut_bot.git proyecto_b
cd /home/lvant/Documents/proyecto_b
```

---

## 3. Métodos de Despliegue

### Opción A: Despliegue directo con Git Clone en la Jetson (Recomendada)
1. **En la Jetson, configurar el archivo `.env`:**
   ```bash
   cd /home/lvant/Documents/proyecto_b
   cp .env.example .env
   nano .env
   PORT=8000
   HOST=0.0.0.0
   TELEGRAM_BOT_TOKEN=tu_token_de_telegram
   GEMINI_API_KEY=tu_api_key_de_gemini
   AZURE_SPEECH_KEY=tu_azure_speech_key
   AZURE_SPEECH_REGION=eastus
   IS_MOCK_MODE=false
   DATA_DIR=/app/data
   EOF
   ```
3. **Construir y levantar el contenedor con Docker Compose:**
   ```bash
   docker-compose up -d --build
   ```

---

### Opción B: Cross-Compilation en PC con Docker Buildx (Si se desea ahorrar CPU en la Jetson)
*(Ejecutar en la máquina de desarrollo con soporte Docker Buildx)*:
```bash
# 1. Compilar imagen dirigida a arquitectura ARM64
docker buildx build --platform linux/arm64 -t tutbot:arm64 --load .

# 2. Exportar y transferir comprimida por SSH a la Jetson
docker save tutbot:arm64 | gzip | ssh lvant@192.168.10.10 "gunzip | docker load"

# 3. En la Jetson, levantar usando la imagen cargada
ssh lvant@192.168.10.10 "cd /home/lvant/Documents/proyecto_b && docker-compose up -d"
```

---

## 4. Verificación y Monitoreo Post-Despliegue

Inmediatamente después de ejecutar `docker-compose up -d`, ejecuta:

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
cd /home/lvant/Documents/proyecto_b

# Reiniciar tut_bot
docker-compose restart

# Detener tut_bot de forma limpia
docker-compose down

# Reconstruir tras cambios
docker-compose up -d --build
```
