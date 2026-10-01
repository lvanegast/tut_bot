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
    assert len(exercises_de) > 0
    assert any(e["category"] == "ich-Laut vs ach-Laut" for e in exercises_de)

    # Inglés
    res_en = client.get("/api/exercises?language=en-US")
    assert res_en.status_code == 200
    exercises_en = res_en.json()
    assert len(exercises_en) > 0
    assert any("TH" in e["category"] for e in exercises_en)


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


if __name__ == "__main__":
    test_health_endpoint()
    test_exercises_endpoints()
    test_categories_endpoint()
    test_static_index()
    test_evaluate_endpoint_mock_flow()
    print("\n[EXITO] Todas las pruebas unitarias pasaron correctamente!")
