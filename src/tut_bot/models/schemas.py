from typing import List, Optional

from pydantic import BaseModel


class PhonemeScore(BaseModel):
    phoneme: str
    score: float


class WordScore(BaseModel):
    word: str
    score: float
    error_type: str = "None"
    phonemes: List[PhonemeScore] = []


class EvaluationResponse(BaseModel):
    recognized_text: str
    reference_text: str
    overall_score: float
    accuracy_score: float
    fluency_score: float
    completeness_score: float
    prosody_score: Optional[float] = None
    words: List[WordScore] = []
    pedagogical_feedback: Optional[str] = None
    is_mock: bool = False


class Exercise(BaseModel):
    id: str
    language: str  # "de-DE" | "en-US"
    category: str
    level: str  # "A1", "A2", "B1", "B2"
    title: str
    target_text: str
    ipa: Optional[str] = None
    phonetic_guide: Optional[str] = None  # Pronunciación figurada amigable en español (ej. "Ij shpreje kain doitch")
    phonetic_notes: Optional[str] = None  # Guía o equivalencia de símbolos (ej. "ç = ch suave, ʃ = sonido sh")
    translation_es: str
    focus_phonemes: List[str] = []
    tip: str
    articulation_type: Optional[str] = None  # "vowel", "bilabial", "labiodental", "dental", "alveolar", "postalveolar", "palatal", "velar", "uvular", "glottal"


class TTSRequest(BaseModel):
    text: str
    language: str = "de-DE"
    voice: Optional[str] = None


class HealthStatus(BaseModel):
    status: str
    azure_configured: bool
    gemini_configured: bool
    telegram_configured: bool
    mock_mode: bool
