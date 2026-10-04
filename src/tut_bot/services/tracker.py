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
            conn.commit()

    def get_user_state(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el estado actual del usuario o crea uno por defecto."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                return {
                    "user_id": row_dict["user_id"],
                    "language": row_dict["language"],
                    "exercise_index": row_dict["exercise_index"],
                    "custom_phrase": row_dict["custom_phrase"],
                    "skill_mode": row_dict.get("skill_mode", "speaking"),
                    "level": row_dict.get("level", "A1"),
                    "updated_at": row_dict["updated_at"],
                }

            # Estado por defecto
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO user_states (user_id, language, exercise_index, custom_phrase, skill_mode, level, updated_at)
                VALUES (?, 'de-DE', 0, NULL, 'speaking', 'A1', ?)
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
                "updated_at": now,
            }

    def set_user_language(self, user_id: str, language: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_states (user_id, language, exercise_index, updated_at)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language = excluded.language,
                    exercise_index = 0,
                    updated_at = excluded.updated_at
                """,
                (user_id, language, now),
            )
            conn.commit()

    def set_user_skill_mode(self, user_id: str, skill_mode: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET skill_mode = ?, exercise_index = 0, custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (skill_mode, now, user_id),
            )
            conn.commit()

    def set_user_level(self, user_id: str, level: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_states
                SET level = ?, exercise_index = 0, custom_phrase = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (level, now, user_id),
            )
            conn.commit()

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


tracker = ProgressTracker()
