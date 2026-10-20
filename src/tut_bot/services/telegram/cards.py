from typing import Any, Dict, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tut_bot.services.telegram.formatters import _make_progress_bar


def build_level_completed_card(
    state: Dict[str, Any],
    info: Dict[str, Any],
    is_certified: bool,
    req: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera el texto HTML y el teclado inline de culminación de nivel/serie."""
    lang = info.get("language") or state["language"]
    level = info.get("level") or state.get("level", "A1")
    skill = info.get("skill_mode") or state.get("skill_mode", "speaking")
    next_level = "A2" if level == "A1" else ("B1" if level == "A2" else None)
    unlocked = state.get("unlocked_levels", ["A1"])

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
        if not req.get("can_take"):
            lines.append(
                f"📊 <i>Progreso de Temas: {req.get('completed_count', 0)} / {req.get('total_units', 6)} unidades aprobadas.</i>"
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

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_ready_for_exam_card(
    state: Dict[str, Any],
    info: Dict[str, Any],
    is_certified: bool,
    lvl_lex: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera el texto HTML y el teclado de habilitación para el examen final."""
    lang = info.get("language") or state["language"]
    level = info.get("level") or state.get("level", "A1")
    next_level = info.get("next_level") or ("A2" if level == "A1" else ("B1" if level == "A2" else None))
    lang_name = "🇩🇪 Alemán" if lang.startswith("de") else "🇺🇸 Inglés"
    exam_name = "Goethe Start Deutsch 1" if lang.startswith("de") else "Cambridge A1 Key"

    lines = [
        f"🎓 <b>¡HAS RECORRIDO LAS 6 UNIDADES DE NIVEL {level}!</b> 🎓\n",
        f"Has practicado las 6 Unidades Temáticas oficiales de <b>{level}</b> ({lang_name}).",
        f"📖 <b>Vocabulario oficial dominado:</b> <code>{lvl_lex['mastered_count']} / {lvl_lex['total_target']}</code> palabras ({lvl_lex['percentage']:.1f}%).\n",
        f"🏆 <b>EVALUACIÓN FINAL {level} ({exam_name}):</b>",
        "La evaluación evalúa las 4 macro-habilidades oficiales del MCER:",
        "• 👂 <b>Hören:</b> Comprensión auditiva de audios nativos.",
        "• 📖 <b>Lesen:</b> Comprensión lectora y avisos cotidianos.",
        "• ✍️ <b>Schreiben:</b> Redacción formal corta o respuestas directas.",
        "• 🗣️ <b>Sprechen:</b> Pronunciación y acústica fonética.\n",
    ]

    keyboard = []
    if is_certified:
        lines.append(f"✅ <i>¡Ya estás certificado en Nivel {level}! Puedes ascender a {next_level} o reintentar el examen para mejorar tu nota.</i>")
        if next_level:
            keyboard.append([
                InlineKeyboardButton(f"🚀 Ascender a Nivel {next_level}", callback_data=f"fsm_ascend_{next_level}")
            ])
        keyboard.append([
            InlineKeyboardButton(f"📝 Reintentar Evaluación Final {level}", callback_data=f"exam_start_{level}")
        ])
    else:
        lines.append(f"⚡ <i>Para desbloquear y ascender a <b>Nivel {next_level}</b> debes obtener al menos 75% en esta evaluación.</i>")
        keyboard.append([
            InlineKeyboardButton(f"📝 Rendir Evaluación Final {level}", callback_data=f"exam_start_{level}")
        ])

    keyboard.extend([
        [
            InlineKeyboardButton("📂 Repasar Unidades", callback_data="btn_units_menu"),
            InlineKeyboardButton("🎯 Cambiar Modo", callback_data="btn_mode_menu"),
        ],
        [
            InlineKeyboardButton("📊 Mis Estadísticas", callback_data="btn_stats"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="btn_start_menu"),
        ],
    ])

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_unit_completed_card(
    state: Dict[str, Any],
    info: Dict[str, Any],
    u_info: Any,
    next_u_info: Any,
    u_lex: Dict[str, Any],
    lvl_lex: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera el texto HTML y el teclado de unidad completada."""
    level = info.get("level") or state.get("level", "A1")
    completed_unit = info.get("completed_unit", "unit_1")
    next_unit = info.get("next_unit")
    units_done = info.get("units_completed_count", 1)
    total_units = info.get("total_units", 6)

    u_title = f"{u_info.icon} {u_info.title_es}" if u_info else completed_unit
    next_title = f"{next_u_info.icon} {next_u_info.title_es}" if next_u_info else next_unit

    bar = _make_progress_bar((units_done / total_units) * 100.0)

    lines = [
        "🎉 <b>¡SERIE DE EJERCICIOS COMPLETADA!</b> 🎉\n",
        f"Has completado la ronda de práctica de: <b>{u_title}</b>.",
        f"📖 <b>Vocabulario aprendido en esta unidad:</b> <code>{u_lex['mastered_count']} / {u_lex['total_target']}</code> palabras ({u_lex['percentage']:.0f}%)\n",
        f"📊 <b>Progreso léxico en Nivel {level}:</b> <code>{lvl_lex['mastered_count']} / {lvl_lex['total_target']}</code> palabras ({lvl_lex['percentage']:.1f}%)\n",
        f"🗺️ <b>Progreso de Unidades en Nivel {level}:</b>\n",
        f"• <code>[{bar}]</code> <b>{units_done} / {total_units}</b> unidades recorridas ({int((units_done / total_units) * 100)}%)\n",
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

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_exam_question_card(
    exam_session: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera el contenido visual y teclado de una pregunta de examen."""
    q = exam_session.get("current_question")
    if not q:
        return "", InlineKeyboardMarkup([])

    q_idx = exam_session.get("current_index", 0) + 1
    total_q = exam_session.get("total_questions", 6)
    level = exam_session.get("level", "A1")

    bar = _make_progress_bar((q_idx / total_q) * 100.0)

    lines = [
        f"📝 <b>EVALUACIÓN FINAL DE NIVEL {level}</b>",
        f"<code>[{bar}]</code> Pregunta <b>{q_idx} de {total_q}</b> — <i>{q.section_name_es}</i>\n",
        f"🎯 <b>Consigna:</b> {q.prompt_es}\n",
    ]

    if getattr(q, "context_text", None):
        lines.append(f"📖 <b>Texto de Lectura:</b>\n<i>\"{q.context_text}\"</i>\n")

    if getattr(q, "question_text", None):
        lines.append(f"❓ <b>{q.question_text}</b>\n")

    keyboard = []

    if getattr(q, "audio_text", None):
        keyboard.append([
            InlineKeyboardButton("🔊 Escuchar Audio", callback_data=f"exam_tts_{q.id}"),
            InlineKeyboardButton("🐢 Escuchar Lento", callback_data=f"exam_ttsslow_{q.id}"),
        ])

    if getattr(q, "options", None):
        for idx, opt in enumerate(q.options):
            keyboard.append([
                InlineKeyboardButton(f"{chr(65 + idx)}) {opt}", callback_data=f"exam_opt_{idx}")
            ])
    elif q.section == "schreiben":
        lines.append("✍️ <i>Escribe tu respuesta como mensaje de texto a continuación:</i>")
    elif q.section == "sprechen":
        lines.append(f"👉 Frase: <b>\"{q.target_answer}\"</b>\n🎙️ <i>Graba y envía una nota de voz pronunciando la frase indicada.</i>")

    keyboard.append([
        InlineKeyboardButton("❌ Cancelar Examen", callback_data="exam_cancel"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_exam_result_card(
    result: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera la tarjeta con el resultado de aprobación o reprobación del examen final."""
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

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_stats_card(
    stats: Dict[str, Any],
    user_state: Dict[str, Any],
    lex_prog: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera el texto de estadísticas del usuario y el teclado de navegación."""
    lang = user_state["language"]
    level = user_state.get("level", "A1")
    exam_name = "Goethe Start Deutsch 1" if lang.startswith("de") else "Cambridge A1 Key"

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

    if stats.get("total_attempts", 0) == 0:
        text = (
            f"📊 <b>Tus Estadísticas en tut_bot</b>\n\n"
            f"{lex_section}"
            "🗣️ <i>Aún no has realizado prácticas de fonética con notas de voz.</i>\n"
            "¡Usa /ejercicio y envía tu primer audio para comenzar tu registro acústico!"
        )
    else:
        avg_acc = stats.get("average_accuracy", 0.0)
        avg_flu = stats.get("average_fluency", 0.0)
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

    return text, InlineKeyboardMarkup(keyboard)


def build_conversation_mission_card(
    scen: Any,
    active_conv: Dict[str, Any],
    lang: str,
    level: str,
    u_info: Any,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Genera la tarjeta visual y teclado de misión para roleplay conversacional."""
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

    hints = [f"• <i>{p}</i>" for p in scen.target_phrases[:3]]
    hints_str = "\n".join(hints)

    char_avatar = getattr(scen, "avatar_emoji", "👤")
    char_traits = getattr(scen, "personality_traits", "")
    traits_block = f"✨ <b>Personalidad:</b> <i>{char_traits}</i>\n" if char_traits else ""

    dialogue_preview = []
    for t in turns[-4:]:
        icon = char_avatar if t.get("role") == "character" else "🎓"
        dialogue_preview.append(f"{icon} <b>{t.get('name')}:</b> {t.get('text')}")
    dialogue_text = "\n".join(dialogue_preview)

    spoiler_es = (
        f"<tg-spoiler><i>🇪🇸 {last_turn.get('text_es', '')}</i></tg-spoiler>"
        if last_turn.get("text_es")
        else ""
    )

    lang_badge = "🇩🇪 ALEMÁN" if lang.startswith("de") else "🇺🇸 INGLÉS"
    u_badge = f" · {u_info.icon} U{u_info.number}" if u_info else ""

    card = (
        f"🎭 <b>{lang_badge} [{level}{u_badge}] — Misión de Conversación</b>\n"
        f"<b>Escenario:</b> {scen.title}\n"
        f"{char_avatar} <b>Interlocutor:</b> <b>{scen.character_name}</b> (<i>{scen.character_role}</i>)\n"
        f"{traits_block}"
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
            InlineKeyboardButton(
                "💡 ¿Qué puedo responder?", callback_data="conv_hint_0"
            ),
        ],
        [
            InlineKeyboardButton("🏁 Finalizar Misión", callback_data="conv_finish"),
            InlineKeyboardButton("🔄 Reiniciar Misión", callback_data="conv_restart"),
        ],
        [
            InlineKeyboardButton("🎭 Cambiar Personaje", callback_data="conv_change_char"),
            InlineKeyboardButton("📂 Unidades", callback_data="btn_units_menu"),
        ],
        [
            InlineKeyboardButton("🎯 Cambiar Modo", callback_data="btn_mode_menu"),
        ],
    ]

    return card, InlineKeyboardMarkup(keyboard)
