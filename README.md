# tut_bot 🎙️🇩🇪🇬🇧

**tut_bot** es un entrenador fonético interactivo inteligente para perfeccionar la pronunciación en **Alemán** e **Inglés**, desarrollado con:
- **Azure Cognitive Services Speech (Free Tier F0)**: Evaluación acústica fonema por fonema con alfabeto fonético internacional (IPA), cálculo de precisión, fluidez, completitud y prosodia.
- **Google Gemini (Google AI Studio API - Free Tier)**: Tutor pedagógico que analiza los fonemas desviados y genera explicaciones anatómicas en español sobre cómo colocar la lengua, labios y flujo de aire.
- **Web Audio API**: Grabador en el navegador calibrado a 16.000 Hz, 16 bits PCM mono (el formato estándar de alta fidelidad para reconocimiento acústico).
- **Gestión Moderna de Proyectos con `uv`**: Empaquetado estandarizado mediante `pyproject.toml` y Clean Architecture en `src/tut_bot`.
- **Soporte Docker Multiplataforma**: Contenedor optimizado y listo para correr en PC o en **NVIDIA Jetson Nano** consumiendo menos de 80 MB de memoria unificada.

---

## 📁 Estructura del Proyecto

```
tut_bot/
├── pyproject.toml              # Definición del proyecto, dependencias y herramientas (uv, ruff, pytest)
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
│       ├── main.py             # Aplicación FastAPI y routers de evaluación
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py      # Esquemas de datos Pydantic (Fonemas, Palabras, Métricas)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── azure_speech.py # Evaluación fonética y TTS con Azure SDK
│       │   ├── gemini_coach.py # Pedagogía fonética con Gemini 2.5 Flash
│       │   └── exercises.py    # Catálogo curricular fonético (Alemán / Inglés)
│       └── static/             # Interfaz web SPA (HTML5, TailwindCSS, Web Audio API)
│           ├── index.html
│           ├── css/custom.css
│           └── js/
│               ├── app.js
│               └── recorder.js
└── tests/
    ├── __init__.py
    └── test_api.py             # Pruebas automatizadas de integración y endpoints
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

PORT=8000
HOST=0.0.0.0
MOCK_MODE=auto
```

> **Nota sobre el Modo Simulación (Mock):**
> Si dejas las claves vacías o aún no las has configurado, `tut_bot` iniciará automáticamente en **Modo Simulación**, permitiéndote probar la interfaz completa, la grabación y el flujo de feedback de inmediato sin consumir cuotas.

### 3. Iniciar el servidor
Puedes iniciar la aplicación con cualquiera de los siguientes comandos:
```bash
# Opción A (CLI de uv):
uv run tut-bot

# Opción B (Runner directo):
uv run python run.py
```

Abre tu navegador en:
👉 **[http://localhost:8000](http://localhost:8000)**

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
