import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from tut_bot.config import settings
from tut_bot.models.schemas import EvaluationResponse, HealthStatus, TTSRequest
from tut_bot.services.azure_speech import azure_service
from tut_bot.services.exercises import get_categories, get_exercises
from tut_bot.services.gemini_coach import gemini_coach
from tut_bot.services.telegram_bot import telegram_bot
from tut_bot.services.tracker import tracker

import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tut_bot")


async def cleanup_orphaned_audio_files(max_age_seconds: int = 1800):
    """Limpia archivos de audio temporales huérfanos para no saturar memoria/disco en Jetson Nano."""
    temp_dir = Path(tempfile.gettempdir())
    now = time.time()
    count = 0
    patterns = ("tmp*.wav", "tmp*.ogg", "*_converted.wav", "*_voice.ogg")
    for pattern in patterns:
        for f in temp_dir.glob(pattern):
            try:
                if (now - f.stat().st_mtime) > max_age_seconds:
                    f.unlink(missing_ok=True)
                    count += 1
            except Exception:
                pass
    if count > 0:
        logger.info(f"Limpieza de disco: {count} archivo(s) de audio temporales eliminados.")


async def periodic_temp_cleaner():
    """Tarea en segundo plano que purga archivos temporales periódicamente."""
    while True:
        try:
            await asyncio.sleep(21600)  # Cada 6 horas
            await cleanup_orphaned_audio_files(max_age_seconds=1800)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error en limpieza periódica de audios: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicializa Telegram Bot y tareas de mantenimiento en segundo plano."""
    # 1. Purgar cualquier archivo temporal residual al arrancar
    await cleanup_orphaned_audio_files(max_age_seconds=600)
    cleaner_task = asyncio.create_task(periodic_temp_cleaner())

    polling_task = None
    if settings.is_telegram_ready:
        logger.info("Iniciando integración con Telegram Bot...")
        polling_task = asyncio.create_task(telegram_bot.start_polling())
    else:
        logger.info(
            "Telegram Bot no configurado (TELEGRAM_BOT_TOKEN ausente o vacío). "
            "Para activarlo, agrega TELEGRAM_BOT_TOKEN a tu archivo .env"
        )

    yield

    # Limpieza en apagado
    cleaner_task.cancel()
    if polling_task:
        await telegram_bot.stop()
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="tut_bot - Entrenador Fonético Inteligente",
    description="Evaluación acústica con Azure Speech SDK (F0), pedagogía con Google Gemini AI Studio y canal de Telegram.",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS para permitir pruebas desde dispositivos móviles en la misma red Wi-Fi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthStatus)
def health_check():
    return HealthStatus(
        status="running",
        azure_configured=azure_service.is_available(),
        gemini_configured=gemini_coach.is_available(),
        telegram_configured=telegram_bot.is_configured(),
        mock_mode=settings.is_mock_mode,
    )


@app.get("/api/exercises")
def list_exercises(
    language: Optional[str] = "de-DE",
    category: Optional[str] = None,
    level: Optional[str] = None,
):
    return get_exercises(language=language, category=category, level=level)


@app.get("/api/categories")
def list_categories(language: str = "de-DE"):
    return get_categories(language=language)


@app.get("/api/stats")
def get_user_stats(user_id: str = "web_default"):
    """Devuelve las estadísticas acumuladas, puntuación promedio y fonemas débiles."""
    return tracker.get_user_stats(user_id)


@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_audio(
    audio: UploadFile = File(...),
    reference_text: str = Form(...),
    language: str = Form("de-DE"),
    user_id: str = Form("web_default"),
):
    """
    Recibe el archivo de audio del micrófono y el texto de referencia.
    Evalúa la pronunciación con Azure, enriquece con feedback de Gemini y persiste en SQLite.
    """
    if not reference_text.strip():
        raise HTTPException(status_code=400, detail="El texto de referencia no puede estar vacío.")

    suffix = ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name
        content = await audio.read()
        temp_file.write(content)

    try:
        # 1. Evaluación acústica (Azure Speech SDK o simulación)
        eval_result = azure_service.evaluate_pronunciation(
            wav_path=temp_path,
            reference_text=reference_text.strip(),
            language=language,
        )

        # 2. Orquestador pedagógico (Gemini AI Studio)
        pedagogical_feedback = gemini_coach.generate_feedback(
            reference_text=reference_text.strip(),
            language=language,
            overall_score=eval_result.overall_score,
            words=eval_result.words,
        )
        eval_result.pedagogical_feedback = pedagogical_feedback

        # 3. Registrar en SQLite para historial pedagógico
        weak_phonemes = []
        for w in eval_result.words:
            for p in w.phonemes:
                if p.score < 70:
                    weak_phonemes.append(p.phoneme)

        tracker.record_evaluation(
            user_id=user_id,
            language=language,
            reference_text=reference_text.strip(),
            overall_score=eval_result.overall_score,
            accuracy_score=eval_result.accuracy_score,
            fluency_score=eval_result.fluency_score,
            prosody_score=eval_result.prosody_score,
            weak_phonemes=weak_phonemes,
        )

        return eval_result

    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/tts")
async def text_to_speech(payload: TTSRequest):
    """Genera audio nativo de referencia para que el usuario escuche cómo debe sonar."""
    audio_bytes = azure_service.synthesize_speech(payload.text, payload.language)
    if not audio_bytes:
        raise HTTPException(status_code=503, detail="TTS no disponible o Azure no configurado.")
    return Response(content=audio_bytes, media_type="audio/wav")


# Servir interfaz web estática
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def start():
    """Punto de entrada de ejecución con uv run tut-bot."""
    import uvicorn

    logger.info(f"Iniciando tut_bot en http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("tut_bot.main:app", host=settings.HOST, port=settings.PORT, reload=True)
