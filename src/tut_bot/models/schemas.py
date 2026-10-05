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
    skill_type: str = (
        "speaking"  # "speaking" (Hablar) | "writing" (Escribir) | "listening" (Comprender)
    )
    title: str
    target_text: str
    prompt: Optional[str] = None  # Instrucción para escribir o escuchar (ej: "Traduce al alemán:")
    ipa: Optional[str] = None
    phonetic_guide: Optional[str] = (
        None  # Pronunciación figurada amigable en español (ej. "Ij shpreje kain doitch")
    )
    phonetic_notes: Optional[str] = (
        None  # Guía o equivalencia de símbolos (ej. "ç = ch suave, ʃ = sonido sh")
    )
    translation_es: str
    focus_phonemes: List[str] = []
    tip: str
    articulation_type: Optional[str] = None
    options: List[str] = []  # Para ejercicios de comprensión con alternativas
    correct_option_index: Optional[int] = None
    grammar_note: Optional[str] = None
    vocabulary_breakdown: Optional[dict] = (
        None  # Desglose de vocabulario de la frase {"Buch": "el libro (neutro das Buch)"}
    )
    unit_id: Optional[str] = None  # ej: "unit_1", "unit_2", etc.
    unit_title: Optional[str] = None  # ej: "Unidad 1: Saludos y Presentaciones"


class WritingEvaluationResponse(BaseModel):
    user_input: str
    target_text: str
    score: float
    is_correct: bool
    corrections: List[str] = []
    pedagogical_feedback: str
    grammar_notes: Optional[str] = None


class VocabularyExplanation(BaseModel):
    term: str
    translation: str
    part_of_speech: Optional[str] = None
    gender: Optional[str] = None  # der, die, das
    explanation: str
    examples: List[str] = []


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
