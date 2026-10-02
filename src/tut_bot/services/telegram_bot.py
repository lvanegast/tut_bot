import io
import logging
import os
import tempfile
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tut_bot.config import settings
from tut_bot.services.audio_converter import audio_converter
from tut_bot.services.azure_speech import azure_service
from tut_bot.services.exercises import get_exercises
from tut_bot.services.gemini_coach import gemini_coach
from tut_bot.services.tracker import tracker

logger = logging.getLogger(__name__)


def _make_progress_bar(score: float, length: int = 10) -> str:
    """Genera una barra de progreso visual con caracteres Unicode."""
    filled = int(round((score / 100.0) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


class TelegramCoachBot:
    """
    Bot interactivo de Telegram para tut_bot.
    Permite enviar notas de voz desde cualquier celular y recibir diagnósticos acústicos IPA
    y feedback anatómico de Google Gemini en tiempo real.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.app: Optional[Application] = None
        self._is_running = False

    def is_configured(self) -> bool:
        return bool(self.token and not self.token.startswith("tu_"))

    def build_app(self) -> Application:
        """Construye y configura los handlers del bot."""
        app = ApplicationBuilder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("ejercicio", self.cmd_exercise))
        app.add_handler(CommandHandler("practicar", self.cmd_exercise))
        app.add_handler(CommandHandler("idioma", self.cmd_language))
        app.add_handler(CommandHandler("libre", self.cmd_custom_phrase))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("web", self.cmd_web))

        # Callback queries de botones inline
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Mensajes de voz
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

        # Mensajes de texto (por si escribe una frase directamente para practicar)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        self.app = app
        return app

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mensaje de bienvenida y selección de idioma inicial."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang_flag = "🇩🇪 Alemán" if state["language"].startswith("de") else "🇺🇸 Inglés"

        welcome_text = (
            "🎙️ **¡Bienvenido a tut_bot!**\n"
            "Tu entrenador fonético inteligente para **Alemán** e **Inglés**, impulsado por "
            "**Azure Speech (IPA)** y **Google Gemini**.\n\n"
            "⚡ **¿Cómo funciona?**\n"
            "1️⃣ Pide un ejercicio con /ejercicio o escribe una frase libre.\n"
            "2️⃣ Escucha la referencia nativa con el botón de audio.\n"
            "3️⃣ **Envía una nota de voz** manteniendo presionado el micrófono 🎙️.\n"
            "4️⃣ Recibe tu desglose fonema a fonema y consejos anatómicos para tu boca y lengua.\n\n"
            f"🌐 **Idioma actual:** {lang_flag}"
        )

        keyboard = [
            [
                InlineKeyboardButton("🇩🇪 Alemán", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton("📚 Empezar Ejercicio", callback_data="btn_exercise"),
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
            ],
            [
                InlineKeyboardButton("🌐 Panel Web", callback_data="btn_web"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📖 **Comandos disponibles en tut_bot:**\n\n"
            "• `/ejercicio` o `/practicar` - Muestra la frase fonética actual.\n"
            "• `/idioma` - Alterna entre Alemán (de-DE) e Inglés (en-US).\n"
            "• `/libre <frase>` - Configura cualquier frase que desees pronunciar.\n"
            "• `/stats` - Muestra tu historial, puntuación promedio y fonemas débiles.\n"
            "• `/web` - Enlace a la interfaz web visual.\n\n"
            "🎙️ **Simplemente envía una nota de voz** cuando estés listo para evaluar tu pronunciación."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("🇩🇪 Alemán (de-DE)", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés (en-US)", callback_data="lang_en"),
            ]
        ]
        await update.message.reply_text(
            "🌍 **Selecciona el idioma que deseas perfeccionar:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_custom_phrase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Permite al usuario fijar una frase propia para practicar."""
        user_id = f"tg_{update.effective_user.id}"
        phrase = " ".join(context.args).strip() if context.args else ""
        if not phrase:
            await update.message.reply_text(
                "✍️ Por favor indica la frase que deseas practicar.\n"
                "Ejemplo: `/libre Ich möchte heute Deutsch sprechen`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        tracker.set_user_custom_phrase(user_id, phrase)
        keyboard = [
            [InlineKeyboardButton("🔊 Escuchar Pronunciación", callback_data="tts_custom")],
            [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
        ]
        await update.message.reply_text(
            f"🎯 **Frase personalizada fijada:**\n\n"
            f'👉 *"{phrase}"*\n\n'
            f"Mantén presionado el micrófono 🎙️ de Telegram y envía tu nota de voz para evaluarla.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_exercise(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_exercise_card(update, user_id)

    async def _send_exercise_card(self, update: Update, user_id: str, edit_message: bool = False):
        """Envía o actualiza la tarjeta del ejercicio actual del usuario."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        exercises = get_exercises(language=lang)

        if not exercises:
            msg = "No hay ejercicios disponibles en este momento."
            if edit_message and update.callback_query:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.effective_message.reply_text(msg)
            return

        idx = state["exercise_index"] % len(exercises)
        ex = exercises[idx]

        # Reset custom phrase when looking at curated exercises
        tracker.set_user_custom_phrase(user_id, None)

        lang_header = "🇩🇪 ALEMÁN" if lang.startswith("de") else "🇺🇸 INGLÉS"
        phonemes_str = " · ".join([f"`/{p}/`" for p in ex.focus_phonemes])

        card_text = (
            f"📖 **{lang_header}** — [{ex.level}] {ex.category}\n"
            f"**Tema:** {ex.title}\n\n"
            f"🗣️ **Frase a pronunciar:**\n"
            f'**"{ex.target_text}"**\n\n'
            f"🔤 **IPA:** `{ex.ipa}`\n"
            f'🇪🇸 **Traducción:** *"{ex.translation_es}"*\n'
            f"🎯 **Fonemas clave:** {phonemes_str}\n\n"
            f"💡 **Consejo Anatómico:**\n"
            f"_{ex.tip}_\n\n"
            f"_(Ejercicio {idx + 1} de {len(exercises)})_\n"
            f"👇 **¡Envía tu nota de voz ahora para evaluarte!**"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔊 Escuchar Referencia", callback_data=f"tts_{ex.id}"),
            ],
            [
                InlineKeyboardButton("⬅️ Anterior", callback_data="ex_prev"),
                InlineKeyboardButton(f"{idx + 1}/{len(exercises)}", callback_data="ex_curr"),
                InlineKeyboardButton("Siguiente ➡️", callback_data="ex_next"),
            ],
            [
                InlineKeyboardButton("🌐 Cambiar Idioma", callback_data="btn_lang_menu"),
                InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    card_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                await update.effective_chat.send_message(
                    card_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.effective_chat.send_message(
                card_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_stats(update, user_id)

    async def _send_stats(self, update: Update, user_id: str, edit_message: bool = False):
        stats = tracker.get_user_stats(user_id)
        if stats["total_attempts"] == 0:
            text = (
                "📊 **Tus Estadísticas en tut_bot**\n\n"
                "Aún no has realizado ninguna práctica con notas de voz.\n"
                "¡Usa /ejercicio y envía tu primer audio para comenzar tu registro!"
            )
        else:
            weak_list = (
                "\n".join(
                    [
                        f"• Fonema `/{item['phoneme']}/`: {item['count']} veces con dificultad"
                        for item in stats["weak_phonemes_top"]
                    ]
                )
                or "• ¡Ningún fonema crítico detectado! Buen trabajo."
            )

            recent_list = "\n".join(
                [
                    f"• {r['reference_text'][:30]}... ➔ **{r['overall_score']:.0f} pts**"
                    for r in stats["recent_history"]
                ]
            )

            text = (
                f"📊 **Tus Estadísticas de Pronunciación**\n\n"
                f"🎯 **Prácticas totales:** {stats['total_attempts']}\n"
                f"⭐ **Puntuación Promedio:** **{stats['average_overall']}/100**\n"
                f"🔍 **Precisión Media:** {stats['average_accuracy']}%\n"
                f"🌊 **Fluidez Media:** {stats['average_fluency']}%\n\n"
                f"⚠️ **Fonemas que más debes reforzar:**\n"
                f"{weak_list}\n\n"
                f"🕒 **Últimas prácticas:**\n"
                f"{recent_list}"
            )

        keyboard = [
            [InlineKeyboardButton("📚 Ir a Ejercicios", callback_data="btn_exercise")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                await update.effective_chat.send_message(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.effective_chat.send_message(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_web(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = settings.WEB_BASE_URL or f"http://{settings.HOST}:{settings.PORT}"
        text = (
            f"🖥️ **Interfaz Web / Dashboard de tut_bot**\n\n"
            f"Puedes abrir la interfaz gráfica en tu navegador en:\n"
            f"👉 `{url}`\n\n"
            f"💡 *Nota:* Si estás en la misma red Wi-Fi que la Jetson Nano o tu PC, "
            f"reemplaza `0.0.0.0` por la IP local de tu Jetson (ej. `http://192.168.1.50:8000`)."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja las interacciones con botones en línea."""
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = f"tg_{update.effective_user.id}"

        if data == "btn_exercise":
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data == "btn_stats":
            await self._send_stats(update, user_id, edit_message=True)

        elif data == "btn_lang_menu":
            keyboard = [
                [
                    InlineKeyboardButton("🇩🇪 Alemán (de-DE)", callback_data="lang_de"),
                    InlineKeyboardButton("🇺🇸 Inglés (en-US)", callback_data="lang_en"),
                ],
                [InlineKeyboardButton("⬅️ Volver", callback_data="btn_exercise")],
            ]
            await query.edit_message_text(
                "🌍 **Selecciona el idioma para practicar:**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data in ("lang_de", "lang_en"):
            new_lang = "de-DE" if data == "lang_de" else "en-US"
            tracker.set_user_language(user_id, new_lang)
            flag = "🇩🇪 Alemán" if new_lang.startswith("de") else "🇺🇸 Inglés"
            await query.edit_message_text(f"✅ ¡Idioma cambiado a **{flag}**!")
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "ex_next":
            state = tracker.get_user_state(user_id)
            exercises = get_exercises(language=state["language"])
            next_idx = (state["exercise_index"] + 1) % len(exercises)
            tracker.set_user_exercise_index(user_id, next_idx)
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data == "ex_prev":
            state = tracker.get_user_state(user_id)
            exercises = get_exercises(language=state["language"])
            prev_idx = (state["exercise_index"] - 1 + len(exercises)) % len(exercises)
            tracker.set_user_exercise_index(user_id, prev_idx)
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data.startswith("tts_"):
            # Generar audio de referencia nativo y enviarlo como nota de voz
            await self._send_tts_reference(query, user_id, data)

        elif data == "btn_web":
            url = settings.WEB_BASE_URL or f"http://{settings.HOST}:{settings.PORT}"
            await query.edit_message_text(
                f"🖥️ **Panel Web de tut_bot:**\n`{url}`\n\nUsa /ejercicio para volver al entrenamiento.",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def _send_tts_reference(self, query, user_id: str, data: str):
        """Sintetiza la voz nativa y la envía como audio/voz a Telegram."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        # Determinar el texto de referencia
        if data == "tts_custom" and state.get("custom_phrase"):
            text = state["custom_phrase"]
        else:
            exercises = get_exercises(language=lang)
            idx = state["exercise_index"] % len(exercises)
            text = exercises[idx].target_text

        await query.message.reply_chat_action(ChatAction.RECORD_VOICE)

        # Generar WAV con Azure TTS
        wav_bytes = azure_service.synthesize_speech(text=text, language=lang)
        if not wav_bytes:
            await query.message.reply_text(
                "⚠️ Azure TTS no está disponible en este momento. Revisa tus credenciales o el modo simulación."
            )
            return

        # Convertir a OGG Opus para que Telegram lo reproduzca nativamente como nota de voz
        ogg_bytes = audio_converter.wav_to_ogg_opus(wav_bytes)
        audio_stream = io.BytesIO(ogg_bytes if ogg_bytes else wav_bytes)
        audio_stream.name = "referencia_nativa.ogg" if ogg_bytes else "referencia_nativa.wav"

        await query.message.reply_voice(
            voice=audio_stream,
            caption=f'🔊 **Referencia nativa ({"🇩🇪" if lang.startswith("de") else "🇺🇸"}):**\n"{text}"',
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Si el usuario escribe un texto directamente, lo establece como frase de práctica."""
        text = update.message.text.strip()
        user_id = f"tg_{update.effective_user.id}"
        tracker.set_user_custom_phrase(user_id, text)

        keyboard = [
            [InlineKeyboardButton("🔊 Escuchar Referencia", callback_data="tts_custom")],
            [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
        ]
        await update.message.reply_text(
            f"🎯 **Frase para practicar establecida:**\n\n"
            f'👉 *"{text}"*\n\n'
            f"Mantén presionado el micrófono 🎙️ para enviar tu audio.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa la nota de voz enviada por el usuario."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        # Determinar frase de referencia
        if state.get("custom_phrase"):
            reference_text = state["custom_phrase"]
            is_custom = True
        else:
            exercises = get_exercises(language=lang)
            idx = state["exercise_index"] % len(exercises)
            reference_text = exercises[idx].target_text
            is_custom = False

        status_msg = await update.message.reply_text(
            "🎧 **Analizando fonemas y acústica con Azure & Gemini...**",
            parse_mode=ParseMode.MARKDOWN,
        )
        await update.message.reply_chat_action(ChatAction.TYPING)

        temp_wav_path = None
        try:
            # 1. Descargar audio de Telegram (.ogg)
            voice_file = await update.message.voice.get_file()
            ogg_bytes = await voice_file.download_as_bytearray()

            # 2. Convertir a WAV PCM 16kHz mono para Azure Speech SDK
            wav_bytes = audio_converter.ogg_to_wav(bytes(ogg_bytes))
            if not wav_bytes:
                await status_msg.edit_text(
                    "❌ No se pudo procesar el formato del archivo de voz. Por favor intenta de nuevo."
                )
                return

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_wav_path = f.name

            # 3. Evaluación Acústica (Azure Speech o Mock)
            eval_result = azure_service.evaluate_pronunciation(
                wav_path=temp_wav_path,
                reference_text=reference_text,
                language=lang,
            )

            # 4. Feedback Pedagógico (Gemini AI Coach)
            feedback = gemini_coach.generate_feedback(
                reference_text=reference_text,
                language=lang,
                overall_score=eval_result.overall_score,
                words=eval_result.words,
            )

            # 5. Extraer fonemas débiles y registrar en SQLite
            weak_phonemes = []
            for w in eval_result.words:
                for p in w.phonemes:
                    if p.score < 70:
                        weak_phonemes.append(p.phoneme)

            tracker.record_evaluation(
                user_id=user_id,
                language=lang,
                reference_text=reference_text,
                overall_score=eval_result.overall_score,
                accuracy_score=eval_result.accuracy_score,
                fluency_score=eval_result.fluency_score,
                prosody_score=eval_result.prosody_score,
                weak_phonemes=weak_phonemes,
            )

            # 6. Formatear reporte de Telegram
            score = eval_result.overall_score
            if score >= 85:
                badge = f"🟢 **¡Excelente! {score:.0f}/100** 🎉"
            elif score >= 70:
                badge = f"🟡 **¡Buen intento! {score:.0f}/100** 👍"
            else:
                badge = f"🔴 **A mejorar: {score:.0f}/100** 💪"

            acc_bar = _make_progress_bar(eval_result.accuracy_score)
            flu_bar = _make_progress_bar(eval_result.fluency_score)
            pro_bar = _make_progress_bar(eval_result.prosody_score or eval_result.accuracy_score)

            # Desglose de palabras
            word_lines = []
            for w in eval_result.words:
                icon = "✅" if w.score >= 75 else "⚠️"
                phoneme_details = " ".join(
                    [
                        f"{p.phoneme}({p.score:.0f})" if p.score < 70 else p.phoneme
                        for p in w.phonemes
                    ]
                )
                word_lines.append(f"{icon} *{w.word}* [{phoneme_details}] ➔ `{w.score:.0f}%`")

            words_formatted = "\n".join(word_lines)

            response_text = (
                f"{badge}\n"
                f'📝 Frase: *"{reference_text}"*\n\n'
                f"🎯 **Precisión:** `[{acc_bar}]` {eval_result.accuracy_score:.0f}%\n"
                f"🌊 **Fluidez:**   `[{flu_bar}]` {eval_result.fluency_score:.0f}%\n"
                f"🎵 **Prosodia:**  `[{pro_bar}]` {eval_result.prosody_score or 0:.0f}%\n\n"
                f"🔍 **Desglose de fonemas (IPA):**\n"
                f"{words_formatted}\n\n"
                f"👨‍🏫 **Tutor Gemini:**\n"
                f"{feedback}"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔊 Escuchar Referencia",
                        callback_data="tts_custom" if is_custom else "tts_curated",
                    ),
                    InlineKeyboardButton("🔄 Repetir Frase", callback_data="btn_exercise"),
                ],
                [
                    InlineKeyboardButton("➡️ Siguiente Ejercicio", callback_data="ex_next"),
                    InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                ],
            ]

            await status_msg.edit_text(
                response_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"Error procesando nota de voz de Telegram: {e}", exc_info=True)
            await status_msg.edit_text(f"⚠️ Ocurrió un error al evaluar tu pronunciación: {str(e)}")
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass

    async def start_polling(self):
        """Inicia el bot en modo polling asíncrono."""
        if not self.is_configured():
            logger.warning("TelegramCoachBot: TELEGRAM_BOT_TOKEN no configurado. Bot no iniciado.")
            return

        self.build_app()
        logger.info("Iniciando Telegram Coach Bot en modo Polling...")
        self._is_running = True
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        """Detiene el bot de forma limpia."""
        if self.app and self._is_running:
            logger.info("Deteniendo Telegram Coach Bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self._is_running = False


telegram_bot = TelegramCoachBot()


def run_standalone():
    """Punto de entrada para ejecutar únicamente el bot de Telegram (ej. uv run tut-bot-telegram)."""
    logging.basicConfig(level=logging.INFO)
    if not telegram_bot.is_configured():
        print(
            "\n[AVISO] TELEGRAM_BOT_TOKEN no está configurado en tu archivo .env\n"
            "Crea un bot con @BotFather en Telegram, copia el token en .env y vuelve a ejecutar."
        )
        return

    print("🤖 Iniciando tut_bot en Telegram...")
    app = telegram_bot.build_app()
    app.run_polling(drop_pending_updates=True)
