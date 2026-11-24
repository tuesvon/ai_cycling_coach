
import json
import math
import sqlite3

from datetime import datetime, timezone

from src.athletes.credentials import (
    DATABASE_PATH,
    initialize_database,
)


WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def initialize_training_preferences_table():
    initialize_database()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS training_preferences (
                athlete_id TEXT PRIMARY KEY,
                availability_json TEXT NOT NULL,
                spontaneous_races INTEGER NOT NULL DEFAULT 0,
                race_duration_minutes INTEGER,
                notes TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        connection.commit()

    finally:
        connection.close()


def validate_training_preferences(preferences):
    if not isinstance(preferences, dict):
        raise ValueError("Настройки должны быть словарём")

    allowed_fields = {
        "availability",
        "spontaneous_races",
        "race_duration_minutes",
        "notes",
    }

    unknown = set(preferences) - allowed_fields

    if unknown:
        raise ValueError(f"Неизвестные поля: {sorted(unknown)}")

    availability = preferences.get("availability")

    if not isinstance(availability, dict):
        raise ValueError("Не указано расписание тренировок")

    if set(availability) != set(WEEKDAYS):
        raise ValueError(
            "Расписание должно содержать все семь дней недели"
        )

    normalized_availability = {}

    for day in WEEKDAYS:
        minutes = availability[day]

        if minutes is not None:
            if (
                isinstance(minutes, bool)
                or not isinstance(minutes, int)
                or minutes < 0
            ):
                raise ValueError(
                    f"Некорректное время тренировки: {day}"
                )

        normalized_availability[day] = minutes

    spontaneous_races = preferences.get(
        "spontaneous_races", False
    )

    if not isinstance(spontaneous_races, bool):
        raise ValueError(
            "spontaneous_races должен быть True или False"
        )

    race_duration = preferences.get("race_duration_minutes")

    if race_duration is not None:
        if (
            isinstance(race_duration, bool)
            or not isinstance(race_duration, int)
            or race_duration <= 0
        ):
            raise ValueError(
                "Продолжительность гонки должна быть "
                "положительным целым числом"
            )

    notes = preferences.get("notes")

    if notes is not None and not isinstance(notes, str):
        raise ValueError("Примечания должны быть текстом")

    return {
        "availability": normalized_availability,
        "spontaneous_races": spontaneous_races,
        "race_duration_minutes": race_duration,
        "notes": notes.strip() if notes else None,
    }


def save_training_preferences(athlete_id, preferences):
    """
    Создаёт или обновляет предпочтения спортсмена.
    """
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise ValueError("Не указан спортсмен")

    validated = validate_training_preferences(preferences)

    initialize_training_preferences_table()

    updated_at = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute(
            """
            INSERT INTO training_preferences (
                athlete_id,
                availability_json,
                spontaneous_races,
                race_duration_minutes,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(athlete_id) DO UPDATE SET
                availability_json = excluded.availability_json,
                spontaneous_races = excluded.spontaneous_races,
                race_duration_minutes = excluded.race_duration_minutes,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                athlete_id.strip(),
                json.dumps(validated["availability"]),
                int(validated["spontaneous_races"]),
                validated["race_duration_minutes"],
                validated["notes"],
                updated_at,
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_training_preferences(athlete_id):
    """
    Возвращает предпочтения спортсмена или None.
    """
    initialize_training_preferences_table()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM training_preferences
            WHERE athlete_id = ?
            """,
            (athlete_id,),
        ).fetchone()

        if row is None:
            return None

        return {
            "athlete_id": row["athlete_id"],
            "availability": json.loads(
                row["availability_json"]
            ),
            "spontaneous_races": bool(
                row["spontaneous_races"]
            ),
            "race_duration_minutes": row[
                "race_duration_minutes"
            ],
            "notes": row["notes"],
            "updated_at": row["updated_at"],
        }

    finally:
        connection.close()
