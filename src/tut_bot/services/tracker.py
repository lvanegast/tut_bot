import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tut_bot.config import BASE_DIR

logger = logging.getLogger(__name__)

DB_PATH = BASE_DIR / "data" / "tut_bot.db"


class ProgressTracker:
    """
    Gestor de persistencia ligero en SQLite para registrar el progreso,
    estado de la sesión (Telegram y Web) y fonemas con mayor margen de mejora.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crea las tablas necesarias si no existen."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id TEXT PRIMARY KEY,
                    language TEXT NOT NULL DEFAULT 'de-DE',
                    exercise_index INTEGER NOT NULL DEFAULT 0,
                    custom_phrase TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    reference_text TEXT NOT NULL,
                    overall_score REAL NOT NULL,
                    accuracy_score REAL NOT NULL,
                    fluency_score REAL NOT NULL,
                    prosody_score REAL,
                    weak_phonemes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_user ON evaluations(user_id)")

            # Migración ligera: añadir columnas si no existen
            cursor.execute("PRAGMA table_info(user_states)")
            cols = [c["name"] for c in cursor.fetchall()]
            if "skill_mode" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN skill_mode TEXT NOT NULL DEFAULT 'speaking'"
                )
            if "level" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN level TEXT NOT NULL DEFAULT 'A1'"
                )
            if "fsm_state" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN fsm_state TEXT NOT NULL DEFAULT 'IN_EXERCISE'"
                )
            if "completed_exercises" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN completed_exercises TEXT NOT NULL DEFAULT '[]'"
                )
            if "unlocked_levels" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN unlocked_levels TEXT NOT NULL DEFAULT '[\"A1\"]'"
                )
            if "passed_levels" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN passed_levels TEXT NOT NULL DEFAULT '[]'"
                )
            if "active_unit" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN active_unit TEXT NOT NULL DEFAULT 'all'"
                )
            if "completed_units" not in cols:
                cursor.execute(
                    "ALTER TABLE user_states ADD COLUMN completed_units TEXT NOT NULL DEFAULT '[]'"
                )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    word TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'A1',
                    mastery_score INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_reviewed TEXT NOT NULL,
                    UNIQUE(user_id, language, word)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_vocab ON user_vocabulary(user_id, language)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    level TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    scenario_title TEXT NOT NULL,
                    mission_brief TEXT NOT NULL,
                    character_name TEXT NOT NULL,
                    turns_json TEXT NOT NULL DEFAULT '[]',
                    is_completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_conv ON user_conversations(user_id, is_completed)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    level TEXT NOT NULL,
                    current_question_index INTEGER NOT NULL DEFAULT 0,
                    answers_json TEXT NOT NULL DEFAULT '[]',
                    score REAL DEFAULT 0.0,
                    is_passed INTEGER DEFAULT 0,
                    is_completed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_exam ON user_exams(user_id, is_completed)"
            )
            conn.commit()

    def get_user_state(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el estado actual del usuario o crea uno por defecto."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                comp_raw = row_dict.get("completed_exercises", "[]")
                try:
                    completed_exercises = json.loads(comp_raw) if comp_raw else []
                except Exception:
                    completed_exercises = []

                unlocked_raw = row_dict.get("unlocked_levels", '["A1"]')
                try:
                    unlocked_levels = json.loads(unlocked_raw) if unlocked_raw else ["A1"]
                except Exception:
                    unlocked_levels = ["A1"]

                passed_raw = row_dict.get("passed_levels", "[]")
                try:
                    passed_levels = json.loads(passed_raw) if passed_raw else []
                except Exception:
                    passed_levels = []

                units_raw = row_dict.get("completed_units", "[]")
                try:
                    completed_units = json.loads(units_raw) if units_raw else []
                except Exception:
                    completed_units = []

                return {
                    "user_id": row_dict["user_id"],
                    "language": row_dict["language"],
                    "exercise_index": row_dict["exercise_index"],
                    "custom_phrase": row_dict["custom_phrase"],
                    "skill_mode": row_dict.get("skill_mode", "speaking"),
                    "level": row_dict.get("level", "A1"),
                    "fsm_state": row_dict.get("fsm_state", "IN_EXERCISE"),
                    "completed_exercises": completed_exercises,
                    "unlocked_levels": unlocked_levels,
                    "passed_levels": passed_levels,
                    "active_unit": row_dict.get("active_unit", "all"),
                    "completed_units": completed_units,
                    "updated_at": row_dict["updated_at"],
                }

            # Estado por defecto
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO user_states (user_id, language, exercise_index, custom_phrase, skill_mode, level, fsm_state, completed_exercises, unlocked_levels, passed_levels, active_unit, completed_units, updated_at)
                VALUES (?, 'de-DE', 0, NULL, 'speaking', 'A1', 'IN_EXERCISE', '[]', '[\"A1\"]', '[]', 'all', '[]', ?)
                """,
                (user_id, now),
            )
            conn.commit()
            return {
                "user_id": user_id,
                "language": "de-DE",
                "exercise_index": 0,
                "custom_phrase": None,
                "skill_mode": "speaking",
                "level": "A1",
                "fsm_state": "IN_EXERCISE",
                "completed_exercises": [],
                "unlocked_levels": ["A1"],
                "passed_levels": [],
                "active_unit": "all",
                "completed_units": [],
                "updated_at": now,
            }

    def set_user_language(self, user_id: str, language: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_states (user_id, language, exercise_index, fsm_state, updated_at)
                VALUES (?, ?, 0, 'IN_EXERCISE', ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language = excluded.language,
                    exercise_index = 0,
                    fsm_state = 'IN_EXERCISE',
                    custom_phrase = NULL,
                    updated_at = excluded.updated_at
                """,
                (user_id, language, now),
            )
            conn.commit()

    def set_user_skill_mode(self, user_id: str, skill_mode: str):
        self.get_user_state(user_id)
        now = datetime.now(timezone.utc).isoformat()
        target_fsm = "IN_CONVERSATION" if skill_mode == "conversation" else "IN_EXERCISE"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET skill_mode = ?, exercise_index = 0, fsm_state = ?, custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (skill_mode, target_fsm, now, user_id),
            )
            conn.commit()

    def set_user_level(self, user_id: str, level: str) -> bool:
        state = self.get_user_state(user_id)
        unlocked = state.get("unlocked_levels", ["A1"])
        if level not in unlocked:
            logger.warning(
                f"Usuario {user_id} intentó acceder al nivel {level} pero aún no está desbloqueado."
            )
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET level = ?, exercise_index = 0, fsm_state = 'IN_EXERCISE', custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (level, now, user_id),
            )
            conn.commit()
        return True

    def set_user_exercise_index(self, user_id: str, index: int):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET exercise_index = ?, custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (max(0, index), now, user_id),
            )
            conn.commit()

    def set_user_custom_phrase(self, user_id: str, phrase: Optional[str]):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET custom_phrase = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (phrase.strip() if phrase else None, now, user_id),
            )
            conn.commit()

    def set_fsm_state(self, user_id: str, state: str):
        """Actualiza el estado actual en la Máquina de Estados Finita."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET fsm_state = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (state, now, user_id),
            )
            conn.commit()

    def mark_exercise_completed(self, user_id: str, exercise_id: str):
        """Registra un ejercicio como completado/aprobado por el usuario."""
        state = self.get_user_state(user_id)
        completed = set(state.get("completed_exercises", []))
        if exercise_id not in completed:
            completed.add(exercise_id)
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_states
                    SET completed_exercises = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (json.dumps(sorted(list(completed))), now, user_id),
                )
                conn.commit()

    def mark_unit_completed(
        self, user_id: str, language: str, level: str, unit_id: str
    ) -> List[str]:
        """Registra una unidad temática completada para el usuario y retorna la lista de unidades aprobadas del nivel."""
        key = f"{language}_{level}_{unit_id}"
        state = self.get_user_state(user_id)
        completed = set(state.get("completed_units", []))
        if key not in completed:
            completed.add(key)
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_states
                    SET completed_units = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (json.dumps(sorted(list(completed))), now, user_id),
                )
                conn.commit()

        prefix = f"{language}_{level}_"
        return [u.replace(prefix, "") for u in completed if u.startswith(prefix)]

    def get_completed_units(self, user_id: str, language: str, level: str) -> List[str]:
        """Obtiene la lista de IDs de unidades completadas para un nivel e idioma dados."""
        state = self.get_user_state(user_id)
        completed = set(state.get("completed_units", []))
        prefix = f"{language}_{level}_"
        return [u.replace(prefix, "") for u in completed if u.startswith(prefix)]

    def advance_exercise_fsm(
        self,
        user_id: str,
        total_exercises: int,
        current_unit_id: Optional[str] = None,
        require_all_units: bool = True,
    ) -> Dict[str, Any]:
        """
        Avanza la máquina de estados pedagógica.
        - Si quedan ejercicios en la serie actual: avanza al siguiente (IN_EXERCISE).
        - Si se completa una unidad: transiciona a UNIT_COMPLETED.
        - Solo cuando se completan las 6 unidades oficiales de A1: transiciona a READY_FOR_FINAL_EXAM.
          El siguiente nivel (A2) NUNCA se desbloquea automáticamente hasta aprobar el Examen Final.
        """
        state = self.get_user_state(user_id)
        current_idx = state["exercise_index"]
        next_idx = current_idx + 1
        lang = state["language"]
        level = state["level"]
        skill = state["skill_mode"]

        if next_idx < total_exercises:
            self.set_user_exercise_index(user_id, next_idx)
            self.set_fsm_state(user_id, "IN_EXERCISE")
            return {
                "status": "next_exercise",
                "index": next_idx,
                "total": total_exercises,
            }
        else:
            # Llegó al final de la serie de ejercicios
            unit_to_mark = (
                current_unit_id
                if (current_unit_id and current_unit_id != "all")
                else state.get("active_unit", "unit_1")
            )
            if unit_to_mark == "all":
                unit_to_mark = "unit_1"

            completed_units = self.mark_unit_completed(user_id, lang, level, unit_to_mark)
            total_units = 6  # 6 Unidades Temáticas oficiales por nivel

            unit_num = 1
            if unit_to_mark.startswith("unit_"):
                try:
                    unit_num = int(unit_to_mark.replace("unit_", ""))
                except ValueError:
                    unit_num = 1
            elif unit_to_mark.isdigit():
                unit_num = int(unit_to_mark)
            next_unit_num = unit_num + 1
            next_unit_id = f"unit_{next_unit_num}" if next_unit_num <= total_units else None

            all_units_done = len(completed_units) >= total_units

            if all_units_done:
                self.set_fsm_state(user_id, "READY_FOR_FINAL_EXAM")
                self.mark_level_passed(user_id, lang, level, skill)
                next_level = "A2" if level == "A1" else ("B1" if level == "A2" else None)
                return {
                    "status": "ready_for_final_exam",
                    "language": lang,
                    "level": level,
                    "skill_mode": skill,
                    "next_level": next_level,
                    "total_completed": total_exercises,
                    "units_completed": len(completed_units),
                    "total_units": total_units,
                }
            else:
                self.set_fsm_state(user_id, "UNIT_COMPLETED")
                return {
                    "status": "unit_completed",
                    "language": lang,
                    "level": level,
                    "skill_mode": skill,
                    "completed_unit": unit_to_mark,
                    "next_unit": next_unit_id,
                    "units_completed_count": len(completed_units),
                    "total_units": total_units,
                }

    def mark_level_passed(self, user_id: str, language: str, level: str, skill_mode: str):
        """Registra que una destreza de un nivel específico fue completada y aprobada."""
        key = f"{language}_{level}_{skill_mode}"
        state = self.get_user_state(user_id)
        passed = set(state.get("passed_levels", []))
        if key not in passed:
            passed.add(key)
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_states
                    SET passed_levels = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (json.dumps(sorted(list(passed))), now, user_id),
                )
                conn.commit()

    def unlock_level(self, user_id: str, level: str):
        """Desbloquea un nuevo nivel CEFR para el alumno."""
        state = self.get_user_state(user_id)
        unlocked = set(state.get("unlocked_levels", ["A1"]))
        if level not in unlocked:
            unlocked.add(level)
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_states
                    SET unlocked_levels = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (json.dumps(sorted(list(unlocked))), now, user_id),
                )
                conn.commit()

    def ascend_to_next_level(self, user_id: str) -> Optional[str]:
        """Asciende al alumno al siguiente nivel CEFR únicamente si ya fue desbloqueado tras aprobar el examen final."""
        state = self.get_user_state(user_id)
        current_level = state.get("level", "A1")
        next_level = "A2" if current_level == "A1" else ("B1" if current_level == "A2" else None)
        unlocked = state.get("unlocked_levels", ["A1"])
        if next_level and next_level in unlocked:
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_states
                    SET level = ?, exercise_index = 0, fsm_state = 'IN_EXERCISE', custom_phrase = NULL, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (next_level, now, user_id),
                )
                conn.commit()
            return next_level
        logger.warning(
            f"Ascenso denegado para {user_id}: el nivel {next_level} aún no está en desbloqueados {unlocked}"
        )
        return None

    def can_take_final_exam(self, user_id: str, language: str, level: str) -> Dict[str, Any]:
        """
        Determina si el usuario cumple los requisitos para rendir la Evaluación Final de Nivel.
        Requisito estricto: Haber completado las 6 Unidades Temáticas oficiales de dicho nivel.
        """
        completed_units = self.get_completed_units(user_id, language, level)
        total_units = 6
        can_take = len(completed_units) >= total_units
        missing = [
            f"unit_{i}"
            for i in range(1, total_units + 1)
            if f"unit_{i}" not in completed_units
        ]
        state = self.get_user_state(user_id)
        is_already_certified = f"{language}_{level}_certified" in state.get(
            "passed_levels", []
        )
        return {
            "can_take": can_take,
            "completed_count": len(completed_units),
            "total_units": total_units,
            "missing_units": missing,
            "is_already_certified": is_already_certified,
        }

    def start_final_exam(
        self, user_id: str, language: str, level: str
    ) -> Optional[Dict[str, Any]]:
        """Inicia una sesión de Evaluación Final de Nivel en la base de datos."""
        from tut_bot.services.final_exam import get_level_exam

        exam = get_level_exam(language, level)
        if not exam:
            return None

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Cerrar exámenes previos no completados
            cursor.execute(
                "UPDATE user_exams SET is_completed = 1, updated_at = ? WHERE user_id = ? AND is_completed = 0",
                (now, user_id),
            )
            cursor.execute(
                """
                INSERT INTO user_exams (
                    user_id, language, level, current_question_index,
                    answers_json, score, is_passed, is_completed, created_at, updated_at
                )
                VALUES (?, ?, ?, 0, '[]', 0.0, 0, 0, ?, ?)
                """,
                (user_id, language, level, now, now),
            )
            conn.commit()
            exam_id = cursor.lastrowid

        self.set_fsm_state(user_id, "IN_FINAL_EXAM")
        return {
            "exam_id": exam_id,
            "level": level,
            "language": language,
            "title_es": exam.title_es,
            "description_es": exam.description_es,
            "total_questions": len(exam.questions),
            "current_index": 0,
            "current_question": exam.questions[0] if exam.questions else None,
        }

    def get_active_final_exam(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Recupera el examen final activo del usuario si existe."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_exams
                WHERE user_id = ? AND is_completed = 0
                ORDER BY id DESC LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row_dict = dict(row)
            try:
                answers = json.loads(row_dict.get("answers_json", "[]"))
            except Exception:
                answers = []
            row_dict["answers"] = answers
            return row_dict

    def submit_exam_answer(
        self,
        user_id: str,
        question_id: str,
        section: str,
        user_answer: str,
        is_correct: bool,
        score_points: float,
        explanation: str,
    ) -> Dict[str, Any]:
        """Registra la respuesta a una pregunta del examen y avanza."""
        from tut_bot.services.final_exam import get_level_exam

        active = self.get_active_final_exam(user_id)
        if not active:
            return {"error": "No hay examen activo"}

        language = active["language"]
        level = active["level"]
        exam = get_level_exam(language, level)
        if not exam:
            return {"error": "Examen no encontrado"}

        answers = active.get("answers", [])
        answers.append(
            {
                "question_id": question_id,
                "section": section,
                "user_answer": user_answer,
                "is_correct": is_correct,
                "score_points": score_points,
                "explanation": explanation,
            }
        )

        next_idx = active["current_question_index"] + 1
        now = datetime.now(timezone.utc).isoformat()
        total_q = len(exam.questions)

        if next_idx < total_q:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE user_exams SET current_question_index = ?, answers_json = ?, updated_at = ? WHERE id = ?",
                    (next_idx, json.dumps(answers), now, active["id"]),
                )
                conn.commit()
            return {
                "status": "next_question",
                "current_index": next_idx,
                "total_questions": total_q,
                "current_question": exam.questions[next_idx],
                "last_result": {
                    "is_correct": is_correct,
                    "explanation": explanation,
                },
            }
        else:
            # Calificación final del examen completo
            total_possible = sum(q.points for q in exam.questions)
            total_earned = sum(a.get("score_points", 0.0) for a in answers)
            score_percent = round((total_earned / max(1, total_possible)) * 100.0, 1)
            is_passed = score_percent >= exam.passing_score_percentage

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_exams
                    SET current_question_index = ?, answers_json = ?, score = ?,
                        is_passed = ?, is_completed = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        next_idx,
                        json.dumps(answers),
                        score_percent,
                        1 if is_passed else 0,
                        now,
                        active["id"],
                    ),
                )
                conn.commit()

            if is_passed:
                self.mark_level_passed(user_id, language, level, "certified")
                next_level = "A2" if level == "A1" else ("B1" if level == "A2" else None)
                if next_level:
                    self.unlock_level(user_id, next_level)
                self.set_fsm_state(user_id, "EXAM_PASSED")
            else:
                next_level = None
                self.set_fsm_state(user_id, "EXAM_FAILED")

            return {
                "status": "exam_completed",
                "is_passed": is_passed,
                "score_percent": score_percent,
                "passing_score": exam.passing_score_percentage,
                "level": level,
                "language": language,
                "next_level": next_level,
                "answers": answers,
            }

    def cancel_final_exam(self, user_id: str):
        """Cancela el examen activo y regresa al modo de ejercicios."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_exams SET is_completed = 1, updated_at = ? WHERE user_id = ? AND is_completed = 0",
                (now, user_id),
            )
            conn.commit()
        self.set_fsm_state(user_id, "IN_EXERCISE")

    def set_user_unit(self, user_id: str, unit_id: str):
        """Fija la unidad temática activa del usuario y reinicia el índice del ejercicio."""
        self.get_user_state(user_id)
        now = datetime.now(timezone.utc).isoformat()
        norm_unit = str(unit_id).strip()
        if norm_unit.startswith("sel_"):
            norm_unit = norm_unit[len("sel_"):]
        if norm_unit.isdigit():
            norm_unit = f"unit_{norm_unit}"
        elif norm_unit != "all" and not norm_unit.startswith("unit_"):
            norm_unit = f"unit_{norm_unit}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET active_unit = ?, exercise_index = 0, fsm_state = 'IN_EXERCISE', custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (norm_unit, now, user_id),
            )
            conn.commit()

    def record_mastered_words(
        self, user_id: str, language: str, words: List[str], level: str = "A1"
    ) -> int:
        """Registra palabras aprendidas en el inventario léxico del usuario. Retorna cuántas fueron nuevas."""
        if not words:
            return 0
        from tut_bot.services.curriculum import match_known_words

        valid_words = match_known_words(words, language, level)
        if not valid_words:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        new_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for w in set(valid_words):
                cursor.execute(
                    """
                    INSERT INTO user_vocabulary (user_id, language, word, level, mastery_score, first_seen, last_reviewed)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(user_id, language, word) DO UPDATE SET
                        mastery_score = mastery_score + 1,
                        last_reviewed = excluded.last_reviewed
                    """,
                    (user_id, language, w, level, now, now),
                )
                if cursor.rowcount == 1:
                    new_count += 1
            conn.commit()
        return new_count

    def get_user_mastered_words(self, user_id: str, language: str, level: str = "A1") -> List[str]:
        """Obtiene la lista de palabras únicas que el usuario domina."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT word FROM user_vocabulary
                WHERE user_id = ? AND language = ? AND level = ?
                ORDER BY mastery_score DESC
                """,
                (user_id, language, level),
            )
            return [row["word"] for row in cursor.fetchall()]

    def get_user_lexicon_progress(
        self, user_id: str, language: str, level: str = "A1"
    ) -> Dict[str, Any]:
        """Calcula el progreso del usuario hacia la meta oficial del examen (ej: 650 palabras en A1)."""
        from tut_bot.services.curriculum import TOTAL_A1_LEXICON_COUNT

        mastered = self.get_user_mastered_words(user_id, language, level)
        mastered_set = set(mastered)
        total_target = TOTAL_A1_LEXICON_COUNT
        count = len(mastered_set)
        percent = min(100.0, (count / total_target) * 100.0) if total_target > 0 else 0.0

        return {
            "mastered_count": count,
            "total_target": total_target,
            "percentage": percent,
            "mastered_words": mastered,
        }

    def record_evaluation(
        self,
        user_id: str,
        language: str,
        reference_text: str,
        overall_score: float,
        accuracy_score: float,
        fluency_score: float,
        prosody_score: Optional[float],
        weak_phonemes: List[str],
    ):
        """Registra el intento para seguimiento pedagógico."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluations (
                    user_id, language, reference_text, overall_score,
                    accuracy_score, fluency_score, prosody_score,
                    weak_phonemes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    language,
                    reference_text,
                    overall_score,
                    accuracy_score,
                    fluency_score,
                    prosody_score,
                    json.dumps(weak_phonemes),
                    now,
                ),
            )
            conn.commit()

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Calcula estadísticas agregadas y los fonemas más débiles del usuario."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT overall_score, accuracy_score, fluency_score, prosody_score, weak_phonemes, created_at, reference_text
                FROM evaluations
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        if not rows:
            return {
                "total_attempts": 0,
                "average_overall": 0.0,
                "average_accuracy": 0.0,
                "average_fluency": 0.0,
                "weak_phonemes_top": [],
                "weak_phonemes": [],
                "recent_history": [],
            }

        total_attempts = len(rows)
        avg_overall = round(sum(r["overall_score"] for r in rows) / total_attempts, 1)
        avg_accuracy = round(sum(r["accuracy_score"] for r in rows) / total_attempts, 1)
        avg_fluency = round(sum(r["fluency_score"] for r in rows) / total_attempts, 1)

        # Contador de fonemas débiles
        phoneme_counter: Counter = Counter()
        for r in rows:
            try:
                phonemes = json.loads(r["weak_phonemes"])
                for p in phonemes:
                    phoneme_counter[p] += 1
            except Exception:
                pass

        weak_phonemes_top = [
            {"phoneme": p, "count": count} for p, count in phoneme_counter.most_common(5)
        ]

        recent = [
            {
                "reference_text": r["reference_text"],
                "overall_score": r["overall_score"],
                "created_at": r["created_at"],
            }
            for r in rows[:5]
        ]

        return {
            "total_attempts": total_attempts,
            "average_overall": avg_overall,
            "average_accuracy": avg_accuracy,
            "average_fluency": avg_fluency,
            "weak_phonemes_top": weak_phonemes_top,
            "weak_phonemes": [p for p, _ in phoneme_counter.most_common(5)],
            "recent_history": recent,
        }

    def start_conversation(
        self,
        user_id: str,
        language: str,
        level: str,
        scenario_id: str,
        scenario_title: str,
        mission_brief: str,
        character_name: str,
        initial_greeting: str,
        initial_greeting_es: str,
        unit_id: str = "unit_1",
    ) -> Dict[str, Any]:
        """Inicia una nueva sesión conversacional de roleplay activo."""
        self.get_user_state(user_id)
        now = datetime.now(timezone.utc).isoformat()
        initial_turn = [
            {
                "role": "character",
                "name": character_name,
                "text": initial_greeting,
                "text_es": initial_greeting_es,
                "timestamp": now,
            }
        ]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Cerrar conversaciones abiertas previas
            cursor.execute(
                "UPDATE user_conversations SET is_completed = 1, updated_at = ? WHERE user_id = ? AND is_completed = 0",
                (now, user_id),
            )
            cursor.execute(
                """
                INSERT INTO user_conversations (
                    user_id, language, level, unit_id, scenario_id, scenario_title,
                    mission_brief, character_name, turns_json, is_completed, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    user_id,
                    language,
                    level,
                    unit_id,
                    scenario_id,
                    scenario_title,
                    mission_brief,
                    character_name,
                    json.dumps(initial_turn),
                    now,
                    now,
                ),
            )
            conn.commit()
            conv_id = cursor.lastrowid

        self.set_user_skill_mode(user_id, "conversation")
        self.set_fsm_state(user_id, "IN_CONVERSATION")
        return {
            "conversation_id": conv_id,
            "scenario_id": scenario_id,
            "scenario_title": scenario_title,
            "mission_brief": mission_brief,
            "character_name": character_name,
            "turns": initial_turn,
        }

    def get_active_conversation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Recupera la conversación de roleplay activa del usuario si existe."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_conversations
                WHERE user_id = ? AND is_completed = 0
                ORDER BY id DESC LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row_dict = dict(row)
            try:
                turns = json.loads(row_dict.get("turns_json", "[]"))
            except Exception:
                turns = []
            row_dict["turns"] = turns
            return row_dict

    def append_conversation_turn(
        self,
        user_id: str,
        role: str,
        text: str,
        text_es: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """Agrega un turno (del alumno o del personaje) al diálogo activo."""
        active = self.get_active_conversation(user_id)
        if not active:
            return
        now = datetime.now(timezone.utc).isoformat()
        turns = active.get("turns", [])
        turn_data = {
            "role": role,
            "name": name or (active["character_name"] if role == "character" else "Alumno"),
            "text": text,
            "text_es": text_es,
            "timestamp": now,
        }
        turns.append(turn_data)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_conversations
                SET turns_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(turns), now, active["id"]),
            )
            conn.commit()

    def complete_conversation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Marca la conversación activa como completada y devuelve el registro final."""
        active = self.get_active_conversation(user_id)
        if not active:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_conversations SET is_completed = 1, updated_at = ? WHERE id = ?",
                (now, active["id"]),
            )
            conn.commit()
        self.set_fsm_state(user_id, "CONVERSATION_SUMMARY")
        return active

    def cancel_conversation(self, user_id: str):
        """Cancela la conversación activa y regresa al modo ejercicios."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_conversations SET is_completed = 1, updated_at = ? WHERE user_id = ? AND is_completed = 0",
                (now, user_id),
            )
            conn.commit()
        self.set_fsm_state(user_id, "IN_EXERCISE")
        self.set_user_skill_mode(user_id, "speaking")


tracker = ProgressTracker()
