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
    tracker.set_user_skill_mode(user_id, "writing")
    tracker.set_user_level(user_id, "A2")
    tracker.set_user_exercise_index(user_id, 3)
    state = tracker.get_user_state(user_id)
    assert state["language"] == "de-DE"
    assert state["exercise_index"] == 3
    assert state["skill_mode"] == "writing"
    assert state["level"] == "A2"

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


def test_exercises_skill_and_level_filtering():
    from tut_bot.services.exercises import get_exercises

    # Habla A1 en alemán
    de_speaking_a1 = get_exercises(language="de-DE", level="A1", skill_type="speaking")
    assert len(de_speaking_a1) > 0
    assert all(e.skill_type == "speaking" for e in de_speaking_a1)

    # Escritura A1 en alemán
    de_writing_a1 = get_exercises(language="de-DE", level="A1", skill_type="writing")
    assert len(de_writing_a1) > 0
    assert all(e.skill_type == "writing" for e in de_writing_a1)
    assert de_writing_a1[0].prompt is not None

    # Comprensión auditiva A1 en alemán (soporta 'listening' y alias 'comprehension')
    de_comp_a1 = get_exercises(language="de-DE", level="A1", skill_type="listening")
    assert len(de_comp_a1) > 0
    assert all(e.skill_type == "listening" for e in de_comp_a1)
    assert len(de_comp_a1[0].options) > 0

    de_comp_alias = get_exercises(language="de-DE", level="A1", skill_type="comprehension")
    assert len(de_comp_alias) == len(de_comp_a1)

    # Escritura en inglés
    en_writing = get_exercises(language="en-US", skill_type="writing")
    assert len(en_writing) > 0


def test_gemini_coach_multiskill():
    from tut_bot.services.gemini_coach import gemini_coach

    # Prueba de evaluación de escritura con coincidencia exacta
    res_exact = gemini_coach.evaluate_writing(
        user_input="Ich heiße Lucas.",
        target_text="Ich heiße Lucas.",
        prompt="Escribe en alemán: 'Me llamo Lucas.'",
        language="de-DE",
    )
    assert res_exact.is_correct is True
    assert res_exact.score == 100.0

    # Prueba de evaluación de escritura con texto diferente
    res_diff = gemini_coach.evaluate_writing(
        user_input="Mein Name ist Lucas",
        target_text="Ich heiße Lucas.",
        prompt="Escribe en alemán: 'Me llamo Lucas.'",
        language="de-DE",
    )
    assert res_diff.score is not None
    assert res_diff.pedagogical_feedback is not None

    # Prueba de explicación de vocabulario
    vocab_explanation = gemini_coach.explain_vocabulary(
        term_or_phrase="Krankenhaus", language="de-DE"
    )
    assert "Krankenhaus" in vocab_explanation or len(vocab_explanation) > 10

    # Prueba de evaluación de comprensión auditiva con opciones múltiples
    comp_eval = gemini_coach.evaluate_comprehension(
        user_answer="A las 08:00",
        audio_transcript="Der Zug fährt um 08:00 Uhr ab.",
        question="¿A qué hora sale el tren?",
        target_answer="A las 08:00",
        options=["A las 07:00", "A las 08:00", "A las 09:00"],
    )
    assert comp_eval["is_correct"] is True
    assert comp_eval["score"] == 100.0


def test_telegram_bot_service():
    from tut_bot.services.telegram_bot import TelegramCoachBot

    bot = TelegramCoachBot(token="123456:TEST_TOKEN_DUMMY_FOR_UNIT_TEST")
    assert bot.is_configured() is True
    app = bot.build_app()
    assert app is not None


