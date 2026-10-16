import json
import logging
from typing import List, Optional

from tut_bot.config import settings
from tut_bot.models.schemas import WordScore, WritingEvaluationResponse

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
            f"REGLA CRÍTICA: NUNCA uses encabezados con almohadillas (# o ##). Sé directo, sin saludos ni introducciones."
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

                for candidate_model in [
                    "gemini-flash-lite-latest",
                    "gemini-flash-latest",
                    "gemini-2.5-flash-lite",
                ]:
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

    def evaluate_writing(
        self,
        user_input: str,
        target_text: str,
        prompt: str,
        language: str = "de-DE",
        level: str = "A1",
    ) -> WritingEvaluationResponse:
        """Evalúa un texto escrito por el usuario contra la meta pedagógica (traducción, gramática, ortografía)."""
        clean_user = user_input.strip()
        clean_target = target_text.strip()
        lang_name = "alemán" if language.startswith("de") else "inglés"

        # Coincidencia idéntica
        if clean_user.lower() == clean_target.lower():
            return WritingEvaluationResponse(
                user_input=clean_user,
                target_text=clean_target,
                score=100.0,
                is_correct=True,
                corrections=[],
                pedagogical_feedback="¡Excelente! Tu respuesta es 100% correcta y natural.",
                grammar_notes="Estructura y ortografía impecables.",
            )

        if not self.is_available() or settings.is_mock_mode:
            match_chars = sum(1 for a, b in zip(clean_user.lower(), clean_target.lower()) if a == b)
            sim_score = round(
                max(30.0, min(95.0, (match_chars / max(1, len(clean_target))) * 100)), 1
            )
            is_correct = sim_score >= 80.0
            return WritingEvaluationResponse(
                user_input=clean_user,
                target_text=clean_target,
                score=sim_score,
                is_correct=is_correct,
                corrections=[f"Forma esperada: {clean_target}"],
                pedagogical_feedback="Buen intento. Compara tu respuesta con la frase modelo."
                if is_correct
                else "Revisa las diferencias con la frase esperada.",
                grammar_notes=f"Recuerda cuidar la concordancia en {lang_name} para nivel {level}.",
            )

        ai_prompt = (
            f"Eres un profesor experto de {lang_name} (nivel {level}) evaluando una respuesta escrita de un alumno hispanohablante.\n"
            f"Consigna: {prompt}\n"
            f"Texto esperado: '{clean_target}'\n"
            f"Respuesta del alumno: '{clean_user}'\n\n"
            f"Analiza si la respuesta del alumno es válida, gramaticalmente correcta y natural.\n"
            f"Responde ESTRICTAMENTE con un JSON válido con este formato:\n"
            f'{{"score": 85, "is_correct": true, "corrections": ["detalle del error"], "pedagogical_feedback": "Consejo breve en español", "grammar_notes": "Regla gramatical clave"}}\n'
            f"Si es totalmente correcta aunque use sinónimos válidos, dale score >= 90 e is_correct=true."
        )

        try:
            if HAS_NEW_GENAI and self.client:
                for candidate_model in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
                    try:
                        res = self.client.models.generate_content(
                            model=candidate_model,
                            contents=ai_prompt,
                        )
                        if res and res.text:
                            text_raw = res.text.strip()
                            if "```json" in text_raw:
                                text_raw = text_raw.split("```json")[1].split("```")[0].strip()
                            elif "```" in text_raw:
                                text_raw = text_raw.split("```")[1].split("```")[0].strip()
                            data = json.loads(text_raw)
                            return WritingEvaluationResponse(
                                user_input=clean_user,
                                target_text=clean_target,
                                score=float(data.get("score", 70.0)),
                                is_correct=bool(data.get("is_correct", False)),
                                corrections=data.get("corrections", []),
                                pedagogical_feedback=data.get(
                                    "pedagogical_feedback", "Buen trabajo practicando."
                                ),
                                grammar_notes=data.get("grammar_notes"),
                            )
                    except Exception as err:
                        logger.warning(f"Error procesando JSON de Gemini en escritura: {err}")
                        continue
        except Exception as e:
            logger.error(f"Error en evaluate_writing: {e}")

        return WritingEvaluationResponse(
            user_input=clean_user,
            target_text=clean_target,
            score=70.0,
            is_correct=False,
            corrections=[f"Respuesta esperada: {clean_target}"],
            pedagogical_feedback=f"Compara tu respuesta con la frase correcta: '{clean_target}'.",
            grammar_notes=f"Presta atención al orden de palabras y artículos en {lang_name}.",
        )

    def explain_vocabulary(self, term_or_phrase: str, language: str = "de-DE") -> str:
        """Explica detalladamente una palabra o frase desconocida en español con ejemplos y gramática."""
        term = term_or_phrase.strip()
        lang_name = "alemán" if language.startswith("de") else "inglés"

        if not self.is_available() or settings.is_mock_mode:
            return (
                f"📖 <b>Vocabulario: {term}</b> ({lang_name.capitalize()})\n\n"
                f"• <b>Significado:</b> Término de práctica frecuente.\n"
                f"• <b>Consejo:</b> Úsalo en tus oraciones cotidianas para automatizarlo."
            )

        prompt = (
            f"El usuario no conoce o pregunta por la palabra/frase en {lang_name}: '{term}'.\n"
            f"Explícasela en español de forma súper clara y pedagógica (menos de 60 palabras):\n"
            f"1. Significado exacto en español.\n"
            f"2. Categoría gramatical (si es sustantivo alemán incluye artículo der/die/das y plural; si es verbo sus formas clave).\n"
            f"3. Un ejemplo corto y práctico con su traducción al español.\n"
            f"Formato directo con viñetas limpias."
        )

        try:
            if HAS_NEW_GENAI and self.client:
                for candidate_model in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
                    try:
                        res = self.client.models.generate_content(
                            model=candidate_model,
                            contents=prompt,
                        )
                        if res and res.text:
                            return res.text.strip()
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error en explain_vocabulary: {e}")

        return f"📖 <b>{term}</b>: Término en {lang_name}."

    def evaluate_comprehension(
        self,
        user_answer: str,
        audio_transcript: str,
        question: str,
        target_answer: str,
        language: str = "de-DE",
        options: Optional[List[str]] = None,
    ) -> dict:
        """Evalúa si la respuesta del usuario demuestra comprensión del audio escuchado."""
        clean_user = user_answer.strip()
        clean_target = target_answer.strip()
        lang_name = "alemán" if language.startswith("de") else "inglés"

        if clean_user.lower() == clean_target.lower():
            return {
                "score": 100.0,
                "is_correct": True,
                "feedback": "¡Entendiste el audio perfectamente! Captaste el dato clave a la primera.",
            }

        options_section = ""
        if options:
            opts_formatted = "\n".join([f"{i + 1}. {opt}" for i, opt in enumerate(options)])
            options_section = (
                f"\nOpciones del ejercicio:\n{opts_formatted}\n"
                f"Nota: Si el alumno responde con el número (ej: '1'), letra o texto de la opción correcta, evalúala como correcta.\n"
            )

        if not self.is_available() or settings.is_mock_mode:
            is_ok = any(word in clean_user.lower() for word in clean_target.lower().split())
            return {
                "score": 85.0 if is_ok else 50.0,
                "is_correct": is_ok,
                "feedback": f"Respuesta esperada: {clean_target}."
                if not is_ok
                else "¡Bien entendido!",
            }

        prompt = (
            f"Un alumno de {lang_name} escuchó un audio con este texto: '{audio_transcript}'.\n"
            f"Pregunta formulada: {question}\n"
            f"Respuesta esperada: '{clean_target}'\n"
            f"{options_section}"
            f"Respuesta que dio el alumno: '{clean_user}'\n\n"
            f"¿El alumno comprendió el significado correctamente? Responde en JSON:\n"
            f'{{"score": 90, "is_correct": true, "feedback": "Breve retroalimentación en español (1-2 frases)"}}'
        )

        try:
            if HAS_NEW_GENAI and self.client:
                for candidate_model in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
                    try:
                        res = self.client.models.generate_content(
                            model=candidate_model,
                            contents=prompt,
                        )
                        if res and res.text:
                            text_raw = res.text.strip()
                            if "```json" in text_raw:
                                text_raw = text_raw.split("```json")[1].split("```")[0].strip()
                            elif "```" in text_raw:
                                text_raw = text_raw.split("```")[1].split("```")[0].strip()
                            return json.loads(text_raw)
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error evaluando comprensión: {e}")

        return {
            "score": 60.0,
            "is_correct": False,
            "feedback": f"La respuesta esperada era: '{clean_target}'. Vuelve a escuchar el audio prestando atención a los detalles.",
        }

    def generate_conversation_reply(
        self,
        scenario_title: str,
        character_name: str,
        character_role: str,
        mission_brief: str,
        target_phrases: List[str],
        dialogue_history: List[dict],
        user_message: str,
        language: str = "de-DE",
        personality_traits: str = "",
        catchphrases: Optional[List[str]] = None,
    ) -> dict:
        """
        Genera la réplica del personaje en un roleplay conversacional interactivo.
        Garantiza flujo conversacional dinámico, evita desviaciones de tema (re-anchoring),
        adapta vocabulario a CEFR estricto y asiste con andamiaje si el alumno se bloquea.
        """
        lang_name = "alemán" if language.startswith("de") else "inglés"

        # Mantener los últimos 10 turnos para memoria contextual fluida
        # Excluir el último turno si ya es idéntico a user_message para evitar duplicación
        history_to_format = list(dialogue_history) if dialogue_history else []
        if history_to_format and history_to_format[-1].get("text") == user_message:
            history_to_format = history_to_format[:-1]
        recent_history = history_to_format[-10:]

        history_lines = [
            f"- {turn.get('name', turn.get('role', 'Interlocutor'))}: {turn.get('text', '')}"
            for turn in recent_history
        ]
        history_text = "\n".join(history_lines) if history_lines else "(Inicio de la conversación)"

        user_turn_count = sum(1 for t in dialogue_history if t.get("role") == "user")

        # Fallbacks contextuales por personaje y escenario con andamiaje dinámico (suggested_replies)
        scenario_flows_de = {
            "Frau Müller": [
                ("Guten Tag! Herzlich willkommen im Kurs. Wie heißen Sie?", "¡Buenas tardes! Bienvenido/a al curso. ¿Cómo se llama usted?", ["Ich heiße...", "Mein Name ist..."]),
                ("Sehr schön! Und woher kommen Sie?", "¡Muy bien! ¿Y de dónde viene usted?", ["Ich komme aus Spanien.", "Aus Mexiko, und Sie?"]),
                ("Ausgezeichnet. Können Sie bitte Ihren Namen buchstabieren?", "Excelente. ¿Puede deletrear su nombre por favor?", ["Ja, gerne.", "Klar!"]),
                ("Vielen Dank! Herzlich willkommen. Nehmen Sie bitte Platz.", "¡Muchas gracias! Bienvenido/a. Tome asiento por favor.", ["Danke schön!", "Vielen Dank!"]),
            ],
            "Herr Schmidt": [
                ("Guten Morgen! Was möchten Sie bitte?", "¡Buenos días! ¿Qué desea por favor?", ["Ich möchte zwei Brötchen bitte.", "Einen Kaffee bitte!"]),
                ("Sehr gerne! Zwei Brötchen. Möchten Sie auch einen Kaffee?", "¡Con gusto! Dos panecillos. ¿Desea también un café?", ["Ja, bitte!", "Nein danke, nur die Brötchen."]),
                ("Das macht vier Euro bitte. Zahlen Sie bar oder mit Karte?", "Son cuatro euros por favor. ¿Paga en efectivo o con tarjeta?", ["Ich zahle bar.", "Mit Karte bitte."]),
                ("Vielen Dank! Einen schönen Tag noch!", "¡Muchas gracias! ¡Que tenga un buen día!", ["Danke, gleichfalls!", "Tschüss!"]),
            ],
            "Lukas": [
                ("Guten Morgen! Na, was darf es denn heute Leckeres sein?", "¡Buenos días! ¿Qué se te antoja de rico para hoy?", ["Ich möchte zwei Brötchen bitte.", "Ein Kaffee bitte!"]),
                ("Alles klar! Geht sofort los. Möchtest du auch Milch oder Zucker dazu?", "¡Entendido! Sale de inmediato. ¿Deseas leche o azúcar?", ["Mit Milch bitte.", "Nein danke, schwarz."]),
                ("Das macht vier Euro bitte. Wie viel möchtest du zahlen: bar oder mit Karte?", "Son cuatro euros por favor. ¿Cómo vas a pagar: efectivo o tarjeta?", ["Ich zahle bar.", "Mit Karte bitte."]),
                ("Perfekt! Guten Appetit und einen schönen Tag noch!", "¡Perfecto! ¡Buen provecho y que tengas un lindo día!", ["Danke gleichfalls!", "Tschüss Lukas!"]),
            ],
            "Felix": [
                ("Hallo! Bist du auch neu hier auf dem Campus? Erzähl mal, hast du Geschwister?", "¡Hola! ¿Tú también eres nuevo aquí en el campus? Cuéntame, ¿tienes hermanos?", ["Ich habe einen Bruder.", "Nein, keine Geschwister."]),
                ("Ach so! Und wohnen deine Eltern auch in der Stadt?", "¡Ah, ya veo! ¿Y tus padres también viven en la ciudad?", ["Meine Eltern wohnen in...", "Nein, sie wohnen weit weg."]),
                ("Mega interessant! Und wie alt bist du eigentlich?", "¡Mega interesante! ¿Y cuántos años tienes en realidad?", ["Ich bin zwanzig Jahre alt.", "Ich bin fünfundzwanzig."]),
                ("Super! Schön dich kennenzulernen. Bis später auf dem Campus!", "¡Súper! Un gusto conocerte. ¡Hasta luego en el campus!", ["Bis später Felix!", "Tschüss!"]),
            ],
            "Anna": [
                ("Hallo! Hast du am Samstag Zeit?", "¡Hola! ¿Tienes tiempo el sábado?", ["Ja, ich habe Zeit!", "Am Samstag kann ich."]),
                ("Super Idee! Um wie viel Uhr treffen wir uns?", "¡Estupenda idea! ¿A qué hora nos encontramos?", ["Um zehn Uhr?", "Um drei Uhr nachmittags."]),
                ("Das passt mir gut! Wo treffen wir uns?", "¡Me viene muy bien! ¿Dónde nos encontramos?", ["Im Park?", "Am Café."]),
                ("Perfekt! Abgemacht, dann bis Samstag. Tschüss!", "¡Perfecto! ¡Trato hecho, hasta el sábado. Chao!", ["Bis Samstag!", "Tschüss Anna!"]),
            ],
            "Herr Becker": [
                ("Guten Tag! Informationsschalter Hauptbahnhof. Wie kann ich Ihnen helfen?", "¡Buenas tardes! Mostrador de información de la estación central. ¿Cómo le puedo ayudar?", ["Wo ist der Bus?", "Entschuldigung, wo ist Gleis drei?"]),
                ("Der Bus hält direkt vor dem Haupteingang. Die Züge nach München fahren auf Gleis drei ab.", "El autobús para justo frente a la entrada principal. Los trenes a Múnich salen del andén tres.", ["Vielen Dank!", "Danke für die Hilfe!"]),
                ("Bitte sehr! Der nächste Zug fährt pünktlich um vierzehn Uhr.", "¡De nada! El próximo tren sale puntual a las catorce horas.", ["Sehr gut, danke!", "Auf Gleis drei, danke!"]),
                ("Pünktlich wie die Bahn! Gute Reise und auf Wiedersehen!", "¡Puntual como el tren! ¡Buen viaje y hasta luego!", ["Auf Wiedersehen!", "Danke schön!"]),
            ],
            "Herr Weber": [
                ("Guten Tag! Wie kann ich Ihnen helfen?", "¡Buenas tardes! ¿Cómo le puedo ayudar?", ["Wo ist der Bahnhof?", "Entschuldigung, wo ist der Zug?"]),
                ("Der Bahnhof ist geradeaus und dann links.", "La estación está derecho y luego a la izquierda.", ["Vielen Dank!", "Danke schön!"]),
                ("Der Zug fährt auf Gleis drei ab.", "El tren sale del andén tres.", ["Danke für die Hilfe!", "Auf Gleis drei, danke!"]),
                ("Gute Reise und auf Wiedersehen!", "¡Buen viaje y hasta luego!", ["Auf Wiedersehen!", "Danke!"]),
            ],
            "Frau Wagner": [
                ("Guten Tag! Was fehlt Ihnen denn? Wie kann ich helfen?", "¡Buenas tardes! ¿Qué le ocurre? ¿Cómo le puedo ayudar?", ["Ich habe Kopfschmerzen.", "Mein Bauch tut weh."]),
                ("Haben Sie auch Fieber?", "¿Tiene también fiebre?", ["Nein, kein Fieber.", "Ja, ein bisschen Fieber."]),
                ("Hier sind Tabletten gegen die Schmerzen. Nehmen Sie eine mit Wasser.", "Aquí tiene pastillas para el dolor. Tome una con agua.", ["Vielen Dank Frau Wagner.", "Wie oft am Tag?"]),
                ("Keine Sorge, das hilft schnell. Gute Besserung und auf Wiedersehen!", "¡No se preocupe, esto alivia rápido. Que se mejore y hasta luego!", ["Danke sehr, auf Wiedersehen!", "Tschüss!"]),
            ],
        }

        scenario_flows_en = {
            "Ms. Miller": [
                ("Good morning! Welcome to the class. What is your name?", "¡Buenos días! Bienvenido a la clase. ¿Cuál es tu nombre?", ["My name is...", "I am..."]),
                ("Nice to meet you! Where are you from?", "¡Gusto en conocerte! ¿De dónde eres?", ["I am from Spain.", "I am from Mexico, and you?"]),
                ("Great! Can you spell your name please?", "¡Genial! ¿Puedes deletrear tu nombre por favor?", ["Yes, of course.", "Sure!"]),
                ("Thank you! Please take a seat.", "¡Gracias! Por favor toma asiento.", ["Thank you!", "Thanks a lot!"]),
            ],
            "Tom": [
                ("Hello there! What can I get started for you today?", "¡Hola! A ver, ¿qué te puedo preparar hoy?", ["A coffee, please.", "Can I have a tea and croissant?"]),
                ("Right away! Would you like coffee with milk or sugar?", "¡Sale enseguida! ¿Te gustaría café con leche o azúcar?", ["With milk, please.", "Black coffee, please."]),
                ("That is four pounds please. Cash or card, mate?", "Son cuatro libras por favor. ¿Efectivo o tarjeta, amigo?", ["Cash, please.", "By card, please."]),
                ("Cheers mate! Have a lovely day ahead!", "¡Gracias amigo! ¡Que tengas un lindo día!", ["Thank you, you too!", "Cheers Tom!"]),
            ],
            "Oliver": [
                ("Hi! Great to meet you. Do you have any brothers or sisters back home?", "¡Hola! Un gusto conocerte. ¿Tienes hermanos o hermanas en tu ciudad?", ["I have one brother.", "No, I am an only child."]),
                ("That's awesome! Where do your parents live?", "¡Qué bien! ¿Dónde viven tus padres?", ["My parents live in Spain.", "They live in Colombia."]),
                ("Sounds cool! How old are you, by the way?", "¡Suena genial! ¿Cuántos años tienes, por cierto?", ["I am twenty years old.", "I am twenty-five."]),
                ("Brilliant! Really great to meet you flatmate!", "¡Brillante! ¡Genial conocerte compañero de piso!", ["Nice to meet you too Oliver!", "See you!"]),
            ],
            "Sarah": [
                ("Hey! Are you free this weekend? What time should we meet up?", "¡Hola! ¿Estás libre este fin de semana? ¿A qué hora deberíamos encontrarnos?", ["On Saturday at two?", "Yes, I am free!"]),
                ("Sounds like a plan! Where do you want to go?", "¡Me parece un gran plan! ¿A dónde quieres ir?", ["To the park?", "To the cafe for brunch."]),
                ("Can't wait! At three o'clock sounds totally perfect for me.", "¡No puedo esperar! A las tres me queda totalmente perfecto.", ["Awesome!", "See you at three."]),
                ("Perfect! See you on Saturday! Bye!", "¡Perfecto! ¡Nos vemos el sábado! ¡Chao!", ["See you then!", "Bye Sarah!"]),
            ],
            "Officer Davis": [
                ("Hello there! Can I help you with directions today?", "¡Hola! ¿Puedo ayudarte con direcciones hoy?", ["Excuse me, where is the station?", "Where is the bus stop?"]),
                ("The underground station is straight ahead and then on your left.", "La estación del metro está todo derecho y luego a tu izquierda.", ["Thank you very much!", "Thanks officer!"]),
                ("Mind the gap on the platform, and the bus stop is just across the street.", "Cuidado con el hueco en el andén, y la parada de autobús está cruzando la calle.", ["Got it, thank you!", "Thanks for your help!"]),
                ("You are very welcome. Have a safe trip around London!", "De nada. ¡Que tengas un viaje seguro por Londres!", ["Thank you, goodbye!", "Bye!"]),
            ],
            "Dr. Jenkins": [
                ("Hello. What seems to be the problem today?", "Hola. ¿Cuál parece ser el problema hoy?", ["I have a headache.", "I have a sore throat."]),
                ("I see. Do you also have a fever?", "Ya veo. ¿Tienes también fiebre?", ["No, no fever.", "Yes, a little bit."]),
                ("Here is some mild medicine for the headache. Take one tablet with water.", "Aquí tienes medicina suave para el dolor de cabeza. Toma una pastilla con agua.", ["Thank you doctor.", "How many times a day?"]),
                ("Take care now, drink plenty of water, and get well soon!", "¡Cuídate, bebe mucha agua y que te mejores pronto!", ["Thank you, doctor!", "Goodbye!"]),
            ],
        }

        flows = scenario_flows_de if language.startswith("de") else scenario_flows_en
        char_flow = flows.get(character_name)
        if not char_flow:
            # Buscar por coincidencia parcial de nombre
            for k, f in flows.items():
                if k.lower() in character_name.lower():
                    char_flow = f
                    break
        if not char_flow:
            char_flow = list(flows.values())[0]

        if not self.is_available() or settings.is_mock_mode:
            idx = min(user_turn_count - 1 if user_turn_count > 0 else 0, len(char_flow) - 1)
            step = char_flow[idx]
            rep_native = step[0]
            rep_es = step[1]
            sugg_replies = step[2] if len(step) > 2 else list(target_phrases[:2])
            is_goal_met = user_turn_count >= len(char_flow)
            return {
                "reply_native": rep_native,
                "reply_es": rep_es,
                "mission_status": "goal_achieved" if is_goal_met else "in_progress",
                "feedback_tip": None,
                "suggested_replies": sugg_replies,
            }

        persona_context = ""
        if personality_traits or catchphrases:
            catch_str = f"Muletillas habituales (úsala si encaja natural): {', '.join(catchphrases)}" if catchphrases else ""
            persona_context = (
                f"PERFIL Y PERSONALIDAD DEL PERSONAJE ({character_name} - ESTILO LINGOLOOPER):\n"
                f"- Rasgos: {personality_traits}\n"
                f"- {catch_str}\n\n"
            )

        prompt = (
            f"Actúas como {character_name} ({character_role}) en una conversación interactiva de la vida real con un alumno hispanohablante aprendiendo {lang_name} (nivel CEFR A1/A2).\n"
            f"Escenario: {scenario_title}\n"
            f"Misión del alumno: {mission_brief}\n"
            f"Frases clave esperadas: {', '.join(target_phrases)}\n\n"
            f"{persona_context}"
            f"Historial del diálogo previo:\n{history_text}\n"
            f"- Alumno (último mensaje que acaba de enviar): {user_message}\n\n"
            f"PEDAGOGÍA MODERNA Y FILOSOFÍA DE CONVERSACIÓN (MÁXIMA PRIORIDAD):\n"
            f"1. PERSONALIDAD CÁLIDA Y AMIGABLE (LANGUAGE BUDDY):\n"
            f"   - Sé una persona real, empática, amable y atenta. Muestra entusiasmo o curiosidad natural según la situación (usa interjecciones cotidianas como 'Ach so!', 'Wie schön!', 'Toll!', 'Oh great!', 'Awesome!').\n"
            f"   - Conecta directamente con lo que el alumno acaba de decir ('{user_message}'): si compartió su nombre o país, reacciona a ese dato; si dijo 'Ja' o 'Nein', adapta tu réplica.\n"
            f"2. RECASTING IMPLÍCITO (NUNCA REGAÑES NI CORRIJAS DE FORMA FRÍA):\n"
            f"   - Si el alumno cometió un error gramatical o léxico leve, NUNCA digas 'eso está mal'. En su lugar, modela la forma correcta dentro de tu propia respuesta de forma 100% natural mientras la charla continúa con fluidez.\n"
            f"3. LONGITUD Y FLUIDEZ NATURAL A1/A2:\n"
            f"   - Responde con 1 a 3 oraciones naturales (alrededor de 10 a 25 palabras). Evita frases telegráficas o frías, manteniendo siempre un lenguaje accesible para nivel A1/A2.\n"
            f"   - Si la misión sigue en curso ('in_progress'), concluye con una pregunta o comentario sencillo para invitar al alumno a contestar.\n"
            f"4. ANDAMIAJE ACTIVO (SUGGESTED REPLIES):\n"
            f"   - Proporciona EXACTAMENTE 2 o 3 opciones cortas ('suggested_replies') que el alumno podría usar para responderte ahora mismo si se siente bloqueado o tímido.\n"
            f"5. CONSEJO CARIÑOSO OPCIONAL ('feedback_tip'):\n"
            f"   - Si el alumno tuvo un error notable que valga la pena comentar, añade un tip ultra breve, positivo y cariñoso en español (máx 15 palabras, ej: '✨ Tip: Recuerda que decimos \"Ich möchte...\" para pedir con cortesía').\n"
            f"   - Si el alumno se comunicó bien o el error fue menor, pon null.\n"
            f"6. CONDICIÓN DE CUMPLIMIENTO ('mission_status'):\n"
            f"   - 'in_progress': si faltan pasos de la misión ({mission_brief}) o llevan menos de 3 intercambios.\n"
            f"   - 'goal_achieved': solo cuando el alumno haya cumplido la misión con éxito y sea el momento natural de despedirse o cerrar la conversación.\n\n"
            f"Responde ESTRICTAMENTE con un objeto JSON válido sin texto extra:\n"
            f'{{\n'
            f'  "reply_native": "texto en {lang_name} de {character_name}",\n'
            f'  "reply_es": "traducción clara y amigable al español",\n'
            f'  "mission_status": "in_progress" | "goal_achieved",\n'
            f'  "feedback_tip": "consejo breve en español o null",\n'
            f'  "suggested_replies": ["Opción 1 sencilla", "Opción 2 alternativa"]\n'
            f'}}'
        )

        try:
            if HAS_NEW_GENAI and self.client:
                config = None
                try:
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        max_output_tokens=300,
                        temperature=0.4,
                    )
                except Exception:
                    pass

                for candidate_model in [
                    "gemini-flash-lite-latest",
                    "gemini-flash-latest",
                    "gemini-2.5-flash-lite",
                ]:
                    try:
                        kwargs = {"model": candidate_model, "contents": prompt}
                        if config:
                            kwargs["config"] = config
                        res = self.client.models.generate_content(**kwargs)
                        if res and res.text:
                            text_raw = res.text.strip()
                            if "```json" in text_raw:
                                text_raw = text_raw.split("```json")[1].split("```")[0].strip()
                            elif "```" in text_raw:
                                text_raw = text_raw.split("```")[1].split("```")[0].strip()
                            data = json.loads(text_raw)
                            idx_fallback = min(
                                user_turn_count - 1 if user_turn_count > 0 else 0,
                                len(char_flow) - 1,
                            )
                            step_fallback = char_flow[idx_fallback]
                            default_sugg = (
                                step_fallback[2]
                                if len(step_fallback) > 2
                                else list(target_phrases[:2])
                            )
                            return {
                                "reply_native": data.get("reply_native", char_flow[0][0]),
                                "reply_es": data.get("reply_es", char_flow[0][1]),
                                "mission_status": data.get("mission_status", "in_progress"),
                                "feedback_tip": data.get("feedback_tip"),
                                "suggested_replies": data.get("suggested_replies") or default_sugg,
                            }
                    except Exception as exc:
                        logger.warning(f"Error procesando conversación con {candidate_model}: {exc}")
                        continue
        except Exception as e:
            logger.error(f"Error en generate_conversation_reply: {e}")

        # Fallback contextual según el personaje si Gemini falló
        idx = min(user_turn_count - 1 if user_turn_count > 0 else 0, len(char_flow) - 1)
        fallback_step = char_flow[idx]
        fallback_native = fallback_step[0]
        fallback_es = fallback_step[1]
        fallback_sugg = fallback_step[2] if len(fallback_step) > 2 else list(target_phrases[:2])
        return {
            "reply_native": fallback_native,
            "reply_es": fallback_es,
            "mission_status": "in_progress",
            "feedback_tip": None,
            "suggested_replies": fallback_sugg,
        }

    def generate_conversation_debrief(
        self,
        scenario_title: str,
        character_name: str,
        mission_brief: str,
        dialogue_history: List[dict],
        language: str = "de-DE",
    ) -> dict:
        """
        Genera el informe final de debriefing pedagógico tras concluir la misión de roleplay.
        """
        lang_name = "alemán" if language.startswith("de") else "inglés"
        user_turns = [t for t in dialogue_history if t.get("role") == "user"]
        total_user_turns = len(user_turns)

        if not self.is_available() or settings.is_mock_mode:
            passed = total_user_turns >= 2
            score = 88.0 if passed else 60.0
            return {
                "passed": passed,
                "score": score,
                "summary": f"Completaste la interacción con {character_name} en el escenario '{scenario_title}' con {total_user_turns} intervenciones.",
                "strengths": [
                    "Comprensión de las preguntas del interlocutor",
                    "Uso de vocabulario situacional A1 relevante",
                ],
                "areas_to_improve": [
                    "Fluidez en la formulación de preguntas",
                ],
                "tips": f"Continúa practicando los diálogos cotidianos en {lang_name} para ganar seguridad y espontaneidad.",
            }

        history_text = "\n".join(
            [f"- {turn.get('name', turn.get('role'))}: {turn.get('text')}" for turn in dialogue_history]
        )

        prompt = (
            f"Eres un evaluador pedagógico de idiomas ({lang_name} nivel A1 CEFR).\n"
            f"El alumno acaba de completar una misión de conversación/roleplay:\n"
            f"Escenario: {scenario_title}\n"
            f"Interlocutor: {character_name}\n"
            f"Objetivo de la misión: {mission_brief}\n\n"
            f"Transcripción completa de la conversación:\n{history_text}\n\n"
            f"Evalúa el desempeño del alumno con criterios formativos y alentadores de nivel A1.\n"
            f"Genera un informe en JSON con el siguiente esquema:\n"
            f'{{\n'
            f'  "passed": true,\n'
            f'  "score": 85,\n'
            f'  "summary": "Resumen de 1-2 oraciones de cómo se desenvolvió el alumno.",\n'
            f'  "strengths": ["Punto fuerte 1", "Punto fuerte 2"],\n'
            f'  "areas_to_improve": ["Aspecto a mejorar 1"],\n'
            f'  "tips": "Consejo práctico para la próxima misión."\n'
            f'}}'
        )

        try:
            if HAS_NEW_GENAI and self.client:
                for candidate_model in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
                    try:
                        res = self.client.models.generate_content(
                            model=candidate_model,
                            contents=prompt,
                        )
                        if res and res.text:
                            text_raw = res.text.strip()
                            if "```json" in text_raw:
                                text_raw = text_raw.split("```json")[1].split("```")[0].strip()
                            elif "```" in text_raw:
                                text_raw = text_raw.split("```")[1].split("```")[0].strip()
                            return json.loads(text_raw)
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error generando debrief de conversación: {e}")

        return {
            "passed": total_user_turns >= 2,
            "score": 80.0,
            "summary": f"Misión completada con éxito interactuando con {character_name}.",
            "strengths": ["Participación activa", "Respuestas adecuadas al contexto"],
            "areas_to_improve": ["Ampliar las respuestas con detalles adicionales"],
            "tips": "Sigue practicando en voz alta cada intervención.",
        }


gemini_coach = GeminiCoachService()

