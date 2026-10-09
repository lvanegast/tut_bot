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

        if not self.is_available() or settings.is_mock_mode:
            # Flujo dinámico y contextual según el turno
            if language.startswith("de"):
                replies_flow = [
                    (
                        "Guten Tag! Gerne. Möchten Sie einen Kaffee dazu trinken?",
                        "¡Buenas tardes! Con gusto. ¿Desea tomar un café para acompañar?",
                    ),
                    (
                        "Alles klar! Das macht zusammen vier Euro fünfzig bitte. Zahlen Sie bar oder mit Karte?",
                        "¡Muy bien! Son cuatro euros cincuenta en total por favor. ¿Paga en efectivo o con tarjeta?",
                    ),
                    (
                        "Vielen Dank! Hier ist Ihre Quittung und Ihr Wechselgeld. Brauchen Sie sonst noch etwas?",
                        "¡Muchas gracias! Aquí tiene su recibo y su cambio. ¿Necesita algo más?",
                    ),
                    (
                        "Perfekt! Einen wunderschönen Tag noch und auf Wiedersehen!",
                        "¡Perfecto! ¡Que tenga un excelente día y hasta pronto!",
                    ),
                ]
                idx = min(user_turn_count - 1 if user_turn_count > 0 else 0, len(replies_flow) - 1)
                rep_native, rep_es = replies_flow[idx]
            else:
                replies_flow = [
                    (
                        "Hello there! Sure thing. Would you like a hot coffee or tea with that?",
                        "¡Hola! Claro que sí. ¿Te gustaría un café caliente o té para acompañar?",
                    ),
                    (
                        "Coming right up! That comes to four pounds fifty please. Cash or card?",
                        "¡Enseguida! Son cuatro libras con cincuenta por favor. ¿Efectivo o tarjeta?",
                    ),
                    (
                        "Thank you so much! Here is your receipt. Is there anything else I can get you?",
                        "¡Muchas gracias! Aquí está tu recibo. ¿Hay algo más que pueda traerte?",
                    ),
                    (
                        "Brilliant! Have a fantastic day and see you next time!",
                        "¡Estupendo! ¡Que tengas un día fantástico y hasta la próxima!",
                    ),
                ]
                idx = min(user_turn_count - 1 if user_turn_count > 0 else 0, len(replies_flow) - 1)
                rep_native, rep_es = replies_flow[idx]

            is_goal_met = user_turn_count >= 4
            return {
                "reply_native": rep_native,
                "reply_es": rep_es,
                "mission_status": "goal_achieved" if is_goal_met else "in_progress",
                "feedback_tip": "¡Excelente ritmo! Intenta usar frases completas en tu respuesta."
                if user_turn_count == 1
                else None,
            }

        prompt = (
            f"Actúas como un profesor nativo y compañero de roleplay interactivo de {lang_name} para un alumno hispanohablante.\n"
            f"Escenario: {scenario_title}\n"
            f"Tu personaje: {character_name} ({character_role})\n"
            f"Misión pedagógica del alumno: {mission_brief}\n"
            f"Frases clave esperadas: {', '.join(target_phrases)}\n\n"
            f"Historial del diálogo previo:\n{history_text}\n"
            f"- Alumno (último mensaje): {user_message}\n\n"
            f"REGLAS CRÍTICAS DE FLUJO Y COHERENCIA:\n"
            f"1. FLUJO CONVERSACIONAL ACTIVO Y NATURAL (Turn-taking):\n"
            f"   - Reacciona con empatía, credibilidad y calidez humana al mensaje del alumno dentro de tu rol de {character_name}.\n"
            f"   - Si el alumno responde brevemente (ej: 'Ja', 'Nein', 'Danke'), reacciona de forma amigable (ej: 'Kein Problem!', 'Alles klar!') y continúa la escena de forma natural.\n"
            f"   - NUNCA mezcles intenciones contradictorias en la misma frase (ej: JAMÁS digas 'Empezamos la clase. ¡Adiós!'). Mantén absoluta coherencia lógica con la situación.\n"
            f"   - Si la misión sigue en curso ('in_progress'), TERMINA con una sola pregunta o invitación sencilla y directa de nivel A1 que invite al alumno a continuar.\n"
            f"2. CONTROL CONTRA DESVÍOS (Anti-tangentes & Re-anchoring):\n"
            f"   - Si el alumno habla en español, duda o no sabe qué decir:\n"
            f"     Mantente en personaje amablemente en {lang_name} y dale la mano pedagógica (ej: 'Kein Problem! In der Bäckerei sagen wir: Ich möchte...').\n"
            f"     Coloca en 'feedback_tip' una sugerencia clara en español con la frase exacta que puede utilizar.\n"
            f"3. NIVEL CEFR A1 ESTRICTO:\n"
            f"   - Oraciones cortas, directas y comprensibles (máximo 20 palabras por réplica). Cero subordinadas complejas o vocabulario C1.\n"
            f"4. CONDICIÓN DE CUMPLIMIENTO CONTEXTUAL ('mission_status'):\n"
            f"   - 'in_progress': Mientras la interacción siga desarrollándose y falten objetivos de la misión ({mission_brief}).\n"
            f"   - 'goal_achieved': ÚNICAMENTE cuando se hayan cubierto TODOS los objetivos de la misión de forma satisfactoria Y tu personaje realice un cierre congruente con el escenario:\n"
            f"     * En aula/bienvenida: dar la bienvenida formal e invitar a tomar asiento o iniciar la actividad (ej: 'Herzlich willkommen im Kurs! Nehmen Sie bitte Platz.'). ¡NO despedirse con Auf Wiedersehen!\n"
            f"     * En tiendas/cafeterías: agradecer la compra y desear un buen día al salir (ej: 'Danke schön und einen schönen Tag noch! Tschüss!').\n"
            f"     * En presentaciones sociales: expresar gusto de conocerse (ej: 'Sehr angenehm, Carlos!').\n"
            f"   - NUNCA cortes la conversación de forma prematura ni dejes situaciones inconclusas.\n"
            f"5. CORRECCIÓN SUTIL ('feedback_tip'):\n"
            f"   - Si el alumno cometió un error gramatical o léxico relevante, incluye 1 consejo amable y breve en español. Si su mensaje fue correcto o comprensible, pon null.\n\n"
            f"Responde ESTRICTAMENTE en formato JSON válido:\n"
            f'{{\n'
            f'  "reply_native": "texto en {lang_name} de {character_name}",\n'
            f'  "reply_es": "traducción fidedigna al español",\n'
            f'  "mission_status": "in_progress" | "goal_achieved",\n'
            f'  "feedback_tip": "consejo breve en español o null"\n'
            f'}}'
        )

        try:
            if HAS_NEW_GENAI and self.client:
                # Usar configuración con temperatura adecuada para conversación natural
                config = None
                try:
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        max_output_tokens=220,
                        temperature=0.35,
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
                            return {
                                "reply_native": data.get("reply_native", "..."),
                                "reply_es": data.get("reply_es", "..."),
                                "mission_status": data.get("mission_status", "in_progress"),
                                "feedback_tip": data.get("feedback_tip"),
                            }
                    except Exception as exc:
                        logger.warning(f"Error procesando conversación con {candidate_model}: {exc}")
                        continue
        except Exception as e:
            logger.error(f"Error en generate_conversation_reply: {e}")

        # Fallback de emergencia
        default_reply = (
            "Sehr gerne! Möchten Sie noch etwas dazu bestellen?"
            if language.startswith("de")
            else "Certainly! Would you like anything else with that?"
        )
        default_es = (
            "¡Con mucho gusto! ¿Desea pedir algo más para acompañar?"
            if language.startswith("de")
            else "¡Por supuesto! ¿Te gustaría algo más para acompañar?"
        )
        return {
            "reply_native": default_reply,
            "reply_es": default_es,
            "mission_status": "in_progress",
            "feedback_tip": None,
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

