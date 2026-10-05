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
            return await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
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
        """Edita mensaje con HTML; soporta Message y CallbackQuery; si falla, reintenta sin formato."""
        edit_func = getattr(target, "edit_message_text", None)
        if edit_func is None:
            edit_func = getattr(target, "edit_text", None)
        if edit_func is None and hasattr(target, "message"):
            edit_func = getattr(target.message, "edit_text", None)

        if edit_func is None:
            logger.error(f"Target {type(target)} no soporta edición de texto")
            return None

        try:
            return await edit_func(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(
                f"Error en edit_text con parse_mode {parse_mode}: {e}. Reintentando texto plano."
            )
            return await edit_func(
                self._strip_html(text), reply_markup=reply_markup, parse_mode=None
            )

    async def _safe_send_chat_message(
        self, chat, text: str, reply_markup=None, parse_mode=ParseMode.HTML
    ):
        """Envía mensaje a chat con HTML; si falla, reintenta sin formato."""
        try:
            return await chat.send_message(text, reply_markup=reply_markup, parse_mode=parse_mode)
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
        app.add_handler(CommandHandler(["idioma", "lang", "language"], self.cmd_language))
        app.add_handler(CommandHandler(["modo", "skill", "habilidad"], self.cmd_mode))
        app.add_handler(CommandHandler(["nivel", "level"], self.cmd_level))
        app.add_handler(CommandHandler(["palabra", "vocabulario", "definir"], self.cmd_vocab))
        app.add_handler(CommandHandler(["libre", "custom", "fraselibre"], self.cmd_custom_phrase))
        app.add_handler(CommandHandler(["stats", "estadisticas", "progreso"], self.cmd_stats))
        app.add_handler(CommandHandler(["web", "panel", "link", "dashboard"], self.cmd_web))

        # Callback queries de botones inline
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Mensajes de voz y audio
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice))

        # Mensajes de texto normales
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        # Catch-all para comandos no reconocidos
        app.add_handler(MessageHandler(filters.COMMAND, self.cmd_unknown))

        # Manejador global de excepciones
        app.add_error_handler(self.error_handler)

        self.app = app
        return app

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
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

    async def cmd_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja comandos desconocidos o con erratas."""
        cmd_text = (update.effective_message.text or "").strip().lower()
        if any(typo in cmd_text for typo in ["strar", "star", "stat", "starr", "st"]):
            await self.cmd_start(update, context)
            return

        msg = (
            "🤔 <b>No reconocí ese comando.</b>\n\n"
            "• Usa <b>/ejercicio</b> para ver tu frase actual.\n"
            "• Usa <b>/start</b> para ir al menú principal.\n"
            "• O simplemente <b>mantén presionado el micrófono 🎙️</b> para enviar una nota de voz."
        )
        keyboard = [
            [InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu")],
        ]
        await self._safe_reply_text(
            update.effective_message,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mensaje de bienvenida y selección de modalidad e idioma inicial."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang_flag = "🇩🇪 Alemán" if state["language"].startswith("de") else "🇺🇸 Inglés"
        skill_names = {
            "speaking": "🗣️ Hablar",
            "writing": "✍️ Escribir",
            "listening": "👂 Comprender",
        }
        current_skill = skill_names.get(state.get("skill_mode", "speaking"), "🗣️ Hablar")
        current_level = state.get("level", "A1")

        welcome_text = (
            "🎙️ <b>¡Bienvenido a tut_bot!</b>\n"
            "Tu tutor integral inteligente para <b>Alemán</b> e <b>Inglés</b> con <b>Azure Speech (IPA)</b> y <b>Google Gemini</b>.\n\n"
            "🎯 <b>3 Habilidades de Aprendizaje:</b>\n"
            "• 🗣️ <b>Hablar:</b> Diagnóstico acústico de fonemas con notas de voz.\n"
            "• ✍️ <b>Escribir:</b> Redacción, declinaciones y corrección gramatical inmediata.\n"
            "• 👂 <b>Comprender:</b> Audición nativa, responder preguntas y aprender vocabulario.\n\n"
            f"🌐 <b>Idioma:</b> {lang_flag} | <b>Nivel:</b> {current_level} | <b>Modo:</b> {current_skill}\n\n"
            "💡 <i>¿Tienes duda con una palabra? Escribe <code>/palabra término</code> en cualquier momento.</i>"
        )

        keyboard = [
            [
                InlineKeyboardButton("🎯 Modo y Nivel", callback_data="btn_mode_menu"),
                InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise"),
            ],
            [
                InlineKeyboardButton("🇩🇪 Alemán", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
                InlineKeyboardButton("🌐 Panel Web", callback_data="btn_web"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_reply_text(
            update.effective_message, welcome_text, reply_markup=reply_markup
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📖 <b>Comandos disponibles en tut_bot:</b>\n\n"
            "• <b>/ejercicio</b> — Muestra el ejercicio activo según tu modo y nivel.\n"
            "• <b>/modo</b> — Cambia entre 🗣️ Hablar, ✍️ Escribir y 👂 Comprender.\n"
            "• <b>/nivel</b> — Elige tu nivel MCER (A1, A2, B1).\n"
            "• <b>/palabra &lt;término&gt;</b> — Consulta el significado, género o ejemplos de cualquier palabra.\n"
            "• <b>/idioma</b> — Alterna entre Alemán (de-DE) e Inglés (en-US).\n"
            "• <b>/libre &lt;frase&gt;</b> — Configura cualquier frase que desees pronunciar.\n"
            "• <b>/stats</b> — Muestra tu puntuación promedio y fonemas a mejorar.\n"
            "• <b>/web</b> — Enlace al panel web en tu PC."
        )
        await self._safe_reply_text(update.effective_message, help_text)

    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menú interactivo para cambiar Modalidad y Nivel MCER."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        current_skill = state.get("skill_mode", "speaking")
        current_level = state.get("level", "A1")
        lang_flag = "🇩🇪 Alemán" if state["language"].startswith("de") else "🇺🇸 Inglés"

        skill_labels = {
            "speaking": "🗣️ Hablar (Pronunciación IPA)",
            "writing": "✍️ Escribir (Gramática y Traducción)",
            "listening": "👂 Comprender (Audición y Vocabulario)",
        }

        msg = (
            f"🎯 <b>Configuración de Entrenamiento</b>\n\n"
            f"• <b>Idioma:</b> {lang_flag}\n"
            f"• <b>Modalidad Actual:</b> {skill_labels.get(current_skill, current_skill)}\n"
            f"• <b>Nivel MCER:</b> {current_level}\n\n"
            f"👇 <b>Elige qué habilidad deseas practicar o cambia tu nivel:</b>"
        )

        keyboard = [
            [
                InlineKeyboardButton("🗣️ Hablar", callback_data="mode_speaking"),
                InlineKeyboardButton("✍️ Escribir", callback_data="mode_writing"),
                InlineKeyboardButton("👂 Comprender", callback_data="mode_listening"),
            ],
            [
                InlineKeyboardButton("🟢 A1 (Básico)", callback_data="level_A1"),
                InlineKeyboardButton("🟡 A2 (Elemental)", callback_data="level_A2"),
                InlineKeyboardButton("🔵 B1 (Intermedio)", callback_data="level_B1"),
            ],
            [
                InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
            ],
        ]
        await self._safe_reply_text(
            update.effective_message, msg, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.cmd_mode(update, context)

    async def cmd_vocab(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Consulta directa del significado de una palabra o frase desconocida."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        term = " ".join(context.args).strip() if context.args else ""
        if not term:
            await self._safe_reply_text(
                update.effective_message,
                "📖 Por favor indica la palabra que deseas consultar.\n"
                "Ejemplo: <code>/palabra Hund</code> o <code>/palabra weather</code>",
            )
            return

        await update.effective_message.reply_chat_action(ChatAction.TYPING)
        explanation = gemini_coach.explain_vocabulary(term, lang)
        clean_html = _format_markdown_for_telegram(explanation)
        keyboard = [
            [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
        ]
        await self._safe_reply_text(
            update.effective_message,
            f"📖 <b>Consulta de Vocabulario:</b>\n\n{clean_html}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def cmd_custom_phrase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            [InlineKeyboardButton("🔊 Escuchar Pronunciación", callback_data="tts_custom")],
            [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
        ]
        await self._safe_reply_text(
            update.effective_message,
            f"🎯 <b>Frase personalizada fijada:</b>\n\n"
            f'👉 <i>"{phrase}"</i>\n\n'
            f"Mantén presionado el micrófono 🎙️ de Telegram y envía tu nota de voz para evaluarla.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def cmd_exercise(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_exercise_card(update, user_id)

    async def _send_exercise_card(self, update: Update, user_id: str, edit_message: bool = False):
        """Envía o actualiza la tarjeta del ejercicio según la modalidad activa (Hablar, Escribir, Comprender)."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        skill_mode = state.get("skill_mode", "speaking")
        level = state.get("level", "A1")

        exercises = get_exercises(language=lang, level=level, skill_type=skill_mode)
        if not exercises:
            exercises = get_exercises(language=lang, skill_type=skill_mode)
        if not exercises:
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

        if skill_mode == "writing":
            card_lines = [
                f"✍️ <b>{lang_header} — [{ex.level}] {ex.category}</b>",
                f"<b>Tema:</b> {ex.title}\n",
                "📝 <b>Consigna de Escritura:</b>",
                f"👉 <b>{ex.prompt or 'Traduce al alemán:'}</b>\n",
            ]
            if ex.grammar_note:
                card_lines.append(f"💡 <b>Pista Gramatical:</b> <i>{ex.grammar_note}</i>\n")
            card_lines.extend(
                [
                    f"<i>(Ejercicio {idx + 1} de {len(exercises)})</i>",
                    "👇 <b>Escribe tu respuesta directamente en este chat:</b>",
                ]
            )
            keyboard = [
                [
                    InlineKeyboardButton("📖 Vocabulario de la Frase", callback_data="vocab_card"),
                    InlineKeyboardButton("🔊 Escuchar Frase Modelo", callback_data=f"tts_{ex.id}"),
                ],
                [
                    InlineKeyboardButton("⬅️ Anterior", callback_data="ex_prev"),
                    InlineKeyboardButton(f"{idx + 1}/{len(exercises)}", callback_data="ex_curr"),
                    InlineKeyboardButton("Siguiente ➡️", callback_data="ex_next"),
                ],
                [
                    InlineKeyboardButton("🎯 Cambiar Modo/Nivel", callback_data="btn_mode_menu"),
                    InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                ],
            ]

        elif skill_mode == "listening":
            card_lines = [
                f"👂 <b>{lang_header} — [{ex.level}] {ex.category}</b>",
                f"<b>Tema:</b> {ex.title}\n",
                "🎧 <b>Pregunta de Comprensión:</b>",
                f"👉 <b>{ex.prompt or 'Escucha el audio nativo y responde:'}</b>\n",
            ]

            # Andamiaje cognitivo (Scaffolding): Vocabulario clave visible antes de escuchar
            if ex.vocabulary_breakdown:
                card_lines.append("🔑 <b>Vocabulario de apoyo:</b>")
                for w, meaning in list(ex.vocabulary_breakdown.items())[:3]:
                    card_lines.append(f"• <b>{w}</b>: {meaning}")
                card_lines.append("")

            if ex.options:
                card_lines.append("<b>Opciones:</b>")
                for i, opt in enumerate(ex.options):
                    card_lines.append(f"{i + 1}️⃣ {opt}")
                card_lines.append("")
            card_lines.extend(
                [
                    f"<i>(Ejercicio {idx + 1} de {len(exercises)})</i>",
                    "👇 <b>Escucha el audio y luego pulsa la opción correcta o responde por texto:</b>",
                ]
            )

            opt_buttons = []
            if ex.options:
                opt_buttons = [
                    InlineKeyboardButton(f"{i + 1}️⃣", callback_data=f"listen_opt_{i}")
                    for i in range(len(ex.options))
                ]

            keyboard = [
                [
                    InlineKeyboardButton("🔊 Escuchar (1.0x)", callback_data=f"tts_{ex.id}"),
                    InlineKeyboardButton("🐢 Lento (0.8x)", callback_data=f"tts_slow_{ex.id}"),
                ],
                [
                    InlineKeyboardButton("📖 Vocabulario Completo", callback_data="vocab_card"),
                ],
            ]
            if opt_buttons:
                keyboard.append(opt_buttons)
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton("⬅️ Anterior", callback_data="ex_prev"),
                        InlineKeyboardButton(
                            f"{idx + 1}/{len(exercises)}", callback_data="ex_curr"
                        ),
                        InlineKeyboardButton("Siguiente ➡️", callback_data="ex_next"),
                    ],
                    [
                        InlineKeyboardButton(
                            "🎯 Cambiar Modo/Nivel", callback_data="btn_mode_menu"
                        ),
                        InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                    ],
                ]
            )

        else:
            # Modo SPEAKING (Hablar)
            phonemes_str = " · ".join([f"<code>/{p}/</code>" for p in ex.focus_phonemes])
            card_lines = [
                f"🗣️ <b>{lang_header} — [{ex.level}] {ex.category}</b>",
                f"<b>Tema:</b> {ex.title}\n",
                "🗣️ <b>Frase a pronunciar:</b>",
                f'👉 <b>"{ex.target_text}"</b>\n',
            ]
            if ex.phonetic_guide:
                card_lines.append(f'🗣️ <b>Pronunciación fácil:</b> <i>"{ex.phonetic_guide}"</i>')
            if ex.ipa:
                card_lines.append(f"🔤 <b>Símbolos IPA:</b> <code>/{ex.ipa}/</code>")
            if ex.phonetic_notes:
                card_lines.append(f"ℹ️ <b>Guía de sonidos:</b> {ex.phonetic_notes}")

            card_lines.extend(
                [
                    f'🇪🇸 <b>Traducción:</b> <i>"{ex.translation_es}"</i>',
                    f"🎯 <b>Sonidos clave:</b> {phonemes_str}\n",
                    "💡 <b>Consejo de Articulación:</b>",
                    f"<i>{ex.tip}</i>\n",
                    f"<i>(Ejercicio {idx + 1} de {len(exercises)})</i>",
                    "👇 <b>Mantén presionado el micrófono 🎙️ para enviar tu audio</b>",
                ]
            )
            keyboard = [
                [
                    InlineKeyboardButton("🔊 Escuchar (1.0x)", callback_data=f"tts_{ex.id}"),
                    InlineKeyboardButton("🐢 Lento (0.8x)", callback_data=f"tts_slow_{ex.id}"),
                ],
                [
                    InlineKeyboardButton("📖 Vocabulario", callback_data="vocab_card"),
                ],
                [
                    InlineKeyboardButton("⬅️ Anterior", callback_data="ex_prev"),
                    InlineKeyboardButton(f"{idx + 1}/{len(exercises)}", callback_data="ex_curr"),
                    InlineKeyboardButton("Siguiente ➡️", callback_data="ex_next"),
                ],
                [
                    InlineKeyboardButton("🎯 Cambiar Modo/Nivel", callback_data="btn_mode_menu"),
                    InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                ],
            ]

        card_text = "\n".join(card_lines)
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

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = f"tg_{update.effective_user.id}"
        await self._send_stats(update, user_id)

    async def _send_stats(self, update: Update, user_id: str, edit_message: bool = False):
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
            [InlineKeyboardButton("📚 Ir a Ejercicios", callback_data="btn_exercise")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(
                    update.effective_chat, text, reply_markup=reply_markup
                )
        else:
            await self._safe_send_chat_message(
                update.effective_chat, text, reply_markup=reply_markup
            )

    async def cmd_web(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = settings.WEB_BASE_URL or f"http://{settings.HOST}:{settings.PORT}"
        text = (
            f"🖥️ <b>Panel Web interactivo de tut_bot:</b>\n"
            f"<code>{url}</code>\n\n"
            f"Ábrelo en el navegador de tu computadora para ver el osciloscopio en vivo y el atlas fonético."
        )
        await self._safe_reply_text(update.effective_message, text)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    InlineKeyboardButton("🇩🇪 Alemán (de-DE)", callback_data="lang_de"),
                    InlineKeyboardButton("🇺🇸 Inglés (en-US)", callback_data="lang_en"),
                ],
                [InlineKeyboardButton("⬅️ Volver", callback_data="btn_exercise")],
            ]
            await self._safe_edit_text(
                query,
                "🌍 <b>Selecciona el idioma para practicar:</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        elif data == "btn_mode_menu":
            await self.cmd_mode(update, context)

        elif data.startswith("mode_"):
            new_mode = data.replace("mode_", "")
            tracker.set_user_skill_mode(user_id, new_mode)
            skill_names = {
                "speaking": "🗣️ Hablar (Pronunciación)",
                "writing": "✍️ Escribir (Gramática y Traducción)",
                "listening": "👂 Comprender (Audición y Vocabulario)",
            }
            await self._safe_edit_text(
                query,
                f"✅ Modo de entrenamiento cambiado a: <b>{skill_names.get(new_mode, new_mode)}</b>.",
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data.startswith("level_"):
            new_level = data.replace("level_", "")
            tracker.set_user_level(user_id, new_level)
            await self._safe_edit_text(
                query, f"✅ Nivel de dificultad cambiado a: <b>{new_level}</b>."
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "vocab_card":
            state = tracker.get_user_state(user_id)
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            idx = state["exercise_index"] % len(exercises)
            ex = exercises[idx]

            if ex.vocabulary_breakdown:
                lines = [
                    f"📖 <b>Vocabulario de la frase [{ex.level}]:</b>\n",
                    f'👉 <i>"{ex.target_text}"</i>\n',
                ]
                for w, mean in ex.vocabulary_breakdown.items():
                    lines.append(f"• <b>{w}</b>: {mean}")
                if ex.grammar_note:
                    lines.append(f"\n💡 <b>Gramática:</b> <i>{ex.grammar_note}</i>")
                vocab_msg = "\n".join(lines)
            else:
                raw_exp = gemini_coach.explain_vocabulary(ex.target_text, state["language"])
                vocab_msg = _format_markdown_for_telegram(raw_exp)

            keyboard = [
                [InlineKeyboardButton("⬅️ Volver al Ejercicio", callback_data="btn_exercise")],
            ]
            await self._safe_send_chat_message(
                update.effective_chat,
                vocab_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        elif data.startswith("listen_opt_"):
            chosen_idx = int(data.replace("listen_opt_", ""))
            state = tracker.get_user_state(user_id)
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type="listening",
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            idx = state["exercise_index"] % len(exercises)
            ex = exercises[idx]

            is_correct = chosen_idx == ex.correct_option_index
            chosen_str = (
                ex.options[chosen_idx] if ex.options and chosen_idx < len(ex.options) else ""
            )
            correct_str = (
                ex.options[ex.correct_option_index]
                if ex.options
                and ex.correct_option_index is not None
                and ex.correct_option_index < len(ex.options)
                else ex.translation_es
            )

            if is_correct:
                res_msg = (
                    f"🟢 <b>¡Correcto!</b> 🎉\n\n"
                    f'Seleccionaste: <i>"{chosen_str}"</i>\n'
                    f"¡Has comprendido el audio perfectamente!\n\n"
                    f'📖 <b>Transcripción:</b> <i>"{ex.target_text}"</i>\n'
                    f'🇪🇸 <b>Significado:</b> <i>"{ex.translation_es}"</i>'
                )
            else:
                res_msg = (
                    f"🔴 <b>Casi</b> 👍\n\n"
                    f'Elegiste: <i>"{chosen_str}"</i>\n'
                    f'La respuesta correcta era: <b>"{correct_str}"</b>\n\n'
                    f'📖 <b>Transcripción:</b> <i>"{ex.target_text}"</i>\n'
                    f'🇪🇸 <b>Significado:</b> <i>"{ex.translation_es}"</i>'
                )

            keyboard = [
                [
                    InlineKeyboardButton("➡️ Siguiente Ejercicio", callback_data="ex_next"),
                    InlineKeyboardButton("🔄 Reintentar", callback_data="btn_exercise"),
                ],
                [
                    InlineKeyboardButton("🔊 Volver a Escuchar", callback_data=f"tts_{ex.id}"),
                    InlineKeyboardButton("📖 Vocabulario", callback_data="vocab_card"),
                ],
            ]
            await self._safe_send_chat_message(
                update.effective_chat,
                res_msg,
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
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            next_idx = (state["exercise_index"] + 1) % len(exercises)
            tracker.set_user_exercise_index(user_id, next_idx)
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data == "ex_prev":
            state = tracker.get_user_state(user_id)
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            prev_idx = (state["exercise_index"] - 1 + len(exercises)) % len(exercises)
            tracker.set_user_exercise_index(user_id, prev_idx)
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data.startswith("tts_slow_"):
            await self._send_tts_reference(query, user_id, data, slow=True)

        elif data.startswith("tts_"):
            await self._send_tts_reference(query, user_id, data, slow=False)

        elif data == "btn_web":
            url = settings.WEB_BASE_URL or f"http://{settings.HOST}:{settings.PORT}"
            await self._safe_edit_text(
                query,
                f"🖥️ <b>Panel Web de tut_bot:</b>\n<code>{url}</code>\n\nUsa /ejercicio para volver al entrenamiento.",
            )

    async def _send_tts_reference(self, query, user_id: str, data: str, slow: bool = False):
        """Sintetiza la voz nativa y la envía como nota de voz a Telegram (con opción de audio lento)."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        actual_id = data.replace("tts_slow_", "").replace("tts_", "")
        if actual_id == "custom" and state.get("custom_phrase"):
            text = state["custom_phrase"]
        else:
            exercises = get_exercises(
                language=lang,
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
            )
            if not exercises:
                exercises = get_exercises(language=lang)
            # Buscar por ID si está especificado
            matching = [e for e in exercises if e.id == actual_id]
            if matching:
                text = matching[0].target_text
            else:
                idx = state["exercise_index"] % len(exercises)
                text = exercises[idx].target_text

        wav_bytes = azure_service.text_to_speech(text=text, language=lang, slow=slow)
        if not wav_bytes:
            await query.message.reply_text("⚠️ No se pudo generar el audio nativo de referencia.")
            return

        ogg_bytes = audio_converter.wav_to_ogg_opus(wav_bytes)
        audio_stream = io.BytesIO(ogg_bytes if ogg_bytes else wav_bytes)
        audio_stream.name = "referencia_lenta.ogg" if slow else "referencia_nativa.ogg"

        caption_flag = "🇩🇪" if lang.startswith("de") else "🇺🇸"
        icon = "🐢" if slow else "🔊"
        label = (
            f"{icon} <b>Referencia pausada (0.8x - {caption_flag}):</b>"
            if slow
            else f"{icon} <b>Referencia nativa ({caption_flag}):</b>"
        )
        await query.message.reply_voice(
            voice=audio_stream,
            caption=f'{label}\n"{text}"',
            parse_mode=ParseMode.HTML,
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja las respuestas de texto, preguntas de vocabulario y respuestas de escritura/comprensión."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        skill_mode = state.get("skill_mode", "speaking")
        level = state.get("level", "A1")
        text = (update.effective_message.text or "").strip()

        # 1. Consulta directa de vocabulario o palabra desconocida
        lower_text = text.lower()
        if (
            lower_text.startswith("/palabra")
            or lower_text.startswith("¿que significa")
            or lower_text.startswith("que significa")
            or lower_text.startswith("¿qué significa")
            or lower_text.startswith("qué significa")
            or lower_text.startswith("definir")
        ):
            for prefix in [
                "/palabra",
                "¿qué significa",
                "qué significa",
                "¿que significa",
                "que significa",
                "definir",
            ]:
                if lower_text.startswith(prefix):
                    clean_term = text[len(prefix) :].strip(" ?:.,\"'")
                    break
            else:
                clean_term = text

            if not clean_term:
                await self._safe_reply_text(
                    update.effective_message,
                    "📖 Indica la palabra que deseas consultar. Ejemplo: <code>/palabra Hund</code> o <code>¿Qué significa 'Buch'?</code>",
                )
                return

            await update.effective_message.reply_chat_action(ChatAction.TYPING)
            explanation = gemini_coach.explain_vocabulary(clean_term, lang)
            clean_html = _format_markdown_for_telegram(explanation)
            keyboard = [
                [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
            ]
            await self._safe_reply_text(
                update.effective_message,
                f"📖 <b>Consulta de Vocabulario:</b>\n\n{clean_html}",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # 2. Modo ESCRITURA: Evaluar la respuesta del alumno
        if skill_mode == "writing":
            exercises = get_exercises(language=lang, level=level, skill_type="writing")
            if not exercises:
                exercises = get_exercises(language=lang, skill_type="writing")
            if not exercises:
                exercises = get_exercises(language=lang)

            idx = state["exercise_index"] % len(exercises)
            ex = exercises[idx]

            await update.effective_message.reply_chat_action(ChatAction.TYPING)
            eval_res = gemini_coach.evaluate_writing(
                user_input=text,
                target_text=ex.target_text,
                prompt=ex.prompt or ex.title,
                language=lang,
                level=ex.level,
            )

            badge = (
                "🟢 <b>¡Excelente trabajo!</b> 🎉"
                if eval_res.is_correct
                else "🟡 <b>Buen intento</b> 💪"
            )
            corrections_str = ""
            if eval_res.corrections:
                corrections_str = (
                    "\n🔍 <b>Correcciones:</b>\n"
                    + "\n".join([f"• {c}" for c in eval_res.corrections])
                    + "\n"
                )

            grammar_str = (
                f"\n💡 <b>Regla:</b> <i>{eval_res.grammar_notes}</i>\n"
                if eval_res.grammar_notes
                else ""
            )
            clean_feedback = _format_markdown_for_telegram(eval_res.pedagogical_feedback)

            report = (
                f"{badge}\n\n"
                f'📝 <b>Tu respuesta:</b> <i>"{text}"</i>\n'
                f'🎯 <b>Frase modelo:</b> <b>"{ex.target_text}"</b>\n'
                f"📊 <b>Puntaje:</b> <code>{eval_res.score:.0f}/100</code>\n"
                f"{corrections_str}"
                f"{grammar_str}\n"
                f"👨‍🏫 <b>Consejo del Tutor:</b>\n{clean_feedback}"
            )

            keyboard = [
                [
                    InlineKeyboardButton("➡️ Siguiente Ejercicio", callback_data="ex_next"),
                    InlineKeyboardButton("🔄 Reintentar", callback_data="btn_exercise"),
                ],
                [
                    InlineKeyboardButton("📖 Ver Vocabulario", callback_data="vocab_card"),
                    InlineKeyboardButton("🔊 Escuchar Modelo", callback_data=f"tts_{ex.id}"),
                ],
                [
                    InlineKeyboardButton("🎯 Cambiar Modo/Nivel", callback_data="btn_mode_menu"),
                ],
            ]

            await self._safe_reply_text(
                update.effective_message,
                report,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # 3. Modo COMPRENSIÓN (Listening): Evaluar lo que respondió por texto
        if skill_mode == "listening":
            exercises = get_exercises(language=lang, level=level, skill_type="listening")
            if not exercises:
                exercises = get_exercises(language=lang)
            idx = state["exercise_index"] % len(exercises)
            ex = exercises[idx]

            # 3.1 Detección inteligente de opción (si el ejercicio tiene opciones múltiples)
            selected_option_idx = None
            clean_text = text.strip().lower()

            if ex.options:
                # Detección de dígitos: "1", "2", "3", "1.", "#1", "opción 1", "opcion 1", "la 1", "el 1"
                num_match = re.match(
                    r"^(?:opci[oó]n|la|el|número|numero)?\s*#?([1-9])(?:\ufe0f?\u20e3)?\.?$",
                    clean_text,
                )
                if num_match:
                    idx_candidate = int(num_match.group(1)) - 1
                    if 0 <= idx_candidate < len(ex.options):
                        selected_option_idx = idx_candidate

                # Detección de letras: "a", "b", "c", "opción a", etc.
                if selected_option_idx is None:
                    letter_match = re.match(r"^(?:opci[oó]n|la|el)?\s*([a-d])\.?$", clean_text)
                    if letter_match:
                        idx_candidate = ord(letter_match.group(1)) - ord("a")
                        if 0 <= idx_candidate < len(ex.options):
                            selected_option_idx = idx_candidate

                # Detección por texto contenido en alguna opción (ej: "19,50" o "neunzehn")
                if selected_option_idx is None:
                    for i, opt in enumerate(ex.options):
                        opt_lower = opt.lower()
                        words = [
                            w
                            for w in clean_text.replace(",", " ").replace(".", " ").split()
                            if len(w) >= 3
                        ]
                        if clean_text in opt_lower or (
                            words and all(w in opt_lower for w in words)
                        ):
                            selected_option_idx = i
                            break

            # Si el usuario seleccionó una opción válida del ejercicio
            if selected_option_idx is not None and ex.options:
                is_correct = selected_option_idx == ex.correct_option_index
                chosen_str = ex.options[selected_option_idx]
                correct_str = (
                    ex.options[ex.correct_option_index]
                    if ex.correct_option_index is not None
                    and ex.correct_option_index < len(ex.options)
                    else ex.translation_es
                )

                if is_correct:
                    res_msg = (
                        f"🟢 <b>¡Correcto!</b> 🎉\n\n"
                        f"Seleccionaste: <b>{selected_option_idx + 1}️⃣ {chosen_str}</b>\n"
                        f"¡Has comprendido el audio perfectamente!\n\n"
                        f'📖 <b>Transcripción:</b> <i>"{ex.target_text}"</i>\n'
                        f'🇪🇸 <b>Significado:</b> <i>"{ex.translation_es}"</i>'
                    )
                else:
                    res_msg = (
                        f"🔴 <b>Casi</b> 👍\n\n"
                        f'Seleccionaste: <i>{selected_option_idx + 1}️⃣ "{chosen_str}"</i>\n'
                        f'La respuesta correcta era la {ex.correct_option_index + 1}️⃣: <b>"{correct_str}"</b>\n\n'
                        f'📖 <b>Transcripción:</b> <i>"{ex.target_text}"</i>\n'
                        f'🇪🇸 <b>Significado:</b> <i>"{ex.translation_es}"</i>'
                    )

                keyboard = [
                    [
                        InlineKeyboardButton("➡️ Siguiente Ejercicio", callback_data="ex_next"),
                        InlineKeyboardButton("🔄 Reintentar", callback_data="btn_exercise"),
                    ],
                    [
                        InlineKeyboardButton("🔊 Volver a Escuchar", callback_data=f"tts_{ex.id}"),
                        InlineKeyboardButton("📖 Vocabulario", callback_data="vocab_card"),
                    ],
                ]
                await self._safe_reply_text(
                    update.effective_message,
                    res_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
                return

            # Si no fue opción directa, evaluar con IA pasando las opciones
            await update.effective_message.reply_chat_action(ChatAction.TYPING)
            comp_res = gemini_coach.evaluate_comprehension(
                user_answer=text,
                audio_transcript=ex.target_text,
                question=ex.prompt or ex.title,
                target_answer=ex.translation_es,
                language=lang,
                options=ex.options,
            )

            badge = (
                "🟢 <b>¡Correcto!</b> 🎉" if comp_res.get("is_correct") else "🟡 <b>Atención</b> 🎧"
            )
            keyboard = [
                [
                    InlineKeyboardButton("➡️ Siguiente", callback_data="ex_next"),
                    InlineKeyboardButton("🔄 Reintentar", callback_data="btn_exercise"),
                ],
                [
                    InlineKeyboardButton("🔊 Volver a Escuchar", callback_data=f"tts_{ex.id}"),
                    InlineKeyboardButton("📖 Vocabulario", callback_data="vocab_card"),
                ],
            ]
            await self._safe_reply_text(
                update.effective_message,
                f"{badge}\n\n"
                f'📝 <b>Tu respuesta:</b> "{text}"\n'
                f"💡 <b>Explicación:</b> {comp_res.get('feedback', '')}\n\n"
                f'📖 <b>Transcripción:</b> <i>"{ex.target_text}"</i>\n'
                f'🇪🇸 <b>Significado:</b> <i>"{ex.translation_es}"</i>',
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # 4. Modo HABLAR: Si escribe texto, fijarlo como frase personalizada para pronunciar
        tracker.set_user_custom_phrase(user_id, text)
        keyboard = [
            [InlineKeyboardButton("🔊 Escuchar Referencia", callback_data="tts_custom")],
            [InlineKeyboardButton("📚 Volver a Ejercicios", callback_data="btn_exercise")],
        ]
        await self._safe_reply_text(
            update.effective_message,
            f"🎯 <b>Frase para practicar establecida:</b>\n\n"
            f'👉 <i>"{text}"</i>\n\n'
            f"Mantén presionado el micrófono 🎙️ para enviar tu audio.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa la nota de voz enviada por el usuario."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]

        if state.get("custom_phrase"):
            reference_text = state["custom_phrase"]
            is_custom = True
        else:
            exercises = get_exercises(
                language=lang,
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
            )
            if not exercises:
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
            pro_bar = _make_progress_bar(eval_result.prosody_score or eval_result.accuracy_score)

            # Desglose de palabras con IPA
            word_lines = []
            for w in eval_result.words:
                icon = "✅" if w.score >= 75 else "⚠️"
                phoneme_details = " ".join(
                    [
                        f"{p.phoneme}({p.score:.0f})" if p.score < 70 else p.phoneme
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
                    "\n📖 <b>Guía de símbolos detectados:</b>\n" + "\n".join(clarifications) + "\n"
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
                        callback_data="tts_custom" if is_custom else "tts_curated",
                    ),
                    InlineKeyboardButton("🔄 Repetir Frase", callback_data="btn_exercise"),
                ],
                [
                    InlineKeyboardButton("➡️ Siguiente Ejercicio", callback_data="ex_next"),
                    InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                ],
            ]

            await self._safe_edit_text(
                status_msg,
                response_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            logger.error(f"Error procesando nota de voz de Telegram: {e}", exc_info=True)
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
