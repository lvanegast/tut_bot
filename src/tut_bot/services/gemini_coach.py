import logging
from typing import List

from tut_bot.config import settings
from tut_bot.models.schemas import WordScore

logger = logging.getLogger(__name__)

# Intentar importar el nuevo SDK de google-genai o google.generativeai
HAS_GEMINI_SDK = False
try:
    from google import genai

    HAS_NEW_GENAI = True
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_NEW_GENAI = False
    try:
        import google.generativeai as legacy_genai

        HAS_GEMINI_SDK = True
    except ImportError:
        pass


class GeminiCoachService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        if HAS_NEW_GENAI and settings.is_gemini_ready:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"No se pudo inicializar client genai: {e}")
        elif HAS_GEMINI_SDK and not HAS_NEW_GENAI and settings.is_gemini_ready:
            try:
                legacy_genai.configure(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"No se pudo configurar legacy_genai: {e}")

    def is_available(self) -> bool:
        return bool(HAS_GEMINI_SDK and settings.is_gemini_ready)

    def generate_feedback(
        self,
        reference_text: str,
        language: str,
        overall_score: float,
        words: List[WordScore],
    ) -> str:
        """
        Genera retroalimentación pedagógica y anatómica basada en los errores detectados.
        Si no hay API key o está en modo mock, devuelve un consejo pedagógico estructurado.
        """
        # Identificar palabras y fonemas deficientes (score < 75)
        problem_words = [w for w in words if w.score < 75 or w.error_type != "None"]
        problem_phonemes = []
        for w in words:
            for p in w.phonemes:
                if p.score < 70:
                    problem_phonemes.append(f"{p.phoneme} (en '{w.word}', score {p.score})")

        lang_name = "alemán" if language.startswith("de") else "inglés"

        # Si todo fue excelente (score > 88)
        if overall_score >= 88 and not problem_words:
            return (
                f"🎉 **¡Excelente pronunciación!** ({overall_score:.0f}/100).\n"
                f"Has articulado con gran precisión los sonidos en {lang_name}. ¡Mantén ese ritmo!"
            )

        if not self.is_available() or settings.is_mock_mode:
            return self._mock_pedagogical_feedback(
                reference_text, language, overall_score, problem_words
            )

        # Prompt ultra-conciso para minimizar tokens y latencia
        prompt = (
            f"Eres un entrenador fonético ultra-conciso para hispanohablantes aprendiendo {lang_name}.\n"
            f"Frase: '{reference_text}' (Puntaje global: {overall_score:.0f}/100).\n"
            f"Dificultades: {[w.word for w in problem_words[:2]]} | Fonemas: {problem_phonemes[:2]}\n\n"
            f"Responde en MÁXIMO 2 viñetas breves (menos de 45 palabras en total):\n"
            f"• 👄 **Articulación**: Dónde colocar lengua/labios para el sonido más errado en 1 sola frase directa.\n"
            f"• 🎯 **Truco**: Metáfora o mini-drill inmediato.\n"
            f"Sé directo, sin saludos ni introducciones."
        )

        try:
            if HAS_NEW_GENAI and self.client:
                # Usar modelo flash-lite rápido y económico para ahorrar tokens
                config = None
                try:
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        max_output_tokens=120,
                        temperature=0.2,
                    )
                except Exception:
                    pass

                for candidate_model in ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash-lite"]:
                    try:
                        kwargs = {"model": candidate_model, "contents": prompt}
                        if config:
                            kwargs["config"] = config
                        response = self.client.models.generate_content(**kwargs)
                        if response and response.text:
                            return response.text.strip()
                    except Exception as exc:
                        logger.warning(f"Fallo con {candidate_model}: {exc}")
                        continue
                return self._mock_pedagogical_feedback(
                    reference_text, language, overall_score, problem_words
                )
            elif HAS_GEMINI_SDK:
                model = legacy_genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                return response.text
            else:
                return self._mock_pedagogical_feedback(
                    reference_text, language, overall_score, problem_words
                )
        except Exception as e:
            logger.error(f"Error generando feedback en Gemini: {e}")
            return self._mock_pedagogical_feedback(
                reference_text, language, overall_score, problem_words
            )

    def _mock_pedagogical_feedback(
        self,
        reference_text: str,
        language: str,
        overall_score: float,
        problem_words: List[WordScore],
    ) -> str:
        """Consejos pedagógicos preconfigurados para demostración y modo sin conexión."""
        text_lower = reference_text.lower()

        if language.startswith("de"):
            if "ich" in text_lower or "möchte" in text_lower or "spreche" in text_lower:
                return (
                    f"💡 **Consejo Anatómico (Ich-Laut /ç/):**\n\n"
                    f"Notamos una ligera imprecisión en el sonido de la **'ch'** (en palabras como *{problem_words[0].word if problem_words else 'ich'}*). "
                    f"Es muy común que los hispanohablantes lo pronuncien como una 'k' dura o como una 'j' áspera española (/x/).\n\n"
                    f"**Cómo colocar la boca:** Apoya suavemente la punta de la lengua contra los dientes inferiores y levanta el dorso de la lengua hacia la mitad del paladar (como si fueras a decir 'i' o a sonreír). "
                    f"Luego, expulsa el aire con suavidad imitando el siseo suave de un gato. ¡No vibres la garganta!\n\n"
                    f"👉 **Prueba este ejercicio:** Repite lentamente: *'i... iiij... ich... möchte'*."
                )
            elif any(u in text_lower for u in ["ö", "ä", "ü"]):
                return (
                    "💡 **Consejo Anatómico (Vocales con Diéresis - Umlaut):**\n\n"
                    "El desafío principal estuvo en las vocales con diéresis. Para dominar sonidos como **'ö'** o **'ü'**, "
                    "los hispanohablantes solemos tender a pronunciar 'e' u 'o' normales.\n\n"
                    "**El truco de los dos pasos:** Pon tus labios bien redondeados hacia adelante como si fueras a decir 'O' (o mandar un beso), "
                    "y SIN mover los labios ni un milímetro, intenta articular la vocal 'E'. Ese sonido resultante es exactamente el Umlaut alemán.\n\n"
                    "👉 **Prueba este drill:** *'o ➔ ö ➔ möchte'*, sintiendo la tensión en los bordes de los labios."
                )
            else:
                return (
                    f"💡 **Consejo de Articulación en Alemán:**\n\n"
                    f"Tu puntuación fue de **{overall_score:.0f}/100**. Enfócate en articular con mayor firmeza las consonantes finales y marcar claramente las pausas entre palabras compuestas. "
                    f"En alemán las palabras no se funden tanto como en español."
                )
        else:
            if "th" in text_lower:
                return (
                    f"💡 **Consejo Anatómico (Sonido TH en Inglés):**\n\n"
                    f"Detectamos dificultad con el sonido **'th'** (como en *{problem_words[0].word if problem_words else 'think'}*). "
                    f"El error más habitual es sustituirlo por una 's', 't' o 'd'.\n\n"
                    f"**Cómo colocar la lengua:** Asoma levemente la punta de la lengua entre tus dientes incisivos superiores e inferiores. "
                    f"Deja escapar el aire rozando la lengua. Si es sordo (/θ/ en *think*), no actives las cuerdas vocales; si es sonoro (/ð/ en *this*), haz vibrar la garganta suavemente.\n\n"
                    f"👉 **Drill:** Repite *'three... third... think'*, asegurándote de ver la punta de tu lengua en el espejo."
                )
            else:
                return (
                    f"💡 **Consejo de Articulación en Inglés:**\n\n"
                    f"Tu puntuación fue de **{overall_score:.0f}/100**. Presta especial atención al contraste de vocales cortas vs. largas y recuerda pronunciar la consonante 'v' apoyando los dientes superiores en el labio inferior con fricción continua."
                )


gemini_coach = GeminiCoachService()