def test_fsm_progression_and_level_graduation():
    from tut_bot.services.tracker import tracker

    user_id = "test_fsm_user_flow"
    tracker.set_user_language(user_id, "de-DE")
    tracker.set_user_level(user_id, "A1")
    tracker.set_user_skill_mode(user_id, "speaking")

    # 1. Estado inicial
    state = tracker.get_user_state(user_id)
    assert state["fsm_state"] == "IN_EXERCISE"
    assert state["exercise_index"] == 0
    assert "A1" in state["unlocked_levels"]

    # 2. Avance secuencial en el nivel (ej: total 3 ejercicios)
    step1 = tracker.advance_exercise_fsm(user_id, total_exercises=3)
    assert step1["status"] == "next_exercise"
    assert step1["index"] == 1

    step2 = tracker.advance_exercise_fsm(user_id, total_exercises=3)
    assert step2["status"] == "next_exercise"
    assert step2["index"] == 2

    # 3. Al completar el último ejercicio, NO debe entrar en bucle infinito
    step3 = tracker.advance_exercise_fsm(user_id, total_exercises=3)
    assert step3["status"] == "level_completed"
    assert step3["level"] == "A1"
    assert step3["next_level"] == "A2"

    state = tracker.get_user_state(user_id)
    assert state["fsm_state"] == "LEVEL_COMPLETED"
    assert "A2" in state["unlocked_levels"]
    assert "de-DE_A1_speaking" in state["passed_levels"]

    # 4. Probar graduación formal / ascenso al siguiente nivel CEFR
    ascend_res = tracker.ascend_to_next_level(user_id)
    assert ascend_res == "A2"

    state = tracker.get_user_state(user_id)
    assert state["level"] == "A2"
    assert state["exercise_index"] == 0
    assert state["fsm_state"] == "IN_EXERCISE"

    # 5. Registro de ejercicios completados individualmente
    tracker.mark_exercise_completed(user_id, "de_a1_spk_01")
    state = tracker.get_user_state(user_id)
    assert "de_a1_spk_01" in state["completed_exercises"]


def test_curriculum_and_vocabulary_tracking():
    from tut_bot.services.curriculum import (
        TOTAL_A1_LEXICON_COUNT,
        get_curriculum_units,
        get_unit_by_id,
    )
    from tut_bot.services.exercises import get_exercises
    from tut_bot.services.tracker import tracker

    # 1. Malla curricular oficial A1: 6 unidades en alemán y 6 en inglés
    de_units = get_curriculum_units("de-DE", "A1")
    assert len(de_units) == 6
    assert de_units[0].id == "unit_1"
    assert de_units[1].id == "unit_2"
    assert "kaffee" in [w.lower() for w in de_units[1].target_words]

    en_units = get_curriculum_units("en-US", "A1")
    assert len(en_units) == 6
    assert en_units[0].id == "unit_1"

    u2 = get_unit_by_id("unit_2", "de-DE", "A1")
    assert u2 is not None
    assert u2.icon == "☕"

    # 2. Selección de unidad en tracker
    user_id = "test_user_curriculum_01"
    tracker.set_user_unit(user_id, "unit_2")
    state = tracker.get_user_state(user_id)
    assert state["active_unit"] == "unit_2"

    # 3. Filtrado de ejercicios por unidad temática
    unit_exs = get_exercises(language="de-DE", level="A1", unit_id="unit_2")
    assert len(unit_exs) > 0

    # 4. Registro y progreso de inventario léxico (Goethe Start Deutsch 1 - 650 palabras)
    learned = ["kaffee", "brot", "wasser", "xyz_no_existe_en_goethe"]
    added_count = tracker.record_mastered_words(user_id, "de-DE", learned, level="A1")
    assert added_count >= 3

    progress = tracker.get_user_lexicon_progress(user_id, "de-DE", "A1")
    assert progress["total_target"] == TOTAL_A1_LEXICON_COUNT
    assert progress["mastered_count"] >= 3
    assert progress["percentage"] > 0.0
    assert "kaffee" in progress["mastered_words"]


if __name__ == "__main__":
    test_health_endpoint()
    test_exercises_endpoints()
    test_categories_endpoint()
    test_static_index()
    test_evaluate_endpoint_mock_flow()
    test_stats_endpoint()
    test_audio_converter_pipeline()
    test_progress_tracker()
    test_exercises_skill_and_level_filtering()
    test_gemini_coach_multiskill()
    test_telegram_bot_service()
    test_fsm_progression_and_level_graduation()
    test_curriculum_and_vocabulary_tracking()
    print("\n[EXITO] Todas las pruebas unitarias pasaron correctamente!")
