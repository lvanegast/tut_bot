import io
import logging
import os
import re
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


def _make_progress_bar(score: Optional[float], length: int = 10) -> str:
    """Genera una barra de progreso visual con caracteres Unicode."""
    val = float(score) if score is not None else 0.0
    filled = int(round((val / 100.0) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def _format_markdown_for_telegram(text: str) -> str:
    """Convierte markdown básico (**negrita**, *cursiva*) a formato HTML válido para Telegram."""
    if not text:
        return ""
    # 1. Escapar entidades HTML especiales
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 2. Convertir **negrita**
    parts = text.split("**")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<b>{part}</b>")
            else:
                res.append(part)
        text = "".join(res)
    # 3. Convertir *cursiva* si queda
    parts = text.split("*")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<i>{part}</i>")
            else:
                res.append(part)
        text = "".join(res)
    return text


def get_phoneme_explanation(phoneme: str, language: str = "de-DE") -> str:
    """Traduce símbolos fonéticos IPA a explicaciones comprensibles en español."""
    clean_p = phoneme.replace("/", "").replace("[", "").replace("]", "").strip()
    EXPLANATIONS = {
        # Alemán
        "ç": "ch suave palatal (siseo suave con lengua en el medio paladar, no es 'j' áspera)",
        "x": "ch velar (similar a la 'j' española suave)",
        "ʃ": "sonido 'sh' (como mandar a callar)",
        "ʁ": "r uvular alemana (vibra en la campanilla)",
        "ɐ": "r final vocalizada (suena como una 'a' corta relajada, ej. 'Lehrer' -> 'Lee-ra')",
        "øː": "ö larga (labios en 'o', diciendo 'e')",
        "œ": "ö corta (labios redondeados)",
        "yː": "ü larga (labios en beso de 'u', diciendo 'i')",
        "ʏ": "ü corta y relajada",
        "ɛː": "ä (e abierta, baja un poco la mandíbula)",
        "ts": "sonido 'ts' (como tsunami o pizza)",
        "z": "s sonora (vibra como zumbido de abeja)",
        "s": "s sorda estándar",
        # Inglés
        "θ": "th sorda (como la 'z' española en 'zapato', sin vibrar)",
        "ð": "th sonora (lengua entre dientes con vibración, ej. 'this', 'father')",
        "iː": "i larga tensa y sonriente (ej. 'sheep')",
        "ɪ": "i corta relajada (ej. 'ship')",
        "æ": "a abierta amplia (entre a y e, mandíbula baja, ej. 'cat')",
        "ʌ": "u corta central neutra (ej. 'cup')",
        "w": "w inglesa redondeada sin tocar dientes (ej. 'we')",
        "v": "v labiodental (dientes superiores sobre labio inferior con vibración)",
    }
    return EXPLANATIONS.get(clean_p, "")


class TelegramCoachBot:
    """
    Bot interactivo de Telegram para tut_bot.
    Permite enviar notas de voz desde cualquier celular y recibir diagnósticos acústicos IPA
    y feedback pedagógico de Google Gemini en tiempo real.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.app: Optional[Application] = None
        self._is_running = False

    def is_configured(self) -> bool:
        return bool(self.token and not self.token.startswith("tu_"))

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remueve etiquetas HTML básicas en caso de fallo de renderizado."""
        return re.sub(r"<[^>]*>", "", text)

    async def _safe_reply_text(
        self, message, text: str, reply_markup=None, parse_mode=ParseMode.HTML
    ):
        """Envía respuesta con HTML; si falla el formateo, reintenta sin formato para nunca callarse."""
        try:
            return await message.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as e:
            logger.warning(
                f"Error en reply_text con parse_mode {parse_mode}: {e}. Reintentando texto plano."
            )
            return await message.reply_text(
                self._strip_html(text), reply_markup=reply_markup, parse_mode=None
            )

    async def _safe_edit_text(
        self, target, text: str, reply_markup=None, parse_mode=ParseMode.HTML
    ):
        """Edita mensaje con HTML; si falla, reintenta sin formato."""
        try:
            return await target.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as e:
            logger.warning(
                f"Error en edit_text con parse_mode {parse_mode}: {e}. Reintentando texto plano."
            )
            return await target.edit_text(
                self._strip_html(text), reply_markup=reply_markup, parse_mode=None
            )

    async def _safe_send_chat_message(
        self, chat, text: str, reply_markup=None, parse_mode=ParseMode.HTML
    ):
        """Envía mensaje a chat con HTML; si falla, reintenta sin formato."""
        try:
            return await chat.send_message(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as e:
            logger.warning(
                f"Error en send_message con parse_mode {parse_mode}: {e}. Reintentando texto plano."
            )
            return await chat.send_message(
                self._strip_html(text), reply_markup=reply_markup, parse_mode=None
            )

    def build_app(self) -> Application:
        """Construye y configura los handlers del bot con tolerancia a erratas."""
        app = ApplicationBuilder().token(self.token).build()

        # Tolerancia a erratas comunes de start (/strar, /star, /inicio, etc.)
        app.add_handler(
            CommandHandler(
                ["start", "strar", "star", "stat", "starr", "inicio", "comenzar"],
                self.cmd_start,
            )
        )
        app.add_handler(CommandHandler(["help", "ayuda", "comandos"], self.cmd_help))
        app.add_handler(
            CommandHandler(
                ["ejercicio", "practicar", "frase", "next", "siguiente"],
                self.cmd_exercise,
            )
        )
        app.add_handler(
            CommandHandler(["idioma", "lang", "language"], self.cmd_language)
        )
        app.add_handler(
            CommandHandler(["libre", "custom", "fraselibre"], self.cmd_custom_phrase)
        )
        app.add_handler(
            CommandHandler(["stats", "estadisticas", "progreso"], self.cmd_stats)
        )
        app.add_handler(
            CommandHandler(["web", "panel", "link", "dashboard"], self.cmd_web)
        )

        # Callback queries de botones inline
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Mensajes de voz y audio
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice))

        # Mensajes de texto normales
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )

        # Catch-all para comandos no reconocidos
        app.add_handler(MessageHandler(filters.COMMAND, self.cmd_unknown))

        # Manejador global de excepciones
        app.add_error_handler(self.error_handler)

        self.app = app
        return app

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ):
        """Captura cualquier excepción no manejada para que el bot nunca se bloquee ni quede callado."""
        logger.error(
            f"Excepción en Telegram update: {context.error}",
            exc_info=context.error,
        )
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Ocurrió una interrupción temporal al procesar tu solicitud. Por favor envía tu audio de nuevo o escribe /ejercicio.",
                    parse_mode=None,
                )
            except Exception:
                pass

    async def cmd_unknown(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Maneja comandos desconocidos o con erratas."""
        cmd_text = (update.effective_message.text or "").strip().lower()
        if any(
            typo in cmd_text
            for typo in ["strar", "star", "stat", "starr", "st"]
        ):
            await self.cmd_start(update, context)
            return

        msg = (
            "🤔 <b>No reconocí ese comando.</b>\n\n"
            "• Usa <b>/ejercicio</b> para ver tu frase actual.\n"
            "• Usa <b>/start</b> para ir al menú principal.\n"
            "• O simplemente <b>mantén presionado el micrófono 🎙️</b> para enviar una nota de voz."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "📚 Ir al Ejercicio", callback_data="btn_exercise"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Menú Principal", callback_data="btn_start_menu"
                )
            ],
        ]
        await self._safe_reply_text(
            update.effective_message,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Mensaje de bienvenida y selección de idioma inicial."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang_flag = (
            "🇩🇪 Alemán" if state["language"].startswith("de") else "🇺🇸 Inglés"
        )

        welcome_text = (
            "🎙️ <b>¡Bienvenido a tut_bot!</b>\n"
            "Tu entrenador fonético inteligente para <b>Alemán</b> e <b>Inglés</b>, impulsado por "
            "<b>Azure Speech (IPA)</b> y <b>Google Gemini</b>.\n\n"
            "⚡ <b>¿Cómo funciona?</b>\n"
            "1️⃣ Pide un ejercicio con /ejercicio o escribe una frase libre.\n"
            "2️⃣ Escucha la referencia nativa con el botón de audio.\n"
            "3️⃣ <b>Envía una nota de voz</b> manteniendo presionado el micrófono 🎙️.\n"
            "4️⃣ Recibe tu desglose de fonemas, pronunciación amigable y consejos anatómicos para tu lengua y labios.\n\n"
            f"🌐 <b>Idioma actual:</b> {lang_flag}"
        )

        keyboard = [
            [
                InlineKeyboardButton("🇩🇪 Alemán", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton(
                    "📚 Empezar Ejercicio", callback_data="btn_exercise"
                ),
                InlineKeyboardButton(
                    "📊 Mis Estadísticas", callback_data="btn_stats"
                ),
            ],
            [
                InlineKeyboardButton("🌐 Panel Web", callback_data="btn_web"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_reply_text(
            update.effective_message, welcome_text, reply_markup=reply_markup
        )

    async def cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        help_text = (
            "📖 <b>Comandos disponibles en tut_bot:</b>\n\n"
            "• <b>/ejercicio</b> — Muestra la frase fonética para practicar.\n"
            "• <b>/idioma</b> — Alterna entre Alemán (de-DE) e Inglés (en-US).\n"
            "• <b>/libre &lt;frase&gt;</b> — Configura cualquier frase que desees pronunciar.\n"
            "• <b>/stats</b> — Muestra tu puntuación promedio y fonemas a mejorar.\n"
            "• <b>/web</b> — Enlace al panel web en tu PC.\n\n"
            "🎙️ <b>Simplemente envía una nota de voz</b> cuando estés listo para evaluar tu pronunciación."
        )
        await self._safe_reply_text(update.effective_message, help_text)

    async def cmd_language(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        keyboard = [
            [
                InlineKeyboardButton("🇩🇪 Alemán (de-DE)", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés (en-US)", callback_data="lang_en"),
            ]
        ]
        await self._safe_reply_text(
            update.effective_message,
            "🌍 <b>Selecciona el idioma que deseas perfeccionar:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_custom_phrase(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Permite al usuario fijar una frase propia para practicar."""
        user_id = f"tg_{update.effective_user.id}"
        phrase = " ".join(context.args).strip() if context.args else ""
        if not phrase:
            await self._safe_reply_text(
                update.effective_message,
                "✍️ Por favor indica la frase que deseas practicar.\n"
                "Ejemplo: <code>/libre Ich möchte heute Deutsch sprechen</code>",
            )
            return

        tracker.set_user_custom_phrase(user_id, phrase)
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Escuchar Pronunciación", callback_data="tts_custom"
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 Volver a Ejercicios", callback_data="btn_exercise"
                )
            ],
        ]
        await self._safe_reply_text(
            update.effective_message,
            f"🎯 <b>Frase personalizada fijada:</b>\n\n"
            f'👉 <i>"{phrase}"</i>\n\n'
            f"Mantén presionado el micrófono 🎙️ de Telegram y envía tu nota de voz para evaluarla.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_exercise(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_exercise_card(update, user_id)

    async def _send_exercise_card(
        self, update: Update, user_id: str, edit_message: bool = False
    ):
        """Envía o actualiza la tarjeta del ejercicio actual con guía fonética amigable e IPA."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        exercises = get_exercises(language=lang)

        if not exercises:
            msg = "No hay ejercicios disponibles en este momento."
            if edit_message and update.callback_query:
                await self._safe_edit_text(update.callback_query, msg)
            else:
                await self._safe_reply_text(update.effective_message, msg)
            return

        idx = state["exercise_index"] % len(exercises)
        ex = exercises[idx]

        tracker.set_user_custom_phrase(user_id, None)

        lang_header = "🇩🇪 ALEMÁN" if lang.startswith("de") else "🇺🇸 INGLÉS"
        phonemes_str = " · ".join([f"<code>/{p}/</code>" for p in ex.focus_phonemes])

        card_lines = [
            f"📖 <b>{lang_header}</b> — [{ex.level}] {ex.category}",
            f"<b>Tema:</b> {ex.title}\n",
            f"🗣️ <b>Frase a pronunciar:</b>",
            f'👉 <b>"{ex.target_text}"</b>\n',
        ]

        if ex.phonetic_guide:
            card_lines.append(
                f'🗣️ <b>Pronunciación fácil:</b> <i>"{ex.phonetic_guide}"</i>'
            )
        if ex.ipa:
            card_lines.append(f"🔤 <b>Símbolos IPA:</b> <code>/{ex.ipa}/</code>")
        if ex.phonetic_notes:
            card_lines.append(f"ℹ️ <b>Guía de sonidos:</b> {ex.phonetic_notes}")

        card_lines.extend(
            [
                f'🇪🇸 <b>Traducción:</b> <i>"{ex.translation_es}"</i>',
                f"🎯 <b>Sonidos clave:</b> {phonemes_str}\n",
                f"💡 <b>Consejo de Articulación:</b>",
                f"<i>{ex.tip}</i>\n",
                f"<i>(Ejercicio {idx + 1} de {len(exercises)})</i>",
                f"👇 <b>Mantén presionado el micrófono 🎙️ para enviar tu audio</b>",
            ]
        )

        card_text = "\n".join(card_lines)

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Escuchar Referencia", callback_data=f"tts_{ex.id}"
                ),
            ],
            [
                InlineKeyboardButton("⬅️ Anterior", callback_data="ex_prev"),
                InlineKeyboardButton(
                    f"{idx + 1}/{len(exercises)}", callback_data="ex_curr"
                ),
                InlineKeyboardButton("Siguiente ➡️", callback_data="ex_next"),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Cambiar Idioma", callback_data="btn_lang_menu"
                ),
                InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(
                    update.callback_query, card_text, reply_markup=reply_markup
                )
            except Exception:
                await self._safe_send_chat_message(
                    update.effective_chat, card_text, reply_markup=reply_markup
                )
        else:
            await self._safe_send_chat_message(
                update.effective_chat, card_text, reply_markup=reply_markup
            )

    async def cmd_stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_stats(update, user_id)

    async def _send_stats(
        self, update: Update, user_id: str, edit_message: bool = False
    ):
        stats = tracker.get_user_stats(user_id)
        if stats["total_attempts"] == 0:
            text = (
                "📊 <b>Tus Estadísticas en tut_bot</b>\n\n"
                "Aún no has realizado ninguna práctica con notas de voz.\n"
                "¡Usa /ejercicio y envía tu primer audio para comenzar tu registro!"
            )
        else:
            avg_acc = stats["average_accuracy"]
            avg_flu = stats["average_fluency"]
            acc_bar = _make_progress_bar(avg_acc)
            flu_bar = _make_progress_bar(avg_flu)

            weak = stats.get("weak_phonemes", [])
            weak_str = (
                ", ".join([f"<code>/{p}/</code>" for p in weak[:5]])
                if weak
                else "¡Ninguno! Estás pronunciando excelente."
            )

            text = (
                "📊 <b>Tus Estadísticas de Pronunciación</b>\n\n"
                f"• <b>Intentos totales:</b> {stats['total_attempts']}\n"
                f"• <b>Precisión Media:</b> <code>[{acc_bar}]</code> {avg_acc:.0f}%\n"
                f"• <b>Fluidez Media:</b>   <code>[{flu_bar}]</code> {avg_flu:.0f}%\n\n"
                f"🎯 <b>Sonidos que más debes practicar:</b>\n{weak_str}"
            )

        keyboard = [
            [
                InlineKeyboardButton(
                    "📚 Ir a Ejercicios", callback_data="btn_exercise"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Menú Principal", callback_data="btn_start_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(
                    update.callback_query, text, reply_markup=reply_markup
                )
            except Exception:
                await self._safe_send_chat_message(
                    update.effective_chat, text, reply_markup=reply_markup
                )
        else:
            await self._safe_send_chat_message(
                update.effective_chat, text, reply_markup=reply_markup
            )

    async def cmd_web(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        url = (
            settings.WEB_BASE_URL or f"http://{settings.HOST}:{settings.PORT}"
        )
        text = (
            f"🖥️ <b>Panel Web interactivo de tut_bot:</b>\n"
            f"<code>{url}</code>\n\n"
            f"Ábrelo en el navegador de tu computadora para ver el osciloscopio en vivo y el atlas fonético."
        )
        await self._safe_reply_text(update.effective_message, text)

    async def handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = f"tg_{update.effective_user.id}"

        if data == "btn_start_menu":
            await self.cmd_start(update, context)

        elif data == "btn_exercise":
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data == "btn_stats":
            await self._send_stats(update, user_id, edit_message=True)

        elif data == "btn_lang_menu":
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🇩🇪 Alemán (de-DE)", callback_data="lang_de"
                    ),
                    InlineKeyboardButton(
                        "🇺🇸 Inglés (en-US)", callback_data="lang_en"
                    ),
                ],
                [InlineKeyboardButton("⬅️ Volver", callback_data="btn_exercise")],
            ]
            await self._safe_edit_text(
                query,
                "🌍 <b>Selecciona el idioma para practicar:</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        elif data in ("lang_de", "lang_en"):
            new_lang = "de-DE" if data == "lang_de" else "en-US"
            tracker.set_user_language(user_id, new_lang)
            flag = "🇩🇪 Alemán" if new_lang.startswith("de") else "🇺🇸 Inglés"
            await self._safe_edit_text(query, f"✅ ¡Idioma cambiado a <b>{flag}</b>!")
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
            prev_idx = (state["exercise_index"] - 1 + len(exercises)) % len(
                exercises
            )
            tracker.set_user_exercise_index(user_id, prev_idx)
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data.startswith("tts_"):
            await self._send_tts_reference(query, user_id, data)

        elif data == "btn_web":
            url = (
                settings.WEB_BASE_URL
                or f"http://{settings.HOST}:{settings.PORT}"
            )
            await self._safe_edit_text(
                query,
                f"🖥️ <b>Panel Web de tut_bot:</b>\n<code>{url}</code>\n\nUsa /ejercicio para volver al entrenamiento.",
            )

    async def _send_tts_reference(self, query, user_id: str, data: str):
        """Sintetiza la voz nativa y la envía como nota de voz a Telegram."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        if data == "tts_custom" and state.get("custom_phrase"):
            text = state["custom_phrase"]
        else:
            exercises = get_exercises(language=lang)
            idx = state["exercise_index"] % len(exercises)
            text = exercises[idx].target_text

        wav_bytes = azure_service.text_to_speech(text=text, language=lang)
        if not wav_bytes:
            await query.message.reply_text(
                "⚠️ No se pudo generar el audio nativo de referencia."
            )
            return

        ogg_bytes = audio_converter.wav_to_ogg_opus(wav_bytes)
        audio_stream = io.BytesIO(ogg_bytes if ogg_bytes else wav_bytes)
        audio_stream.name = (
            "referencia_nativa.ogg" if ogg_bytes else "referencia_nativa.wav"
        )

        caption_flag = "🇩🇪" if lang.startswith("de") else "🇺🇸"
        await query.message.reply_voice(
            voice=audio_stream,
            caption=f'🔊 <b>Referencia nativa ({caption_flag}):</b>\n"{text}"',
            parse_mode=ParseMode.HTML,
        )

    async def handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Si el usuario escribe un texto directamente, lo establece como frase de práctica."""
        text = (update.effective_message.text or "").strip()
        user_id = f"tg_{update.effective_user.id}"
        tracker.set_user_custom_phrase(user_id, text)

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Escuchar Referencia", callback_data="tts_custom"
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 Volver a Ejercicios", callback_data="btn_exercise"
                )
            ],
        ]
        await self._safe_reply_text(
            update.effective_message,
            f"🎯 <b>Frase para practicar establecida:</b>\n\n"
            f'👉 <i>"{text}"</i>\n\n'
            f"Mantén presionado el micrófono 🎙️ para enviar tu audio.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def handle_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Procesa la nota de voz enviada por el usuario."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        if state.get("custom_phrase"):
            reference_text = state["custom_phrase"]
            is_custom = True
        else:
            exercises = get_exercises(language=lang)
            idx = state["exercise_index"] % len(exercises)
            reference_text = exercises[idx].target_text
            is_custom = False

        status_msg = await update.message.reply_text(
            "🎧 <b>Analizando fonemas y acústica con Azure & Gemini...</b>",
            parse_mode=ParseMode.HTML,
        )
        await update.message.reply_chat_action(ChatAction.TYPING)

        temp_wav_path = None
        try:
            # 1. Descargar audio de Telegram (.ogg u otro formato)
            voice_obj = update.message.voice or update.message.audio
            if not voice_obj:
                return
            voice_file = await voice_obj.get_file()
            ogg_bytes = await voice_file.download_as_bytearray()

            # 2. Convertir a WAV PCM 16kHz mono para Azure Speech SDK
            wav_bytes = audio_converter.ogg_to_wav(bytes(ogg_bytes))
            if not wav_bytes:
                await self._safe_edit_text(
                    status_msg,
                    "❌ No se pudo procesar el formato del archivo de voz. Por favor intenta de nuevo.",
                )
                return

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_wav_path = f.name

            # 3. Evaluación Acústica (Azure Speech o Mock)
            eval_result = azure_service.assess_pronunciation(
                audio_wav_path=temp_wav_path,
                reference_text=reference_text,
                language=lang,
            )

            # 4. Feedback Conciso de Gemini Coach
            feedback = gemini_coach.generate_feedback(
                reference_text=reference_text,
                language=lang,
                overall_score=eval_result.overall_score,
                words=eval_result.words,
            )

            # 5. Registrar en historial SQLite
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
                badge = f"🟢 <b>¡Excelente! {score:.0f}/100</b> 🎉"
            elif score >= 70:
                badge = f"🟡 <b>¡Buen intento! {score:.0f}/100</b> 👍"
            else:
                badge = f"🔴 <b>A mejorar: {score:.0f}/100</b> 💪"

            acc_bar = _make_progress_bar(eval_result.accuracy_score)
            flu_bar = _make_progress_bar(eval_result.fluency_score)
            pro_bar = _make_progress_bar(
                eval_result.prosody_score or eval_result.accuracy_score
            )

            # Desglose de palabras con IPA
            word_lines = []
            for w in eval_result.words:
                icon = "✅" if w.score >= 75 else "⚠️"
                phoneme_details = " ".join(
                    [
                        f"{p.phoneme}({p.score:.0f})"
                        if p.score < 70
                        else p.phoneme
                        for p in w.phonemes
                    ]
                )
                word_lines.append(
                    f"{icon} <b>{w.word}</b> [<code>{phoneme_details}</code>] ➔ <code>{w.score:.0f}%</code>"
                )

            words_formatted = "\n".join(word_lines)

            # Aclaración amigable en español de los fonemas que fallaron
            clarifications = []
            for wp in weak_phonemes[:3]:
                explanation = get_phoneme_explanation(wp, lang)
                if explanation:
                    clarifications.append(f"• <code>/{wp}/</code>: {explanation}")

            clarif_section = ""
            if clarifications:
                clarif_section = (
                    f"\n📖 <b>Guía de símbolos detectados:</b>\n"
                    + "\n".join(clarifications)
                    + "\n"
                )

            # Limpiar y sanitizar texto de Gemini para HTML
            clean_feedback = _format_markdown_for_telegram(feedback)

            response_text = (
                f"{badge}\n"
                f'📝 Frase: <b>"{reference_text}"</b>\n\n'
                f"🎯 <b>Precisión:</b> <code>[{acc_bar}]</code> {eval_result.accuracy_score:.0f}%\n"
                f"🌊 <b>Fluidez:</b>   <code>[{flu_bar}]</code> {eval_result.fluency_score:.0f}%\n"
                f"🎵 <b>Prosodia:</b>  <code>[{pro_bar}]</code> {eval_result.prosody_score or 0:.0f}%\n\n"
                f"🔍 <b>Desglose de fonemas (IPA):</b>\n"
                f"{words_formatted}\n"
                f"{clarif_section}\n"
                f"👨‍🏫 <b>Tutor Gemini:</b>\n"
                f"{clean_feedback}"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔊 Escuchar Referencia",
                        callback_data="tts_custom"
                        if is_custom
                        else "tts_curated",
                    ),
                    InlineKeyboardButton(
                        "🔄 Repetir Frase", callback_data="btn_exercise"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "➡️ Siguiente Ejercicio", callback_data="ex_next"
                    ),
                    InlineKeyboardButton(
                        "📊 Estadísticas", callback_data="btn_stats"
                    ),
                ],
            ]

            await self._safe_edit_text(
                status_msg,
                response_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            logger.error(
                f"Error procesando nota de voz de Telegram: {e}", exc_info=True
            )
            await self._safe_edit_text(
                status_msg,
                f"⚠️ Ocurrió un inconveniente evaluando tu audio: {str(e)}\n"
                f"Por favor intenta de nuevo con /ejercicio.",
            )
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass

    async def start_polling(self):
        """Inicia el bot en modo polling asíncrono."""
        if not self.is_configured():
            logger.warning(
                "TelegramCoachBot: TELEGRAM_BOT_TOKEN no configurado. Bot no iniciado."
            )
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
    """Punto de entrada para ejecutar únicamente el bot de Telegram."""
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
