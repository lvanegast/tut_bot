import io
import logging
import os
import re
import tempfile
from typing import Any, Dict, Optional

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
from tut_bot.services.curriculum import (
    ScenarioInfo,
    extract_words_from_text,
    get_curriculum_scenarios,
    get_curriculum_units,
    get_scenario_by_id,
    get_scenarios_for_unit,
    get_unit_by_id,
)
from tut_bot.services.exercises import get_exercises
from tut_bot.services.final_exam import get_level_exam
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
    """Convierte markdown (encabezados, **negrita**, *cursiva*) a formato HTML válido para Telegram sin dejar marcas como ##."""
    if not text:
        return ""
    # 1. Escapar entidades HTML especiales
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2. Convertir encabezados Markdown (#, ##, ###) a negrita limpia
    lines = []
    for line in text.split("\n"):
        header_match = re.match(r"^\s*#{1,6}\s*(.+)$", line)
        if header_match:
            header_content = header_match.group(1).strip()
            lines.append(f"<b>{header_content}</b>")
        else:
            lines.append(line)
    text = "\n".join(lines)

    # 3. Limpiar cualquier ## o # suelto al inicio o entre texto
    text = re.sub(r"#{2,}", "", text)

    # 4. Convertir **negrita**
    parts = text.split("**")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<b>{part}</b>")
            else:
                res.append(part)
        text = "".join(res)

    # 5. Convertir *cursiva* si queda
    parts = text.split("*")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<i>{part}</i>")
            else:
                res.append(part)
        text = "".join(res)

    return text.strip()


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


def get_phoneme_friendly_label(phoneme: str, language: str = "de-DE") -> str:
    """Devuelve la representación legible con letra común para que el usuario siempre identifique el sonido aunque su móvil no tenga la fuente IPA."""
    clean_p = phoneme.replace("/", "").replace("[", "").replace("]", "").strip()
    LABELS = {
        # Alemán
        "ʁ": "r gutural",
        "ɐ": "-er final",
        "ç": "ch suave",
        "x": "ch velar",
        "ʃ": "sh",
        "øː": "ö larga",
        "œ": "ö corta",
        "yː": "ü larga",
        "ʏ": "ü corta",
        "ɛː": "ä abierta",
        "ɛ": "e abierta",
        "eː": "e larga",
        "iː": "i larga",
        "ɪ": "i corta",
        "oː": "o larga",
        "ɔ": "o corta",
        "uː": "u larga",
        "ʊ": "u corta",
        "ə": "e relajada",
        "ts": "z / ts",
        "z": "s sonora",
        "s": "s sorda",
        "aɪ": "ei / ai",
        "aʊ": "au",
        "ɔʏ": "eu / äu",
        # Inglés
        "θ": "th sorda",
        "ð": "th sonora",
        "æ": "a abierta",
        "ʌ": "u central",
        "w": "w inglesa",
        "v": "v labiodental",
        "dʒ": "j suave",
        "tʃ": "ch",
        "ŋ": "ng",
    }
    label = LABELS.get(clean_p)
    if label:
        return f"'{label}' (/{clean_p}/)"
    return f"/{clean_p}/"


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
        app.add_handler(
            CommandHandler(
                ["conversar", "dialogo", "mision", "roleplay", "chat"],
                self.cmd_conversation,
            )
        )
        app.add_handler(CommandHandler(["palabra", "vocabulario", "definir"], self.cmd_vocab))
        app.add_handler(
            CommandHandler(
                ["tema", "temas", "unidad", "unidades", "modulo", "modulos"], self.cmd_units
            )
        )
        app.add_handler(
            CommandHandler(
                ["examen", "evaluacion", "test", "certificacion"], self.cmd_exam
            )
        )
        app.add_handler(CommandHandler(["libre", "custom", "fraselibre"], self.cmd_custom_phrase))
        app.add_handler(CommandHandler(["stats", "estadisticas", "progreso"], self.cmd_stats))
        app.add_handler(CommandHandler(["web", "panel", "link", "dashboard"], self.cmd_web))
        app.add_handler(
            CommandHandler(["reset", "reiniciar", "borrarprogreso"], self.cmd_reset)
        )

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
            "conversation": "💬 Conversar",
        }
        current_skill = skill_names.get(state.get("skill_mode", "speaking"), "🗣️ Hablar")
        current_level = state.get("level", "A1")

        welcome_text = (
            "🎙️ <b>¡Bienvenido a tut_bot!</b>\n"
            "Tu tutor integral inteligente para <b>Alemán</b> e <b>Inglés</b> con <b>Azure Speech (IPA)</b> y <b>Google Gemini</b>.\n\n"
            "🎯 <b>4 Habilidades de Aprendizaje:</b>\n"
            "• 🗣️ <b>Hablar:</b> Diagnóstico acústico de fonemas con notas de voz.\n"
            "• ✍️ <b>Escribir:</b> Redacción, declinaciones y corrección gramatical inmediata.\n"
            "• 👂 <b>Comprender:</b> Audición nativa, responder preguntas y aprender vocabulario.\n"
            "• 💬 <b>Conversar:</b> Misiones de rol inmersivas con personajes nativos IA por unidad temática.\n\n"
            f"🌐 <b>Idioma:</b> {lang_flag} | <b>Nivel:</b> {current_level} | <b>Modo:</b> {current_skill}\n\n"
            "🎓 <b>Certificación Oficial CEFR:</b> Completa las unidades temáticas y aprueba la <b>Evaluación Final</b> para certificar tu nivel y ascender.\n"
            "💡 <i>¿Tienes duda con una palabra? Escribe <code>/palabra término</code> en cualquier momento.</i>"
        )

        keyboard = [
            [
                InlineKeyboardButton("🎯 Modo y Nivel", callback_data="btn_mode_menu"),
                InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise"),
            ],
            [
                InlineKeyboardButton(f"📝 Evaluación Final {current_level}", callback_data="btn_exam_entry"),
                InlineKeyboardButton("📂 Unidades", callback_data="btn_units_menu"),
            ],
            [
                InlineKeyboardButton("💬 Misión de Diálogo", callback_data="mode_conversation"),
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
            ],
            [
                InlineKeyboardButton("🇩🇪 Alemán", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 Inglés", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton("🔄 Reiniciar Progreso", callback_data="btn_reset_ask"),
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
            "• <b>/conversar</b> — Inicia una misión de diálogo conversacional (roleplay con IA).\n"
            "• <b>/modo</b> — Cambia entre 🗣️ Hablar, ✍️ Escribir, 👂 Comprender y 💬 Conversar.\n"
            "• <b>/tema</b> — Selecciona una de las 6 Unidades Temáticas oficiales (~650 palabras).\n"
            "• <b>/nivel</b> — Elige tu nivel MCER (A1, A2, B1).\n"
            "• <b>/palabra &lt;término&gt;</b> — Consulta el significado, género o ejemplos de cualquier palabra.\n"
            "• <b>/idioma</b> — Alterna entre Alemán (de-DE) e Inglés (en-US).\n"
            "• <b>/libre &lt;frase&gt;</b> — Configura cualquier frase que desees pronunciar.\n"
            "• <b>/stats</b> — Muestra tu puntuación promedio y fonemas a mejorar.\n"
            "• <b>/web</b> — Enlace al panel web en tu PC."
        )
        await self._safe_reply_text(update.effective_message, help_text)

    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menú interactivo para cambiar Modalidad, Nivel MCER y Unidad Temática."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        current_skill = state.get("skill_mode", "speaking")
        current_level = state.get("level", "A1")
        active_unit = state.get("active_unit", "all")
        lang = state["language"]
        lang_flag = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"

        skill_labels = {
            "speaking": "🗣️ Hablar (Pronunciación IPA)",
            "writing": "✍️ Escribir (Gramática y Traducción)",
            "listening": "👂 Comprender (Audición y Vocabulario)",
            "conversation": "💬 Conversar (IA Roleplay guiado)",
        }

        unit_label = "🌐 Todas las Unidades"
        if active_unit != "all":
            u_obj = get_unit_by_id(active_unit, lang, current_level)
            if u_obj:
                unit_label = f"{u_obj.icon} U{u_obj.number}: {u_obj.title_es}"

        msg = (
            f"🎯 <b>Configuración de Entrenamiento</b>\n\n"
            f"• <b>Idioma:</b> {lang_flag}\n"
            f"• <b>Modalidad Actual:</b> {skill_labels.get(current_skill, current_skill)}\n"
            f"• <b>Nivel MCER:</b> {current_level}\n"
            f"• <b>Unidad Activa:</b> {unit_label}\n\n"
            f"👇 <b>Elige habilidad, nivel o selecciona una unidad temática:</b>"
        )

        unlocked = state.get("unlocked_levels", ["A1"])

        def get_lvl_label(lvl: str) -> str:
            if tracker.is_level_certified(user_id, lang, lvl):
                return f"🎓 {lvl} (Certificado)"
            elif lvl == current_level:
                return f"📍 {lvl} (En curso)"
            elif lvl in unlocked:
                return f"🔓 {lvl} (Desbloqueado)"
            else:
                return f"🔒 {lvl} (Bloqueado)"

        keyboard = [
            [
                InlineKeyboardButton("🗣️ Hablar", callback_data="mode_speaking"),
                InlineKeyboardButton("✍️ Escribir", callback_data="mode_writing"),
            ],
            [
                InlineKeyboardButton("👂 Comprender", callback_data="mode_listening"),
                InlineKeyboardButton("💬 Conversar (IA)", callback_data="mode_conversation"),
            ],
            [
                InlineKeyboardButton(get_lvl_label("A1"), callback_data="level_A1"),
                InlineKeyboardButton(get_lvl_label("A2"), callback_data="level_A2"),
                InlineKeyboardButton(get_lvl_label("B1"), callback_data="level_B1"),
            ],
            [
                InlineKeyboardButton(
                    f"📝 Rendir Evaluación Final {current_level}", callback_data="btn_exam_entry"
                ),
                InlineKeyboardButton("📂 Seleccionar Unidad", callback_data="btn_units_menu"),
            ],
            [
                InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
            ],
        ]
        await self._safe_reply_text(
            update.effective_message, msg, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_units(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el catálogo de Unidades Temáticas oficiales para el nivel actual."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        level = state.get("level", "A1")
        active_unit = state.get("active_unit", "all")
        units = get_curriculum_units(lang, level)

        lang_name = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"
        exam_name = (
            "Goethe-Zertifikat A1: Start Deutsch 1"
            if lang.startswith("de")
            else "Cambridge A1 Key"
        )

        msg = (
            f"📚 <b>Unidades Temáticas — {lang_name} [{level}]</b>\n"
            f"<i>Estándar oficial: {exam_name} (~650 palabras)</i>\n\n"
            f"👇 <b>Selecciona la Unidad que deseas entrenar:</b>"
        )

        buttons = []
        for u in units:
            prefix = "🔘 " if active_unit == u.id else ""
            btn_text = f"{prefix}{u.icon} U{u.number}: {u.title_es}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"unit_sel_{u.id}")])

        prefix_all = "🔘 " if active_unit == "all" else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{prefix_all}🌐 Todas las Unidades", callback_data="unit_sel_all"
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise"),
                InlineKeyboardButton("🎯 Modo y Nivel", callback_data="btn_mode_menu"),
            ]
        )
        await self._safe_reply_text(
            update.effective_message, msg, reply_markup=InlineKeyboardMarkup(buttons)
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
        state = tracker.get_user_state(user_id)
        if state.get("skill_mode") == "conversation":
            tracker.set_user_skill_mode(user_id, "speaking")
        tracker.set_fsm_state(user_id, "IN_EXERCISE")
        await self._send_exercise_card(update, user_id)

    async def _send_level_completed_card(
        self,
        update: Update,
        user_id: str,
        info: Dict[str, Any],
        edit_message: bool = False,
    ):
        """Muestra la tarjeta de culminación de serie y orienta a la evaluación o a temas pendientes."""
        state = tracker.get_user_state(user_id)
        lang = info.get("language") or state["language"]
        level = info.get("level") or state.get("level", "A1")
        skill = info.get("skill_mode") or state.get("skill_mode", "speaking")
        next_level = "A2" if level == "A1" else ("B1" if level == "A2" else None)

        unlocked = state.get("unlocked_levels", ["A1"])
        req = tracker.can_take_final_exam(user_id, lang, level)

        lang_name = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"
        skill_names = {
            "speaking": "🗣️ Hablar",
            "writing": "✍️ Escribir",
            "listening": "👂 Comprender",
        }
        skill_name = skill_names.get(skill, skill)

        lines = [
            "🏆 <b>¡SERIE DE EJERCICIOS COMPLETADA!</b> 🏆\n",
            f"Has completado la serie de <b>{skill_name}</b> en nivel <b>{level}</b> ({lang_name}).",
            "🎉 <i>Tus ejercicios han sido registrados en tu historial.</i>\n",
        ]

        is_certified = tracker.is_level_certified(user_id, lang, level)
        keyboard = []
        if is_certified and next_level in unlocked:
            lines.append(f"🚀 <b>¡Ya tienes certificado y desbloqueado el Nivel {next_level}!</b>")
            keyboard.append([
                InlineKeyboardButton(f"🚀 Ir a Nivel {next_level}", callback_data=f"fsm_ascend_{next_level}")
            ])
            keyboard.append([
                InlineKeyboardButton(f"🔄 Reintentar Evaluación {level}", callback_data=f"exam_start_{level}")
            ])
        else:
            lines.append("🎓 <b>Evaluación Final Oficial:</b>")
            lines.append(
                f"Para certificar formalmente tus conocimientos y desbloquear el Nivel {next_level}, rinde la Evaluación Final:"
            )
            keyboard.append([
                InlineKeyboardButton(f"📝 Rendir Evaluación Final {level}", callback_data=f"exam_start_{level}")
            ])
            if not req["can_take"]:
                lines.append(
                    f"📊 <i>Progreso de Temas: {req['completed_count']} / {req['total_units']} unidades aprobadas.</i>"
                )
                keyboard.append([
                    InlineKeyboardButton("📂 Ver Temas Pendientes", callback_data="btn_units_menu")
                ])

        keyboard.extend([
            [
                InlineKeyboardButton("🔄 Repasar este Nivel", callback_data=f"fsm_review_{level}"),
                InlineKeyboardButton("🎯 Cambiar Habilidad", callback_data="btn_mode_menu"),
            ],
            [
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
            ],
        ])

        msg_text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, msg_text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)
        else:
            await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)

    async def _send_ready_for_exam_card(
        self,
        update: Update,
        user_id: str,
        info: Dict[str, Any],
        edit_message: bool = False,
    ):
        """Muestra la tarjeta de habilitación de examen al culminar las 6 unidades temáticas oficiales."""
        state = tracker.get_user_state(user_id)
        lang = info.get("language") or state["language"]
        level = info.get("level") or state.get("level", "A1")
        next_level = info.get("next_level") or ("A2" if level == "A1" else ("B1" if level == "A2" else None))
        lang_name = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"
        exam_name = "Goethe Start Deutsch 1" if lang.startswith("de") else "Cambridge A1 Key"

        lines = [
            f"🎓 <b>¡HAS COMPLETADO LOS 6 TEMAS DE NIVEL {level}!</b> 🎓\n",
            f"Has cubierto con éxito todas las 6 Unidades Temáticas oficiales de <b>{level}</b> ({lang_name}).",
            "<i>Inventario cubierto: ~650 palabras de alta frecuencia.</i>\n",
            "🛡️ <b>Requisito de Certificación de Nivel:</b>",
            f"Para certificar tus conocimientos y desbloquear formalmente el <b>Nivel {next_level}</b>, debes aprobar la <b>Evaluación Final Oficial {level}</b> ({exam_name}).\n",
            "📋 <b>Estructura de la Evaluación:</b>",
            "• Comprensión Auditiva (Hören) con audio nativo",
            "• Comprensión de Lectura (Lesen)",
            "• Estructura y Gramática clave",
            "• Expresión Escrita (Schreiben)",
            "• Pronunciación y Fluidez (Sprechen)\n",
            "Nota mínima de aprobación: <b>75%</b>.",
        ]

        keyboard = [
            [
                InlineKeyboardButton(f"📝 Iniciar Evaluación Final {level}", callback_data=f"exam_start_{level}")
            ],
            [
                InlineKeyboardButton("🔄 Repasar Unidades", callback_data="btn_units_menu"),
                InlineKeyboardButton("🎯 Cambiar Modo", callback_data="btn_mode_menu"),
            ],
            [
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
            ],
        ]

        msg_text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, msg_text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)
        else:
            await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)

    async def cmd_exam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia o verifica el estado de la Evaluación Final de Nivel oficial."""
        user_id = f"tg_{update.effective_user.id}"
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        level = state.get("level", "A1")
        lang_name = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"
        exam_name = "Goethe Start Deutsch 1" if lang.startswith("de") else "Cambridge A1 Key"

        is_certified = tracker.is_level_certified(user_id, lang, level)
        req = tracker.can_take_final_exam(user_id, lang, level)

        if is_certified:
            next_lvl = "A2" if level == "A1" else ("B1" if level == "A2" else None)
            msg = (
                f"🎓 <b>NIVEL {level} CERTIFICADO CON ÉXITO ({lang_name})</b>\n\n"
                f"¡Ya has aprobado oficialmente la Evaluación de Nivel {level} ({exam_name})!\n\n"
                f"Puedes comenzar a entrenar el siguiente nivel o reintentar el examen para mejorar tu calificación."
            )
            buttons = []
            if next_lvl:
                buttons.append([InlineKeyboardButton(f"🚀 Ir a Nivel {next_lvl}", callback_data=f"fsm_ascend_{next_lvl}")])
            buttons.append([InlineKeyboardButton(f"🔄 Reintentar Evaluación {level}", callback_data=f"exam_start_{level}")])
            buttons.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu")])
            await self._safe_reply_text(update.effective_message, msg, reply_markup=InlineKeyboardMarkup(buttons))
            return

        if not req["can_take"]:
            msg = (
                f"📝 <b>EVALUACIÓN OFICIAL DE NIVEL {level} ({lang_name})</b>\n"
                f"<i>Estándar oficial: {exam_name} (Aprobación mínima: 75%)</i>\n\n"
                f"📊 <b>Progreso Curricular:</b> <b>{req['completed_count']} de {req['total_units']}</b> unidades completadas.\n"
                f"• Temas pendientes: <i>{', '.join(req['missing_units'])}</i>\n\n"
                f"💡 <b>Recomendación Pedagógica:</b> Se aconseja completar todas las unidades antes del examen. "
                f"Sin embargo, si posees conocimientos previos y deseas medir tu nivel o certificarlo por suficiencia, "
                f"puedes rendir la evaluación ahora mismo."
            )
            keyboard = [
                [InlineKeyboardButton(f"📝 Rendir Evaluación {level} Ahora", callback_data=f"exam_start_{level}")],
                [InlineKeyboardButton("📂 Practicar Temas Pendientes", callback_data="btn_units_menu")],
                [InlineKeyboardButton("📚 Ir al Ejercicio", callback_data="btn_exercise")],
            ]
            await self._safe_reply_text(update.effective_message, msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        exam_session = tracker.start_final_exam(user_id, lang, level)
        if not exam_session:
            await self._safe_reply_text(update.effective_message, "⚠️ No se encontró examen disponible para este nivel.")
            return

        await self._send_exam_question_card(update, user_id, exam_session, edit_message=False)

    async def _send_exam_question_card(
        self,
        update: Update,
        user_id: str,
        exam_session: Dict[str, Any],
        edit_message: bool = False,
    ):
        q = exam_session.get("current_question")
        if not q:
            return

        q_idx = exam_session.get("current_index", 0) + 1
        total_q = exam_session.get("total_questions", 6)
        level = exam_session.get("level", "A1")

        bar = _make_progress_bar((q_idx / total_q) * 100.0)

        lines = [
            f"📝 <b>EVALUACIÓN FINAL DE NIVEL {level}</b>",
            f"<code>[{bar}]</code> Pregunta <b>{q_idx} de {total_q}</b> — <i>{q.section_name_es}</i>\n",
            f"🎯 <b>Consigna:</b> {q.prompt_es}\n",
        ]

        if q.context_text:
            lines.append(f"📖 <b>Texto de Lectura:</b>\n<i>\"{q.context_text}\"</i>\n")

        if q.question_text:
            lines.append(f"❓ <b>{q.question_text}</b>\n")

        keyboard = []

        if q.audio_text:
            keyboard.append([
                InlineKeyboardButton("🔊 Escuchar Audio", callback_data=f"exam_tts_{q.id}"),
                InlineKeyboardButton("🐢 Escuchar Lento", callback_data=f"exam_ttsslow_{q.id}"),
            ])

        if q.options:
            for idx, opt in enumerate(q.options):
                keyboard.append([
                    InlineKeyboardButton(f"{chr(65 + idx)}) {opt}", callback_data=f"exam_opt_{idx}")
                ])
        elif q.section == "schreiben":
            lines.append("✍️ <i>Escribe tu respuesta como mensaje de texto a continuación:</i>")
        elif q.section == "sprechen":
            lines.append(f"👉 Frase: <b>\"{q.target_answer}\"</b>\n🎙️ <i>Graba y envía una nota de voz pronunciando la frase indicada.</i>")

        keyboard.append([
            [InlineKeyboardButton("❌ Cancelar Examen", callback_data="exam_cancel")],
        ])

        msg_text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, msg_text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)
        else:
            await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)

    async def _send_exam_result_card(
        self,
        update: Update,
        user_id: str,
        result: Dict[str, Any],
        edit_message: bool = False,
    ):
        is_passed = result.get("is_passed", False)
        score = result.get("score_percent", 0.0)
        passing_score = result.get("passing_score", 75.0)
        level = result.get("level", "A1")
        next_level = result.get("next_level")

        if is_passed:
            lines = [
                f"🎓 <b>¡FELICITACIONES! HAS APROBADO LA EVALUACIÓN FINAL DE NIVEL {level}</b> 🎓\n",
                f"Puntuación obtenida: <b>{score:.1f}%</b> (Mínimo requerido: {passing_score:.0f}%)\n",
                "🏆 <b>Certificación Oficial Otorgada</b>",
                f"Has demostrado un dominio integral de las 6 unidades temáticas oficiales de {level}.\n",
            ]
            keyboard = []
            if next_level:
                lines.append(f"🚀 <b>¡Nivel {next_level} Desbloqueado con Éxito!</b>")
                lines.append(f"Ya puedes comenzar el programa curricular de Nivel {next_level}.")
                keyboard.append([
                    InlineKeyboardButton(f"🚀 Comenzar Nivel {next_level}", callback_data=f"fsm_ascend_{next_level}")
                ])
            keyboard.extend([
                [InlineKeyboardButton("📊 Ver Mis Estadísticas", callback_data="btn_stats")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu")],
            ])
        else:
            lines = [
                f"🟡 <b>RESULTADO DE LA EVALUACIÓN FINAL {level}</b>\n",
                f"Puntuación obtenida: <b>{score:.1f}%</b> (Mínimo para aprobar: {passing_score:.0f}%)\n",
                "Estuviste cerca, pero necesitas reforzar algunos conceptos antes de obtener la certificación.\n",
                "💡 <b>Recomendación Pedagógica:</b>",
                "Repasa las Unidades Temáticas con /temas y vuelve a intentar la evaluación cuando te sientas listo.",
            ]
            keyboard = [
                [InlineKeyboardButton(f"🔄 Reintentar Examen {level}", callback_data=f"exam_start_{level}")],
                [InlineKeyboardButton("📂 Repasar Unidades Temáticas", callback_data="btn_units_menu")],
                [InlineKeyboardButton("📚 Ir a Ejercicios", callback_data="btn_exercise")],
            ]

        msg_text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, msg_text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)
        else:
            await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)

    async def _send_unit_completed_card(
        self,
        update: Update,
        user_id: str,
        info: Dict[str, Any],
        edit_message: bool = False,
    ):
        """Muestra la tarjeta de unidad completada y guía al alumno hacia la siguiente unidad sin saltarse el nivel."""
        state = tracker.get_user_state(user_id)
        lang = info.get("language") or state["language"]
        level = info.get("level") or state.get("level", "A1")
        completed_unit = info.get("completed_unit", "unit_1")
        next_unit = info.get("next_unit")
        units_done = info.get("units_completed_count", 1)
        total_units = info.get("total_units", 6)

        u_info = get_unit_by_id(completed_unit, lang, level)
        u_title = f"{u_info.icon} {u_info.title_es}" if u_info else completed_unit

        next_u_info = get_unit_by_id(next_unit, lang, level) if next_unit else None
        next_title = f"{next_u_info.icon} {next_u_info.title_es}" if next_u_info else next_unit

        bar = _make_progress_bar((units_done / total_units) * 100.0)

        lines = [
            "🎉 <b>¡UNIDAD TEMÁTICA COMPLETADA!</b> 🎉\n",
            f"Has completado con éxito la unidad: <b>{u_title}</b>.",
            f"📊 <b>Progreso de Unidades en Nivel {level}:</b>\n",
            f"• <code>[{bar}]</code> <b>{units_done} / {total_units}</b> unidades aprobadas ({int((units_done / total_units) * 100)}%)\n",
        ]

        keyboard = []
        if next_unit:
            lines.append(f"👉 <b>Siguiente Unidad:</b> {next_title}")
            lines.append("<i>Para graduarte de A1 debes completar las 6 unidades temáticas oficiales.</i>")
            keyboard.append([
                InlineKeyboardButton(f"➡️ Pasar a: {next_title}", callback_data=f"fsm_next_unit_{next_unit}")
            ])
        else:
            lines.append("🌟 <b>¡Has cubierto todas las unidades de este nivel!</b>")

        keyboard.extend([
            [
                InlineKeyboardButton("🔄 Repasar esta Unidad", callback_data=f"unit_sel_{completed_unit}"),
                InlineKeyboardButton("📂 Ver Todas las Unidades", callback_data="btn_units_menu"),
            ],
            [
                InlineKeyboardButton("🎯 Cambiar Modo (Escribir/Escuchar)", callback_data="btn_mode_menu"),
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
            ],
        ])

        msg_text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard)
        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, msg_text, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)
        else:
            await self._safe_send_chat_message(update.effective_chat, msg_text, reply_markup=reply_markup)

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra confirmación para reiniciar progreso a cero."""
        msg = (
            "⚠️ <b>¿Deseas reiniciar tu progreso pedagógico?</b>\n\n"
            "Esta acción restablecerá tu nivel a <b>A1 inicial</b>, desmarcará unidades y ejercicios completados "
            "y te permitirá comenzar de cero con todas las evaluaciones disponibles."
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 Sí, Reiniciar a Cero", callback_data="btn_reset_confirm"),
                InlineKeyboardButton("❌ Cancelar", callback_data="btn_start_menu"),
            ]
        ]
        await self._safe_reply_text(
            update.effective_message, msg, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia o retoma una misión de conversación interactiva (roleplay con IA)."""
        user_id = f"tg_{update.effective_user.id}"
        tracker.set_user_skill_mode(user_id, "conversation")
        await self._send_conversation_mission_card(update, user_id)

    async def _send_conversation_mission_card(
        self,
        update: Update,
        user_id: str,
        edit_message: bool = False,
    ):
        """Muestra la tarjeta de misión de roleplay conversacional para la unidad activa."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        level = state.get("level", "A1")
        active_unit = state.get("active_unit", "all")

        scenarios = get_scenarios_for_unit(active_unit, lang, level)
        if not scenarios:
            scenarios = get_curriculum_scenarios(lang, level)
        scen = scenarios[0]

        # Verificar si ya hay una conversación activa para este usuario
        active_conv = tracker.get_active_conversation(user_id)
        if not active_conv or active_conv.get("scenario_id") != scen.id:
            active_conv = tracker.start_conversation(
                user_id=user_id,
                language=lang,
                level=level,
                unit_id=scen.unit_id,
                scenario_id=scen.id,
                scenario_title=scen.title,
                mission_brief=scen.mission_brief,
                character_name=scen.character_name,
                initial_greeting=scen.initial_greeting,
                initial_greeting_es=scen.initial_greeting_es,
            )

        turns = active_conv.get("turns", [])
        last_turn = (
            turns[-1]
            if turns
            else {
                "name": scen.character_name,
                "text": scen.initial_greeting,
                "text_es": scen.initial_greeting_es,
            }
        )

        # Frases de apoyo sugeridas
        hints = [f"• <i>{p}</i>" for p in scen.target_phrases[:3]]
        hints_str = "\n".join(hints)

        # Diálogo reciente (últimos 4 turnos)
        dialogue_preview = []
        for t in turns[-4:]:
            icon = "👤" if t.get("role") == "character" else "🎓"
            dialogue_preview.append(f"{icon} <b>{t.get('name')}:</b> {t.get('text')}")
        dialogue_text = "\n".join(dialogue_preview)

        spoiler_es = (
            f"<tg-spoiler><i>🇪🇸 {last_turn.get('text_es', '')}</i></tg-spoiler>"
            if last_turn.get("text_es")
            else ""
        )

        lang_badge = "🇩🇪 ALEMÁN" if lang.startswith("de") else "🇺🇸 INGLÉS"
        u_info = get_unit_by_id(scen.unit_id, lang, level)
        u_badge = f" · {u_info.icon} U{u_info.number}" if u_info else ""

        card = (
            f"🎭 <b>{lang_badge} [{level}{u_badge}] — Misión de Conversación</b>\n"
            f"<b>Escenario:</b> {scen.title}\n"
            f"👤 <b>Interlocutor:</b> {scen.character_name} (<i>{scen.character_role}</i>)\n"
            f"🎯 <b>Tu Misión:</b> {scen.mission_brief}\n\n"
            f"💡 <b>Frases de apoyo sugeridas:</b>\n{hints_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 <b>Diálogo en curso:</b>\n"
            f"{dialogue_text}\n"
            f"{spoiler_es}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎙️ Envía una <b>nota de voz</b> o responde por <b>texto</b> para continuar."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Escuchar al Personaje", callback_data=f"conv_tts_{scen.id}"
                ),
                InlineKeyboardButton(
                    "🐢 Escuchar Lento", callback_data=f"conv_tts_slow_{scen.id}"
                ),
            ],
            [
                InlineKeyboardButton("🏁 Finalizar Misión", callback_data="conv_finish"),
                InlineKeyboardButton("🔄 Reiniciar Misión", callback_data="conv_restart"),
            ],
            [
                InlineKeyboardButton("📂 Cambiar Unidad", callback_data="btn_units_menu"),
                InlineKeyboardButton("🎯 Cambiar Modo", callback_data="btn_mode_menu"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_message and update.callback_query:
            try:
                await self._safe_edit_text(update.callback_query, card, reply_markup=reply_markup)
            except Exception:
                await self._safe_send_chat_message(
                    update.effective_chat, card, reply_markup=reply_markup
                )
        else:
            await self._safe_send_chat_message(
                update.effective_chat, card, reply_markup=reply_markup
            )

    async def _handle_conversation_turn(
        self,
        update: Update,
        user_id: str,
        user_text: str,
        is_audio: bool = False,
        status_msg: Optional[Any] = None,
    ):
        """Procesa una intervención del alumno en el diálogo de roleplay."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        level = state.get("level", "A1")
        active_conv = tracker.get_active_conversation(user_id)
        if not active_conv:
            await self._send_conversation_mission_card(update, user_id)
            return

        scenario_id = active_conv["scenario_id"]
        scen = get_scenario_by_id(scenario_id, lang, level)
        if not scen:
            scenarios = get_curriculum_scenarios(lang, level)
            scen = scenarios[0]

        # 1. Registrar turno del alumno
        tracker.append_conversation_turn(
            user_id=user_id,
            role="user",
            text=user_text,
            name="Alumno",
        )

        # 2. Registrar palabras del vocabulario A1 dominadas por el alumno
        words = extract_words_from_text(user_text)
        tracker.record_mastered_words(user_id, lang, words, level=level)

        # 3. Consultar respuesta a Gemini Coach
        await update.effective_message.reply_chat_action(ChatAction.TYPING)
        active_conv = tracker.get_active_conversation(user_id)
        dialogue_history = active_conv.get("turns", [])

        reply_data = gemini_coach.generate_conversation_reply(
            scenario_title=scen.title,
            character_name=scen.character_name,
            character_role=scen.character_role,
            mission_brief=scen.mission_brief,
            target_phrases=scen.target_phrases,
            dialogue_history=dialogue_history,
            user_message=user_text,
            language=lang,
        )

        # 4. Registrar turno del personaje
        char_reply = reply_data.get("reply_native", "")
        char_es = reply_data.get("reply_es", "")
        tracker.append_conversation_turn(
            user_id=user_id,
            role="character",
            text=char_reply,
            text_es=char_es,
            name=scen.character_name,
        )

        # 5. Formatear la réplica
        feedback_tip = reply_data.get("feedback_tip")
        tip_str = f"\n💡 <i>Consejo: {feedback_tip}</i>\n" if feedback_tip else ""

        user_turn_count = sum(1 for t in dialogue_history if t.get("role") == "user") + 1

        user_header = f'🗣️ <b>Tú:</b> <i>"{user_text}"</i>\n\n' if is_audio else ""
        msg = (
            user_header
            + f"👤 <b>{scen.character_name}:</b>\n"
            f'"{char_reply}"\n'
            f"<tg-spoiler><i>🇪🇸 {char_es}</i></tg-spoiler>\n"
            f"{tip_str}\n"
            f"<i>(Intercambio {user_turn_count})</i>"
        )

        is_goal_achieved = reply_data.get("mission_status") == "goal_achieved"

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Escuchar al Personaje",
                    callback_data=f"conv_tts_rep_{user_turn_count}",
                ),
                InlineKeyboardButton(
                    "🐢 Escuchar Lento",
                    callback_data=f"conv_tts_slowrep_{user_turn_count}",
                ),
            ],
        ]

        if is_goal_achieved:
            msg += (
                "\n\n🎉 <b>¡Objetivo de la misión cumplido!</b>\n"
                "<i>Has completado la meta pedagógica. Puedes ver tu evaluación o seguir charlando libremente:</i>"
            )
            keyboard.append([
                InlineKeyboardButton("🏆 Ver Informe y Evaluación", callback_data="conv_finish"),
                InlineKeyboardButton("🔄 Reiniciar Escenario", callback_data="conv_restart"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🏁 Finalizar Misión", callback_data="conv_finish"),
                InlineKeyboardButton("🔄 Reiniciar", callback_data="conv_restart"),
            ])

        keyboard.append([
            InlineKeyboardButton("🎯 Cambiar Modo", callback_data="btn_mode_menu"),
        ])

        if status_msg is not None:
            edited = await self._safe_edit_text(
                status_msg,
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            if not edited:
                await self._safe_reply_text(
                    update.effective_message,
                    msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        else:
            await self._safe_reply_text(
                update.effective_message,
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    async def _finish_conversation_mission(
        self,
        update: Update,
        user_id: str,
        scen: Optional[ScenarioInfo] = None,
    ):
        """Concluye formalmente la conversación, guarda estadísticas y muestra el debriefing con FSM."""
        active_conv = tracker.get_active_conversation(user_id)
        if not active_conv:
            await self._safe_reply_text(
                update.effective_message,
                "ℹ️ No hay ninguna misión de conversación activa en este momento.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🎭 Nueva Misión", callback_data="mode_conversation"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "📚 Ir a Ejercicios", callback_data="btn_exercise"
                            )
                        ],
                    ]
                ),
            )
            return

        state = tracker.get_user_state(user_id)
        lang = state["language"]
        level = state.get("level", "A1")

        if not scen:
            scen = get_scenario_by_id(active_conv["scenario_id"], lang, level)
            if not scen:
                scenarios = get_curriculum_scenarios(lang, level)
                scen = scenarios[0]

        dialogue_history = active_conv.get("turns", [])
        tracker.complete_conversation(user_id)

        await update.effective_message.reply_chat_action(ChatAction.TYPING)
        debrief = gemini_coach.generate_conversation_debrief(
            scenario_title=scen.title,
            character_name=scen.character_name,
            mission_brief=scen.mission_brief,
            dialogue_history=dialogue_history,
            language=lang,
        )

        score = debrief.get("score", 85.0)
        badge = (
            "🏆 <b>¡MISIÓN CUMPLIDA CON ÉXITO!</b> 🏆"
            if debrief.get("passed", True)
            else "🟡 <b>MISIÓN FINALIZADA</b>"
        )
        summary = debrief.get("summary", "")
        tips = debrief.get("tips", "")

        strengths = debrief.get("strengths", [])
        str_lines = (
            "\n".join([f"• ✅ {s}" for s in strengths])
            if strengths
            else "• Buena participación"
        )

        areas = debrief.get("areas_to_improve", [])
        area_lines = (
            "\n".join([f"• 🎯 {a}" for a in areas])
            if areas
            else "• Continuar practicando"
        )

        msg = (
            f"{badge}\n\n"
            f"<b>Escenario:</b> {scen.title}\n"
            f"<b>Puntuación de Desempeño:</b> <code>{score:.0f}/100</code>\n\n"
            f"📝 <b>Evaluación Pedagógica:</b>\n{summary}\n\n"
            f"💪 <b>Puntos Fuertes:</b>\n{str_lines}\n\n"
            f"🌱 <b>Para Seguir Mejorando:</b>\n{area_lines}\n\n"
            f"💡 <b>Consejo del Tutor:</b>\n<i>{tips}</i>"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔄 Repetir Misión", callback_data="conv_restart"),
                InlineKeyboardButton(
                    "🎭 Siguiente Escenario", callback_data="conv_next_scenario"
                ),
            ],
            [
                InlineKeyboardButton("📚 Ir a Ejercicios", callback_data="btn_exercise"),
                InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
            ],
        ]

        if update.callback_query:
            try:
                await self._safe_edit_text(
                    update.callback_query, msg, reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                await self._safe_send_chat_message(
                    update.effective_chat, msg, reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await self._safe_reply_text(
                update.effective_message, msg, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def _send_conversation_tts(self, query, user_id: str, slow: bool = False):
        """Sintetiza la réplica más reciente del personaje de conversación y la envía como audio."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        active_conv = tracker.get_active_conversation(user_id)
        if not active_conv:
            await query.message.reply_text("⚠️ No hay misión de conversación activa.")
            return

        turns = active_conv.get("turns", [])
        char_turns = [t for t in turns if t.get("role") == "character"]
        text_to_speak = (
            char_turns[-1].get("text")
            if char_turns
            else active_conv.get("initial_greeting", "Hallo")
        )

        wav_bytes = azure_service.text_to_speech(text=text_to_speak, language=lang, slow=slow)
        if not wav_bytes:
            await query.message.reply_text("⚠️ No se pudo generar el audio nativo de referencia.")
            return

        ogg_bytes = audio_converter.wav_to_ogg_opus(wav_bytes)
        audio_stream = io.BytesIO(ogg_bytes if ogg_bytes else wav_bytes)
        audio_stream.name = "dialogo_lento.ogg" if slow else "dialogo_nativo.ogg"

        caption_flag = "🇩🇪" if lang.startswith("de") else "🇺🇸"
        icon = "🐢" if slow else "🔊"
        label = (
            f"{icon} <b>Interlocutor ({active_conv.get('character_name', 'Personaje')} - 0.8x {caption_flag}):</b>"
            if slow
            else f"{icon} <b>Interlocutor ({active_conv.get('character_name', 'Personaje')} - {caption_flag}):</b>"
        )
        await query.message.reply_voice(
            voice=audio_stream,
            caption=f'{label}\n"{text_to_speak}"',
            parse_mode=ParseMode.HTML,
        )

    async def _send_exercise_card(self, update: Update, user_id: str, edit_message: bool = False):
        """Envía o actualiza la tarjeta del ejercicio según la modalidad activa (Hablar, Escribir, Comprender, Conversar)."""
        state = tracker.get_user_state(user_id)
        lang = state["language"]
        skill_mode = state.get("skill_mode", "speaking")
        level = state.get("level", "A1")
        active_unit = state.get("active_unit", "all")

        if skill_mode == "conversation":
            await self._send_conversation_mission_card(update, user_id, edit_message=edit_message)
            return

        exercises = get_exercises(
            language=lang, level=level, skill_type=skill_mode, unit_id=active_unit
        )
        if not exercises:
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

        fsm_state = state.get("fsm_state", "IN_EXERCISE")
        idx = state.get("exercise_index", 0)

        # Si el índice quedó fuera de rango por cambio de unidad o filtro, resetear a 0
        if idx >= len(exercises):
            tracker.set_user_exercise_index(user_id, 0)
            idx = 0

        # Si el usuario ya completó el nivel o las 6 unidades según la FSM, mostrar tarjeta de graduación
        if fsm_state == "LEVEL_COMPLETED" or fsm_state == "READY_FOR_FINAL_EXAM":
            advance_info = {
                "language": lang,
                "level": level,
                "skill_mode": skill_mode,
                "next_level": "A2" if level == "A1" else ("B1" if level == "A2" else None),
            }
            await self._send_level_completed_card(
                update, user_id, advance_info, edit_message=edit_message
            )
            return

        ex = exercises[idx]

        tracker.set_user_custom_phrase(user_id, None)

        lang_header = "🇩🇪 ALEMÁN" if lang.startswith("de") else "🇺🇸 INGLÉS"
        u_info = get_unit_by_id(ex.unit_id or "unit_1", lang, level)
        u_badge = f" · {u_info.icon} U{u_info.number}" if u_info else ""

        if skill_mode == "writing":
            card_lines = [
                f"✍️ <b>{lang_header} — [{ex.level}{u_badge}] {ex.category}</b>",
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
                    InlineKeyboardButton("📂 Unidad", callback_data="btn_units_menu"),
                    InlineKeyboardButton("🎯 Modo/Nivel", callback_data="btn_mode_menu"),
                    InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                ],
            ]

        elif skill_mode == "listening":
            card_lines = [
                f"👂 <b>{lang_header} — [{ex.level}{u_badge}] {ex.category}</b>",
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
                        InlineKeyboardButton("📂 Unidad", callback_data="btn_units_menu"),
                        InlineKeyboardButton("🎯 Modo/Nivel", callback_data="btn_mode_menu"),
                        InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
                    ],
                ]
            )

        else:
            # Modo SPEAKING (Hablar)
            phonemes_str = " · ".join([f"<code>/{p}/</code>" for p in ex.focus_phonemes])
            card_lines = [
                f"🗣️ <b>{lang_header} — [{ex.level}{u_badge}] {ex.category}</b>",
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
                    InlineKeyboardButton("📂 Unidad", callback_data="btn_units_menu"),
                    InlineKeyboardButton("🎯 Modo/Nivel", callback_data="btn_mode_menu"),
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
        user_state = tracker.get_user_state(user_id)
        lang = user_state["language"]
        level = user_state.get("level", "A1")
        exam_name = (
            "Goethe Start Deutsch 1"
            if lang.startswith("de")
            else "Cambridge A1 Key"
        )

        lex_prog = tracker.get_user_lexicon_progress(user_id, lang, level)
        mastered_cnt = lex_prog["mastered_count"]
        total_target = lex_prog["total_target"]
        lex_percent = lex_prog["percentage"]
        lex_bar = _make_progress_bar(lex_percent)

        completed_ex_cnt = len(user_state.get("completed_exercises", []))
        lex_section = (
            f"📚 <b>Inventario Léxico Oficial {level} ({exam_name}):</b>\n"
            f"• <code>[{lex_bar}]</code> <b>{mastered_cnt} / {total_target}</b> palabras dominadas ({lex_percent:.1f}%)\n"
            f"• <b>Ejercicios completados:</b> {completed_ex_cnt}\n"
            f"💡 <i>(La meta de suficiencia oficial {level} es de {total_target} palabras. Practica las 6 unidades con /temas para seguir sumando palabras)</i>\n\n"
        )

        if stats["total_attempts"] == 0:
            text = (
                f"📊 <b>Tus Estadísticas en tut_bot</b>\n\n"
                f"{lex_section}"
                "🗣️ <i>Aún no has realizado prácticas de fonética con notas de voz.</i>\n"
                "¡Usa /ejercicio y envía tu primer audio para comenzar tu registro acústico!"
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
                f"📊 <b>Tus Estadísticas en tut_bot</b>\n\n"
                f"{lex_section}"
                "🗣️ <b>Pronunciación y Fluidez:</b>\n"
                f"• <b>Intentos totales:</b> {stats['total_attempts']}\n"
                f"• <b>Precisión Media:</b> <code>[{acc_bar}]</code> {avg_acc:.0f}%\n"
                f"• <b>Fluidez Media:</b>   <code>[{flu_bar}]</code> {avg_flu:.0f}%\n\n"
                f"🎯 <b>Sonidos que más debes practicar:</b>\n{weak_str}"
            )

        keyboard = [
            [
                InlineKeyboardButton("📚 Ir a Ejercicios", callback_data="btn_exercise"),
                InlineKeyboardButton("📂 Unidades Temáticas", callback_data="btn_units_menu"),
            ],
            [
                InlineKeyboardButton("🎯 Modo y Nivel", callback_data="btn_mode_menu"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
            ],
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
            state = tracker.get_user_state(user_id)
            if state.get("skill_mode") == "conversation":
                tracker.set_user_skill_mode(user_id, "speaking")
            tracker.set_fsm_state(user_id, "IN_EXERCISE")
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

        elif data == "btn_units_menu":
            await self.cmd_units(update, context)

        elif data.startswith("unit_sel_") or data.startswith("unit_"):
            raw = (
                data[len("unit_sel_") :]
                if data.startswith("unit_sel_")
                else data[len("unit_") :]
            )
            if raw.startswith("sel_"):
                raw = raw[len("sel_") :]
            if raw.isdigit():
                new_unit = f"unit_{raw}"
            elif raw == "all":
                new_unit = "all"
            elif raw.startswith("unit_"):
                new_unit = raw
            else:
                new_unit = f"unit_{raw}"

            tracker.set_user_unit(user_id, new_unit)
            state = tracker.get_user_state(user_id)
            if new_unit == "all":
                unit_desc = "Todas las Unidades"
            else:
                u_obj = get_unit_by_id(new_unit, state["language"], state.get("level", "A1"))
                unit_desc = f"{u_obj.icon} {u_obj.title_es}" if u_obj else new_unit
            await self._safe_edit_text(
                query, f"✅ Unidad Temática seleccionada: <b>{unit_desc}</b>."
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data.startswith("mode_"):
            new_mode = data.replace("mode_", "")
            tracker.set_user_skill_mode(user_id, new_mode)
            skill_names = {
                "speaking": "🗣️ Hablar (Pronunciación)",
                "writing": "✍️ Escribir (Gramática y Traducción)",
                "listening": "👂 Comprender (Audición y Vocabulario)",
                "conversation": "💬 Conversar (IA Roleplay)",
            }
            await self._safe_edit_text(
                query,
                f"✅ Modo de entrenamiento cambiado a: <b>{skill_names.get(new_mode, new_mode)}</b>.",
            )
            if new_mode == "conversation":
                await self._send_conversation_mission_card(update, user_id, edit_message=False)
            else:
                tracker.set_fsm_state(user_id, "IN_EXERCISE")
                await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "conv_finish":
            await self._finish_conversation_mission(update, user_id)

        elif data == "conv_restart":
            tracker.cancel_conversation(user_id)
            await self._safe_edit_text(query, "🔄 <b>Reiniciando misión conversacional...</b>")
            await self._send_conversation_mission_card(update, user_id, edit_message=False)

        elif data == "conv_next_scenario":
            tracker.cancel_conversation(user_id)
            state = tracker.get_user_state(user_id)
            units = get_curriculum_units(state["language"], state.get("level", "A1"))
            curr_u = state.get("active_unit", "all")
            next_u = "unit_1"
            for idx, u in enumerate(units):
                if u.id == curr_u:
                    next_u = units[(idx + 1) % len(units)].id
                    break
            tracker.set_user_unit(user_id, next_u)
            await self._send_conversation_mission_card(update, user_id, edit_message=False)

        elif data.startswith("conv_tts_"):
            slow = "slow" in data
            await self._send_conversation_tts(query, user_id, slow=slow)

        elif data.startswith("level_"):
            new_level = data.replace("level_", "")
            state = tracker.get_user_state(user_id)
            unlocked = state.get("unlocked_levels", ["A1"])
            if new_level not in unlocked:
                # Explicar claramente los requisitos
                exam_req = tracker.can_take_final_exam(user_id, state["language"], "A1")
                if not exam_req["can_take"]:
                    await query.answer(
                        f"🔒 Nivel {new_level} bloqueado: Completa las 6 unidades de A1 (llevas {exam_req['completed_count']}/6) para habilitar el examen.",
                        show_alert=True,
                    )
                else:
                    await query.answer(
                        f"🔒 Nivel {new_level} bloqueado: Has completado las 6 unidades de A1, pero debes aprobar la Evaluación Final para certificar y desbloquear {new_level}.",
                        show_alert=True,
                    )
                return
            success = tracker.set_user_level(user_id, new_level)
            if success:
                await self._safe_edit_text(
                    query, f"✅ Nivel de dificultad cambiado a: <b>{new_level}</b>."
                )
                await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "btn_exam_entry":
            await self.cmd_exam(update, context)

        elif data == "btn_reset_ask":
            await self.cmd_reset(update, context)

        elif data == "btn_reset_confirm":
            state = tracker.get_user_state(user_id)
            tracker.reset_user_progress(user_id, state["language"])
            msg = (
                "🔄 <b>¡Progreso reiniciado con éxito!</b>\n\n"
                "• Nivel: <b>A1</b>\n"
                "• Unidades completadas: <b>0 / 6</b>\n"
                "• Habilidad: <b>Hablar</b>\n\n"
                "Comienza tus ejercicios desde la Unidad 1 o rinde la Evaluación de Nivelación cuando desees."
            )
            keyboard = [
                [
                    InlineKeyboardButton("📚 Ir al Ejercicio 1", callback_data="btn_exercise"),
                    InlineKeyboardButton("📝 Evaluación Final A1", callback_data="btn_exam_entry"),
                ],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu")],
            ]
            await self._safe_edit_text(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("exam_start_"):
            target_lvl = data.replace("exam_start_", "")
            exam_session = tracker.start_final_exam(user_id, state["language"], target_lvl)
            if exam_session:
                await self._send_exam_question_card(update, user_id, exam_session, edit_message=True)
            else:
                await query.answer("No se encontró examen para este nivel.", show_alert=True)

        elif data.startswith("exam_opt_"):
            opt_idx = int(data.replace("exam_opt_", ""))
            active_exam = tracker.get_active_final_exam(user_id)
            if not active_exam:
                await query.answer("No hay examen activo.", show_alert=True)
                return
            exam_obj = get_level_exam(active_exam["language"], active_exam["level"])
            if not exam_obj:
                return
            curr_q_idx = active_exam["current_question_index"]
            q = exam_obj.questions[curr_q_idx]

            is_correct = (opt_idx == q.correct_option_index)
            score_pts = float(q.points) if is_correct else 0.0
            user_ans = q.options[opt_idx] if opt_idx < len(q.options) else str(opt_idx)

            res = tracker.submit_exam_answer(
                user_id=user_id,
                question_id=q.id,
                section=q.section,
                user_answer=user_ans,
                is_correct=is_correct,
                score_points=score_pts,
                explanation=q.explanation_es,
            )

            feedback_icon = "✅ Correcto" if is_correct else "❌ Incorrecto"
            await query.answer(f"{feedback_icon}: {q.explanation_es}", show_alert=True)

            if res.get("status") == "next_question":
                active_session = {
                    "level": active_exam["level"],
                    "language": active_exam["language"],
                    "total_questions": len(exam_obj.questions),
                    "current_index": res["current_index"],
                    "current_question": res["current_question"],
                }
                await self._send_exam_question_card(update, user_id, active_session, edit_message=True)
            elif res.get("status") == "exam_completed":
                await self._send_exam_result_card(update, user_id, res, edit_message=True)

        elif data.startswith("exam_tts_") or data.startswith("exam_ttsslow_"):
            slow = "slow" in data
            raw_id = data.replace("exam_ttsslow_", "").replace("exam_tts_", "")
            active_exam = tracker.get_active_final_exam(user_id)
            if active_exam:
                exam_obj = get_level_exam(active_exam["language"], active_exam["level"])
                q = next((item for item in exam_obj.questions if item.id == raw_id), None) if exam_obj else None
                if q and q.audio_text:
                    wav_bytes = azure_service.text_to_speech(text=q.audio_text, language=active_exam["language"], slow=slow)
                    if wav_bytes:
                        ogg_bytes = audio_converter.wav_to_ogg_opus(wav_bytes)
                        stream = io.BytesIO(ogg_bytes if ogg_bytes else wav_bytes)
                        stream.name = "audio_examen.ogg"
                        await query.message.reply_voice(
                            voice=stream,
                            caption=f"🎧 Audio de Examen ({'0.8x' if slow else '1.0x'})",
                        )

        elif data == "exam_cancel":
            tracker.cancel_final_exam(user_id)
            await self._safe_edit_text(query, "❌ Evaluación final cancelada. Regresando a tus ejercicios.")
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data.startswith("fsm_review_"):
            target_level = data.replace("fsm_review_", "")
            tracker.set_user_level(user_id, target_level)
            tracker.set_user_exercise_index(user_id, 0)
            tracker.set_fsm_state(user_id, "IN_EXERCISE")
            await self._safe_edit_text(
                query,
                f"🔄 <b>Reiniciando repaso del nivel {target_level}...</b>\n¡A darlo todo!",
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "vocab_card":
            state = tracker.get_user_state(user_id)
            skill_mode = state.get("skill_mode", "speaking")
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=skill_mode,
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            idx = state["exercise_index"] % len(exercises)
            ex = exercises[idx]

            if skill_mode == "listening":
                lines = [
                    f"📖 <b>Vocabulario de apoyo [{ex.level}]:</b>\n",
                    "🔑 <i>Palabras de apoyo para agudizar el oído sin revelar la solución:</i>\n",
                ]
                if ex.vocabulary_breakdown:
                    for w, mean in ex.vocabulary_breakdown.items():
                        lines.append(f"• <b>{w}</b>: {mean}")
                if ex.grammar_note:
                    lines.append(f"\n💡 <b>Pista gramatical:</b> <i>{ex.grammar_note}</i>")
                vocab_msg = "\n".join(lines)
            elif ex.vocabulary_breakdown:
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
            active_unit = state.get("active_unit", "all")
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type="listening",
                unit_id=active_unit,
            )
            if not exercises:
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
                tracker.mark_exercise_completed(user_id, ex.id)
                words = extract_words_from_text(ex.target_text)
                if ex.vocabulary_breakdown:
                    words.extend(list(ex.vocabulary_breakdown.keys()))
                tracker.record_mastered_words(
                    user_id, state["language"], words, level=state.get("level", "A1")
                )
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
            active_unit = state.get("active_unit", "all")
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
                unit_id=active_unit,
            )
            if not exercises:
                exercises = get_exercises(language=state["language"])

            advance_info = tracker.advance_exercise_fsm(
                user_id, len(exercises), current_unit_id=active_unit, require_all_units=True
            )
            if advance_info["status"] == "next_exercise":
                await self._send_exercise_card(update, user_id, edit_message=True)
            elif advance_info["status"] == "unit_completed":
                await self._send_unit_completed_card(
                    update, user_id, advance_info, edit_message=True
                )
            elif advance_info["status"] == "ready_for_final_exam":
                await self._send_ready_for_exam_card(
                    update, user_id, advance_info, edit_message=True
                )
            else:
                await self._send_level_completed_card(
                    update, user_id, advance_info, edit_message=True
                )

        elif data.startswith("fsm_next_unit_"):
            next_unit = data.replace("fsm_next_unit_", "")
            tracker.set_user_unit(user_id, next_unit)
            await self._safe_edit_text(
                query,
                f"🚀 <b>Iniciando {next_unit}...</b>\n¡Cargando tus nuevos ejercicios!",
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

        elif data == "ex_prev":
            state = tracker.get_user_state(user_id)
            active_unit = state.get("active_unit", "all")
            exercises = get_exercises(
                language=state["language"],
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
                unit_id=active_unit,
            )
            if not exercises:
                exercises = get_exercises(
                    language=state["language"],
                    level=state.get("level", "A1"),
                    skill_type=state.get("skill_mode", "speaking"),
                )
            if not exercises:
                exercises = get_exercises(language=state["language"])
            prev_idx = max(0, state["exercise_index"] - 1)
            tracker.set_user_exercise_index(user_id, prev_idx)
            tracker.set_fsm_state(user_id, "IN_EXERCISE")
            await self._send_exercise_card(update, user_id, edit_message=True)

        elif data.startswith("fsm_ascend_"):
            target_level = data.replace("fsm_ascend_", "")
            state = tracker.get_user_state(user_id)
            unlocked = state.get("unlocked_levels", ["A1"])
            if target_level not in unlocked:
                await query.answer(
                    f"🔒 Para ascender a {target_level} debes aprobar primero la Evaluación Final de {state.get('level', 'A1')}.",
                    show_alert=True,
                )
                return
            tracker.set_user_level(user_id, target_level)
            tracker.set_user_exercise_index(user_id, 0)
            tracker.set_fsm_state(user_id, "IN_EXERCISE")
            await self._safe_edit_text(
                query,
                f"🚀 <b>¡Ascenso al Nivel {target_level} completado!</b>\nIniciando tu nuevo programa de entrenamiento.",
            )
            await self._send_exercise_card(update, user_id, edit_message=False)

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
        active_unit = state.get("active_unit", "all")

        actual_id = data.replace("tts_slow_", "").replace("tts_", "")
        if actual_id == "custom" and state.get("custom_phrase"):
            text = state["custom_phrase"]
        else:
            exercises = get_exercises(
                language=lang,
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
                unit_id=active_unit,
            )
            if not exercises:
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
        if state.get("skill_mode") == "listening":
            caption = (
                f"{icon} <b>Audio de Comprensión Auditiva ({caption_flag}{' - 0.8x' if slow else ''}):</b>\n"
                f"🎧 <i>Escucha con atención y selecciona tu respuesta en la tarjeta del ejercicio arriba.</i>"
            )
        else:
            label = (
                f"{icon} <b>Referencia pausada (0.8x - {caption_flag}):</b>"
                if slow
                else f"{icon} <b>Referencia nativa ({caption_flag}):</b>"
            )
            caption = f'{label}\n"{text}"'

        await query.message.reply_voice(
            voice=audio_stream,
            caption=caption,
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

        # 1.5 Modo CONVERSACIÓN: Interacción de roleplay
        if skill_mode == "conversation" or state.get("fsm_state") == "IN_CONVERSATION":
            await self._handle_conversation_turn(update, user_id, user_text=text, is_audio=False)
            return

        # 1.6 Modo EVALUACIÓN FINAL: Respuesta escrita en el examen
        if state.get("fsm_state") == "IN_FINAL_EXAM":
            active_exam = tracker.get_active_final_exam(user_id)
            if active_exam:
                exam_obj = get_level_exam(active_exam["language"], active_exam["level"])
                if exam_obj:
                    curr_q_idx = active_exam["current_question_index"]
                    q = exam_obj.questions[curr_q_idx]
                    if q.section == "schreiben":
                        await update.effective_message.reply_chat_action(ChatAction.TYPING)
                        eval_res = gemini_coach.evaluate_writing(
                            user_input=text,
                            target_text=q.target_answer or "",
                            prompt=q.prompt_es,
                            language=active_exam["language"],
                            level=active_exam["level"],
                        )
                        is_correct = eval_res.is_correct or eval_res.score >= 70.0
                        score_pts = float(q.points) * (eval_res.score / 100.0)

                        res = tracker.submit_exam_answer(
                            user_id=user_id,
                            question_id=q.id,
                            section=q.section,
                            user_answer=text,
                            is_correct=is_correct,
                            score_points=score_pts,
                            explanation=eval_res.pedagogical_feedback or q.explanation_es,
                        )
                        icon = "✅" if is_correct else "🟡"
                        clean_fb = _format_markdown_for_telegram(eval_res.pedagogical_feedback)
                        await self._safe_reply_text(
                            update.effective_message,
                            f"{icon} <b>Respuesta de Examen registrada ({eval_res.score:.0f}/100):</b>\n{clean_fb}",
                        )
                        if res.get("status") == "next_question":
                            active_session = {
                                "level": active_exam["level"],
                                "language": active_exam["language"],
                                "total_questions": len(exam_obj.questions),
                                "current_index": res["current_index"],
                                "current_question": res["current_question"],
                            }
                            await self._send_exam_question_card(update, user_id, active_session, edit_message=False)
                        elif res.get("status") == "exam_completed":
                            await self._send_exam_result_card(update, user_id, res, edit_message=False)
                        return

        active_unit = state.get("active_unit", "all")

        # 2. Modo ESCRITURA: Evaluar la respuesta del alumno
        if skill_mode == "writing":
            exercises = get_exercises(
                language=lang, level=level, skill_type="writing", unit_id=active_unit
            )
            if not exercises:
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

            if eval_res.is_correct or eval_res.score >= 60:
                tracker.mark_exercise_completed(user_id, ex.id)
                words = extract_words_from_text(ex.target_text)
                if ex.vocabulary_breakdown:
                    words.extend(list(ex.vocabulary_breakdown.keys()))
                tracker.record_mastered_words(user_id, lang, words, level=ex.level)

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
            exercises = get_exercises(
                language=lang, level=level, skill_type="listening", unit_id=active_unit
            )
            if not exercises:
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
                    tracker.mark_exercise_completed(user_id, ex.id)
                    words = extract_words_from_text(ex.target_text)
                    if ex.vocabulary_breakdown:
                        words.extend(list(ex.vocabulary_breakdown.keys()))
                    tracker.record_mastered_words(user_id, lang, words, level=level)
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

            if comp_res.get("is_correct"):
                tracker.mark_exercise_completed(user_id, ex.id)
                words = extract_words_from_text(ex.target_text)
                if ex.vocabulary_breakdown:
                    words.extend(list(ex.vocabulary_breakdown.keys()))
                tracker.record_mastered_words(user_id, lang, words, level=level)

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
        skill_mode = state.get("skill_mode", "speaking")

        # 0. Si el usuario está en modo CONVERSACIÓN
        if skill_mode == "conversation" or state.get("fsm_state") == "IN_CONVERSATION":
            status_msg = await update.message.reply_text(
                "🎙️ <b>Transcribiendo tu audio y consultando con tu interlocutor...</b>",
                parse_mode=ParseMode.HTML,
            )
            await update.message.reply_chat_action(ChatAction.TYPING)
            temp_wav_path = None
            try:
                voice_obj = update.message.voice or update.message.audio
                if not voice_obj:
                    return
                voice_file = await voice_obj.get_file()
                ogg_bytes = await voice_file.download_as_bytearray()
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

                transcription = azure_service.transcribe_speech(temp_wav_path, language=lang)
                if not transcription:
                    transcription = "Hallo" if lang.startswith("de") else "Hello"

                await self._safe_edit_text(
                    status_msg,
                    f'🗣️ <b>Dijiste:</b> <i>"{transcription}"</i>\n'
                    "<i>Consultando respuesta del interlocutor...</i>",
                )
                await self._handle_conversation_turn(
                    update, user_id, user_text=transcription, is_audio=True, status_msg=status_msg
                )
            except Exception as e:
                logger.error(f"Error procesando voz en conversación: {e}", exc_info=True)
                await self._safe_edit_text(
                    status_msg,
                    f"⚠️ Ocurrió un error procesando tu audio: {str(e)}",
                )
            finally:
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                    except Exception:
                        pass
            return

        # 0.5 Modo EVALUACIÓN FINAL: Sección Sprechen (Expresión Oral)
        if state.get("fsm_state") == "IN_FINAL_EXAM":
            active_exam = tracker.get_active_final_exam(user_id)
            if active_exam:
                exam_obj = get_level_exam(active_exam["language"], active_exam["level"])
                if exam_obj:
                    curr_q_idx = active_exam["current_question_index"]
                    q = exam_obj.questions[curr_q_idx]
                    if q.section == "sprechen":
                        status_msg = await update.message.reply_text(
                            "🎧 <b>Evaluando tu pronunciación para la pregunta de examen...</b>",
                            parse_mode=ParseMode.HTML,
                        )
                        temp_wav_path = None
                        try:
                            voice_obj = update.message.voice or update.message.audio
                            if not voice_obj:
                                return
                            voice_file = await voice_obj.get_file()
                            ogg_bytes = await voice_file.download_as_bytearray()
                            wav_bytes = audio_converter.ogg_to_wav(bytes(ogg_bytes))
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                                f.write(wav_bytes)
                                temp_wav_path = f.name

                            eval_res = azure_service.evaluate_pronunciation(
                                temp_wav_path, q.target_answer or "", active_exam["language"]
                            )
                            score_val = eval_res.overall_score
                            is_correct = score_val >= 65.0
                            score_pts = float(q.points) * (score_val / 100.0)

                            res = tracker.submit_exam_answer(
                                user_id=user_id,
                                question_id=q.id,
                                section=q.section,
                                user_answer=q.target_answer or "",
                                is_correct=is_correct,
                                score_points=score_pts,
                                explanation=f"Puntaje fonético: {score_val:.0f}/100. {q.explanation_es}",
                            )
                            icon = "✅" if is_correct else "🟡"
                            await self._safe_edit_text(
                                status_msg,
                                f"{icon} <b>Pregunta Oral Evaluada ({score_val:.0f}/100):</b>\n{q.explanation_es}",
                            )
                            if res.get("status") == "next_question":
                                active_session = {
                                    "level": active_exam["level"],
                                    "language": active_exam["language"],
                                    "total_questions": len(exam_obj.questions),
                                    "current_index": res["current_index"],
                                    "current_question": res["current_question"],
                                }
                                await self._send_exam_question_card(update, user_id, active_session, edit_message=False)
                            elif res.get("status") == "exam_completed":
                                await self._send_exam_result_card(update, user_id, res, edit_message=False)
                        finally:
                            if temp_wav_path and os.path.exists(temp_wav_path):
                                try:
                                    os.remove(temp_wav_path)
                                except Exception:
                                    pass
                        return

        active_unit = state.get("active_unit", "all")
        if state.get("custom_phrase"):
            reference_text = state["custom_phrase"]
            is_custom = True
        else:
            exercises = get_exercises(
                language=lang,
                level=state.get("level", "A1"),
                skill_type=state.get("skill_mode", "speaking"),
                unit_id=active_unit,
            )
            if not exercises:
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

            if not is_custom and eval_result.overall_score >= 60 and idx < len(exercises):
                tracker.mark_exercise_completed(user_id, exercises[idx].id)
                words = extract_words_from_text(reference_text)
                if exercises[idx].vocabulary_breakdown:
                    words.extend(list(exercises[idx].vocabulary_breakdown.keys()))
                tracker.record_mastered_words(
                    user_id, lang, words, level=state.get("level", "A1")
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

            # Desglose lineal compacto (1 línea por palabra con sus fonemas secuenciales)
            word_lines = []
            for w in eval_result.words:
                if w.score >= 85 and not any(p.score < 70 for p in w.phonemes):
                    word_lines.append(f"✅ <b>{w.word}</b> ➔ <code>{w.score:.0f}%</code>")
                else:
                    icon = "🟡" if w.score >= 65 else "🔴"
                    p_parts = []
                    for p in w.phonemes:
                        if p.score >= 75:
                            p_parts.append(p.phoneme)
                        elif p.score >= 55:
                            p_parts.append(f"🟡{p.phoneme}({p.score:.0f}%)")
                        else:
                            p_parts.append(f"🔴{p.phoneme}({p.score:.0f}%)")
                    linear_phonemes = " · ".join(p_parts)
                    word_lines.append(
                        f"{icon} <b>{w.word}</b> [{linear_phonemes}] ➔ <code>{w.score:.0f}%</code>"
                    )

            words_formatted = "\n".join(word_lines)

            # Aclaración amigable en español de los fonemas que fallaron
            clarifications = []
            for wp in set(weak_phonemes[:3]):
                explanation = get_phoneme_explanation(wp, lang)
                friendly_lbl = get_phoneme_friendly_label(wp, lang)
                if explanation:
                    clarifications.append(f"• Sonido <b>{friendly_lbl}</b>: {explanation}")

            clarif_section = ""
            if clarifications:
                clarif_section = (
                    "\n📖 <b>Guía de articulación (dónde colocar lengua/labios):</b>\n" + "\n".join(clarifications) + "\n"
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
