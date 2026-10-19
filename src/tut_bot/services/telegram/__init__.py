"""
Subpaquete de soporte para TelegramCoachBot (formatters, card builders, etc.).
"""

from tut_bot.services.telegram.cards import (
    build_conversation_mission_card,
    build_exam_question_card,
    build_exam_result_card,
    build_level_completed_card,
    build_ready_for_exam_card,
    build_stats_card,
    build_unit_completed_card,
)
from tut_bot.services.telegram.formatters import (
    _format_markdown_for_telegram,
    _make_progress_bar,
    get_phoneme_explanation,
    get_phoneme_friendly_label,
)

__all__ = [
    "_format_markdown_for_telegram",
    "_make_progress_bar",
    "get_phoneme_explanation",
    "get_phoneme_friendly_label",
    "build_level_completed_card",
    "build_ready_for_exam_card",
    "build_unit_completed_card",
    "build_exam_question_card",
    "build_exam_result_card",
    "build_stats_card",
    "build_conversation_mission_card",
]
