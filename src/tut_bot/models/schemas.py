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
    translation_es: str
    focus_phonemes: List[str] = []
    tip: str


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
