# tut_bot 🎙️🇩🇪🇬🇧

**tut_bot** es un entrenador fonético interactivo inteligente para perfeccionar la pronunciación en **Alemán** e **Inglés**, diseñado para ejecutarse en PC o en una **NVIDIA Jetson Nano** con dos interfaces unificadas:

1. **Canal Telegram (Notas de Voz Móvil)**: Entrena hablando directamente a Telegram con el botón del micrófono de tu teléfono. El bot convierte el audio OGG Opus al vuelo, evalúa tus fonemas con Azure, te devuelve el desglose con barras visuales y te envía notas de voz con la pronunciación nativa de referencia.
2. **Web Dashboard SPA (Escritorio / Kiosco)**: Interfaz gráfica web moderna con TailwindCSS, Web Audio API (PCM 16 kHz), visualizador interactivo fonema a fonema y tarjeta de progreso acumulado con fonemas críticos.
3. **Azure Cognitive Services Speech (Free Tier F0)**: Evaluación acústica fonema por fonema con alfabeto fonético internacional (IPA), cálculo de precisión, fluidez, completitud y prosodia.
4. **Google Gemini AI Studio (Free Tier)**: Tutor pedagógico que analiza los fonemas desviados y genera explicaciones anatómicas en español sobre cómo colocar la lengua, labios y flujo de aire.
5. **Persistencia SQLite Ultraligera**: Seguimiento de sesiones y mapeo de fonemas débiles para reentrenamiento continuo.

---

## 📁 Estructura del Proyecto

```
tut_bot/
├── pyproject.toml              # Dependencias y comandos CLI (uv, ruff, pytest)
├── uv.lock                     # Bloqueo reproducible de dependencias
├── Dockerfile                  # Imagen ligera compatible con x86_64 y ARM64 (Jetson Nano)
├── docker-compose.yml          # Orquestación de contenedor con límites de memoria
├── .env.example                # Plantilla de variables de entorno
├── run.py                      # Script de arranque rápido
├── README.md                   # Documentación técnica
├── src/
│   └── tut_bot/
│       ├── __init__.py
│       ├── config.py           # Gestión de variables y detección de modo mock
│       ├── main.py             # Aplicación FastAPI, routers y ciclo de vida de Telegram
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py      # Esquemas de datos Pydantic (Fonemas, Palabras, Métricas)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── audio_converter.py # Remuestreo OGG Opus <-> WAV PCM 16kHz con FFmpeg
│       │   ├── azure_speech.py    # Evaluación fonética y TTS con Azure SDK
│       │   ├── gemini_coach.py    # Pedagogía fonética con Gemini 2.5 Flash
│       │   ├── exercises.py       # Catálogo curricular fonético (Alemán / Inglés)
│       │   ├── telegram_bot.py    # Bot interactivo de Telegram para notas de voz
│       │   └── tracker.py         # Persistencia SQLite y diagnóstico de fonemas débiles
│       └── static/             # Interfaz web SPA (HTML5, TailwindCSS, Web Audio API)
│           ├── index.html
│           ├── css/custom.css
│           └── js/
│               ├── app.js
│               └── recorder.js
└── tests/
    ├── __init__.py
    └── test_api.py             # Pruebas automatizadas (API, Audio, SQLite, Telegram)
```

---

## 🚀 Inicio Rápido con `uv`

### 1. Sincronizar el entorno virtual
En la raíz del proyecto ejecuta:
```bash
uv sync
```

### 2. Configurar credenciales (.env)
Copia o edita el archivo `.env`:
```env
# Azure Cognitive Services Speech (Free Tier F0: 5 horas gratis/mes)
# Obtén tu clave en https://portal.azure.com (Crear recurso 'Speech services' en plan Free F0)
AZURE_SPEECH_KEY=tu_azure_speech_key_aqui
AZURE_SPEECH_REGION=eastus

# Google Gemini API (Free Tier en Google AI Studio)
# Obtén tu clave gratis en https://aistudio.google.com ("Get API key")
GEMINI_API_KEY=tu_gemini_api_key_aqui

# Telegram Bot Token (Opcional pero recomendado para notas de voz en móvil)
# Habla con @BotFather en Telegram y genera un token
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui

PORT=8000
HOST=0.0.0.0
MOCK_MODE=auto
```

> **Nota sobre el Modo Simulación (Mock):**
> Si dejas las claves vacías o aún no las has configurado, `tut_bot` iniciará automáticamente en **Modo Simulación**, permitiéndote probar la interfaz completa, la grabación y el flujo de feedback de inmediato sin consumir cuotas.

### 3. Iniciar la aplicación

Puedes ejecutar la app con ambos canales unificados o de forma independiente:

```bash
# Opción 1: Servidor Web + Telegram Bot juntos (Recomendado)
uv run tut-bot
# O bien: uv run python run.py

# Opción 2: Solo Bot de Telegram
uv run tut-bot-telegram
```

- Si usas el navegador: Abre 👉 **[http://localhost:8000](http://localhost:8000)**
- Si usas Telegram: Busca a tu bot en la app, escribe `/start` y envía una nota de voz hablando.

---

## 🤖 Comandos del Bot de Telegram

| Comando | Acción |
| :--- | :--- |
| `/start` | Bienvenida, selector de idioma y explicación guiada. |
| `/ejercicio` o `/practicar` | Muestra la tarjeta del reto fonético actual (con IPA y consejo anatómico). |
| `/idioma` | Cambia entre Alemán (🇩🇪) e Inglés (🇺🇸). |
| `/libre <frase>` | Configura una frase libre personalizada para practicar. |
| `/stats` | Muestra tu progreso acumulado y los fonemas más desafiantes. |
| `/web` | Enlace al dashboard web. |
| 🎙️ **Nota de voz** | Simplemente deja presionado el micrófono y di la frase. |

---

## 🐳 Despliegue con Docker (PC o Jetson Nano)

El contenedor está diseñado para ser ultraligero y compatible tanto con procesadores **x86_64** (PC) como **ARM64 / aarch64** (Jetson Nano):

```bash
# Construir y levantar en segundo plano
docker compose up -d --build

# Ver logs del contenedor
docker compose logs -f

# Detener el contenedor
docker compose down
```

---

## 🧪 Pruebas y Calidad de Código

Para asegurar la integridad del repositorio conforme a las directivas de calidad:

```bash
# Ejecutar suite de pruebas unitarias:
uv run pytest

# Verificar linter de Ruff:
uv run ruff check .

# Formatear código automáticamente:
uv run ruff format .
```

---

## 📱 Cómo usarlo desde tu Teléfono Móvil

Como el servidor se enlaza a `0.0.0.0`, puedes practicar cómodamente hablando a tu celular:
1. Conecta tu móvil a la misma red Wi-Fi de tu computadora o Jetson Nano.
2. Averigua la IP local de tu máquina (en Windows: `ipconfig`, en Linux/Jetson: `hostname -I`).
3. En el navegador de tu móvil (Chrome/Safari), entra a `http://<IP_LOCAL>:8000`.
