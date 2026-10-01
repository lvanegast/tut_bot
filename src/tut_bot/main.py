import logging
import os
import tempfile
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tut_bot")

app = FastAPI(
    title="tut_bot - Entrenador Fonético Inteligente",
    description="Evaluación acústica con Azure Speech SDK (F0) y pedagogía con Google Gemini AI Studio.",
    version="1.0.0",
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


@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_audio(
    audio: UploadFile = File(...),
    reference_text: str = Form(...),
    language: str = Form("de-DE"),
):
    """
    Recibe el archivo de audio del micrófono y el texto de referencia.
    Evalúa la pronunciación con Azure y enriquece con feedback de Gemini.
    """
    if not reference_text.strip():
        raise HTTPException(status_code=400, detail="El texto de referencia no puede estar vacío.")

    # Guardar audio temporal para que el SDK de Azure lo procese
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

        return eval_result

    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Eliminar archivo temporal
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
