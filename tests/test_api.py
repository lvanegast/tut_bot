import io
import struct
import sys
import wave

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from tut_bot.main import app

client = TestClient(app)


def create_dummy_wav() -> bytes:
    """Crea un archivo WAV en memoria de 0.5s a 16000Hz mono con silencio/tono para pruebas."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        # 8000 muestras = 0.5 segundos
        samples = [int(0) for _ in range(8000)]
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    buffer.seek(0)
    return buffer.read()


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "azure_configured" in data
    assert "gemini_configured" in data
    assert "mock_mode" in data


def test_exercises_endpoints():
    # Alemán
    res_de = client.get("/api/exercises?language=de-DE")
    assert res_de.status_code == 200
    exercises_de = res_de.json()
    assert len(exercises_de) >= 12
    assert any(e["category"] == "ich-Laut vs ach-Laut" for e in exercises_de)
    assert any(e["category"] == "Pares Mínimos Vocálicos" for e in exercises_de)
    assert any(e["category"] == "Zungenbrecher (Trabalenguas)" for e in exercises_de)
    assert any(e.get("articulation_type") == "palatal" for e in exercises_de)

    # Inglés
    res_en = client.get("/api/exercises?language=en-US")
    assert res_en.status_code == 200
    exercises_en = res_en.json()
    assert len(exercises_en) >= 10
    assert any("TH" in e["category"] for e in exercises_en)
    assert any(e["category"] == "Pares Mínimos Vocálicos" for e in exercises_en)
    assert any(e["category"] == "Tongue Twisters (Trabalenguas)" for e in exercises_en)
    assert any(e.get("articulation_type") == "dental" for e in exercises_en)


def test_categories_endpoint():
    res = client.get("/api/categories?language=de-DE")
    assert res.status_code == 200
    categories = res.json()
    assert "ich-Laut vs ach-Laut" in categories
    assert "Umlauts (ä, ö, ü)" in categories


def test_static_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "tut_bot" in response.text
    assert "AudioRecorder" in response.text or "recorder.js" in response.text


def test_evaluate_endpoint_mock_flow():
    wav_bytes = create_dummy_wav()
    response = client.post(
        "/api/evaluate",
        data={
            "reference_text": "Ich möchte ein Buch",
            "language": "de-DE",
        },
        files={"audio": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reference_text"] == "Ich möchte ein Buch"
    assert "overall_score" in data
    assert len(data["words"]) > 0
    assert data["pedagogical_feedback"] is not None
    print("\n[OK] Test de evaluacion completado exitosamente:")
    print(f"Puntuacion Global: {data['overall_score']}")
    print(f"Feedback generado: {data['pedagogical_feedback'][:120]}...")


def test_stats_endpoint():
    res = client.get("/api/stats?user_id=web_default")
    assert res.status_code == 200
    stats = res.json()
    assert "total_attempts" in stats
    assert "average_overall" in stats
    assert "weak_phonemes_top" in stats
    assert "recent_history" in stats


def test_audio_converter_pipeline():
    from tut_bot.services.audio_converter import audio_converter

    dummy_wav = create_dummy_wav()
    # Convertir WAV a OGG Opus
    ogg_bytes = audio_converter.wav_to_ogg_opus(dummy_wav)
    assert ogg_bytes is not None
    assert len(ogg_bytes) > 0

    # Convertir OGG Opus a WAV 16kHz
    wav_converted = audio_converter.ogg_to_wav(ogg_bytes)
    assert wav_converted is not None
    assert len(wav_converted) > 0
    assert wav_converted.startswith(b"RIFF")


def test_progress_tracker():
    from tut_bot.services.tracker import tracker

    user_id = "test_unit_user_01"
    tracker.set_user_language(user_id, "de-DE")
    tracker.set_user_exercise_index(user_id, 3)
    state = tracker.get_user_state(user_id)
    assert state["language"] == "de-DE"
    assert state["exercise_index"] == 3

    tracker.record_evaluation(
        user_id=user_id,
        language="de-DE",
        reference_text="Ich möchte",
        overall_score=72.0,
        accuracy_score=70.0,
        fluency_score=75.0,
        prosody_score=71.0,
        weak_phonemes=["ç", "øː"],
    )

    stats = tracker.get_user_stats(user_id)
    assert stats["total_attempts"] >= 1
    assert any(item["phoneme"] == "ç" for item in stats["weak_phonemes_top"])


def test_telegram_bot_service():
    from tut_bot.services.telegram_bot import TelegramCoachBot

    bot = TelegramCoachBot(token="123456:TEST_TOKEN_DUMMY_FOR_UNIT_TEST")
    assert bot.is_configured() is True
    app = bot.build_app()
    assert app is not None


if __name__ == "__main__":
    test_health_endpoint()
    test_exercises_endpoints()
    test_categories_endpoint()
    test_static_index()
    test_evaluate_endpoint_mock_flow()
    test_stats_endpoint()
    test_audio_converter_pipeline()
    test_progress_tracker()
    test_telegram_bot_service()
    print("\n[EXITO] Todas las pruebas unitarias pasaron correctamente!")
