import json
import logging
import random
from typing import List, Optional

from tut_bot.config import settings
from tut_bot.models.schemas import EvaluationResponse, PhonemeScore, WordScore

logger = logging.getLogger(__name__)

# Intentar importar azure speech sdk
try:
    import azure.cognitiveservices.speech as speechsdk

    HAS_AZURE_SDK = True
except ImportError:
    HAS_AZURE_SDK = False
    logger.warning(
        "azure-cognitiveservices-speech no está instalado. Se utilizará modo simulación."
    )


class AzureSpeechService:
    def __init__(self):
        self.key = settings.AZURE_SPEECH_KEY
        self.region = settings.AZURE_SPEECH_REGION

    def is_available(self) -> bool:
        return HAS_AZURE_SDK and settings.is_azure_ready

    def evaluate_pronunciation(
        self, wav_path: str, reference_text: str, language: str = "de-DE"
    ) -> EvaluationResponse:
        """
        Evalúa el archivo WAV contra el texto de referencia usando Azure Speech SDK.
        Si no hay credenciales o está en modo mock, recurre a una simulación fonética realista.
        """
        if not self.is_available() or settings.is_mock_mode:
            return self._mock_evaluation(reference_text, language)

        try:
            speech_config = speechsdk.SpeechConfig(subscription=self.key, region=self.region)
            speech_config.speech_recognition_language = language

            # Configuración detallada de evaluación de pronunciación
            pron_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=reference_text,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True,
            )
            pron_config.phoneme_alphabet = "IPA"
            pron_config.enable_prosody_assessment = True

            audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                language=language,
                audio_config=audio_config,
            )
            pron_config.apply_to(recognizer)

            logger.info(f"Iniciando evaluación de pronunciación en Azure ({language})...")
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                raw_json = result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult
                )
                return self._parse_azure_json(raw_json, reference_text)
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("Azure Speech no detectó voz en el audio.")
                return EvaluationResponse(
                    recognized_text="",
                    reference_text=reference_text,
                    overall_score=0.0,
                    accuracy_score=0.0,
                    fluency_score=0.0,
                    completeness_score=0.0,
                    prosody_score=0.0,
                    words=[],
                    pedagogical_feedback="No se detectó audio comprensible en la grabación. Por favor, asegúrate de hablar cerca del micrófono.",
                    is_mock=False,
                )
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(
                    f"Azure Speech cancelado: {cancellation.reason} - {cancellation.error_details}"
                )
                # Fallback suave a mock en caso de fallo de red/clave temporal
                resp = self._mock_evaluation(reference_text, language)
                resp.pedagogical_feedback = f"(Aviso: Azure no pudo autenticar: {cancellation.error_details}. Mostrando evaluación de prueba)."
                return resp

        except Exception as e:
            logger.error(f"Error llamando a Azure Speech: {e}", exc_info=True)
            resp = self._mock_evaluation(reference_text, language)
            resp.pedagogical_feedback = f"(Error con Azure SDK: {e}. Mostrando simulación)."
            return resp

    def synthesize_speech(self, text: str, language: str = "de-DE") -> Optional[bytes]:
        """Sintetiza audio nativo con Azure TTS para escuchar la pronunciación de referencia."""
        if not self.is_available():
            return None

        try:
            speech_config = speechsdk.SpeechConfig(subscription=self.key, region=self.region)
            # Voces neurales de alta calidad
            if language.startswith("de"):
                speech_config.speech_synthesis_voice_name = "de-DE-KatjaNeural"
            else:
                speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, audio_config=None
            )
            result = speech_synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            else:
                logger.warning(f"Fallo TTS: {result.reason}")
                return None
        except Exception as e:
            logger.error(f"Error en síntesis TTS: {e}")
            return None

    def _parse_azure_json(self, json_str: str, reference_text: str) -> EvaluationResponse:
        """Parsea la respuesta JSON estructurada de Azure Pronunciation Assessment."""
        data = json.loads(json_str)
        nbest = data.get("NBest", [{}])[0]
        pron_details = nbest.get("PronunciationAssessment", {})

        words_list: List[WordScore] = []
        for w in nbest.get("Words", []):
            word_str = w.get("Word", "")
            w_pron = w.get("PronunciationAssessment", {})
            w_score = float(w_pron.get("AccuracyScore", 0.0))
            error_type = w_pron.get("ErrorType", "None")

            phonemes_list: List[PhonemeScore] = []
            for p in w.get("Phonemes", []):
                phonemes_list.append(
                    PhonemeScore(
                        phoneme=p.get("Phoneme", ""),
                        score=float(p.get("PronunciationAssessment", {}).get("AccuracyScore", 0.0)),
                    )
                )

            words_list.append(
                WordScore(
                    word=word_str,
                    score=w_score,
                    error_type=error_type,
                    phonemes=phonemes_list,
                )
            )

        return EvaluationResponse(
            recognized_text=nbest.get("Display", ""),
            reference_text=reference_text,
            overall_score=float(pron_details.get("PronScore", 0.0)),
            accuracy_score=float(pron_details.get("AccuracyScore", 0.0)),
            fluency_score=float(pron_details.get("FluencyScore", 0.0)),
            completeness_score=float(pron_details.get("CompletenessScore", 100.0)),
            prosody_score=float(pron_details.get("ProsodyScore", 0.0))
            if "ProsodyScore" in pron_details
            else None,
            words=words_list,
            is_mock=False,
        )

    def _mock_evaluation(self, reference_text: str, language: str) -> EvaluationResponse:
        """Genera una evaluación fonética simulada con errores típicos para pruebas sin credenciales."""
        tokens = reference_text.strip().rstrip(".,?!").split()
        words_list: List[WordScore] = []
        total_score = 0.0

        for word in tokens:
            clean_word = word.strip(".,?!")
            lower = clean_word.lower()

            # Simular errores realistas según patrones conocidos de hispanohablantes
            is_difficult = any(x in lower for x in ["ch", "ö", "ä", "ü", "th", "v", "r", "sch"])
            if is_difficult:
                w_score = round(random.uniform(52.0, 74.0), 1)
                err_type = "Mispronunciation"
            else:
                w_score = round(random.uniform(85.0, 98.0), 1)
                err_type = "None"

            total_score += w_score

            # Generar fonemas aproximados
            phonemes: List[PhonemeScore] = []
            for char in clean_word:
                ipa_char = char.lower()
                if ipa_char in "aeiouäöü":
                    p_score = w_score + random.uniform(-4, 4)
                else:
                    p_score = w_score + random.uniform(-8, 8)
                phonemes.append(
                    PhonemeScore(phoneme=ipa_char, score=max(10.0, min(100.0, round(p_score, 1))))
                )

            words_list.append(
                WordScore(
                    word=clean_word,
                    score=w_score,
                    error_type=err_type,
                    phonemes=phonemes,
                )
            )

        avg_score = round(total_score / max(1, len(tokens)), 1)
        fluency = round(max(50.0, avg_score - random.uniform(2, 8)), 1)
        completeness = 100.0
        prosody = round(max(55.0, avg_score - random.uniform(0, 5)), 1)

        return EvaluationResponse(
            recognized_text=reference_text,
            reference_text=reference_text,
            overall_score=avg_score,
            accuracy_score=avg_score,
            fluency_score=fluency,
            completeness_score=completeness,
            prosody_score=prosody,
            words=words_list,
            is_mock=True,
        )


azure_service = AzureSpeechService()
