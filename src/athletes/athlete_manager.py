import json
import sqlite3

from datetime import datetime, timezone

from src.integrations.garmin_api import get_activities as get_garmin_activities

from src.athletes.credentials import (
    DATABASE_PATH,
    initialize_database,
    save_api_key,
    get_api_key as get_stored_api_key
)

from src.integrations.intervals_api import (
    get_athlete_data,
    get_wellness as get_intervals_wellness
)

DEFAULT_DATA_SOURCES = {
    "training": {
        "primary": "intervals",
        "additional": []
    },
    "recovery": {
        "primary": "intervals",
        "additional": []
    },
    "detailed_activity": {
        "primary": "intervals",
        "additional": []
    }
}


def initialize_athletes_table():
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS athletes (
                athlete_id TEXT PRIMARY KEY,
                telegram_id TEXT,
                intervals_athlete_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                data_sources TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def register_athlete(api_key, telegram_id=None, data_sources=None):
    """
    Проверяет API-ключ Intervals.icu и регистрирует спортсмена.
    Сам API-ключ в профиль не записывается.
    """

    if not api_key or not api_key.strip():
        raise ValueError("API-ключ не может быть пустым")

    # Проверяем ключ и получаем данные спортсмена
    athlete_data = get_athlete_data(api_key=api_key.strip())

    intervals_id = athlete_data.get("id")
    name = athlete_data.get("name")

    if not intervals_id:
        raise ValueError("Intervals.icu не вернул ID спортсмена")

    if not name:
        raise ValueError("Intervals.icu не вернул имя спортсмена")

    athlete_id = str(intervals_id)

    sources = data_sources or DEFAULT_DATA_SOURCES

    initialize_athletes_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        existing = connection.execute(
            """
            SELECT telegram_id
            FROM athletes
            WHERE athlete_id = ?
            """,
            (athlete_id,)
        ).fetchone()

        if existing:
            existing_telegram_id = existing[0]

            if (
                existing_telegram_id is not None
                and telegram_id is not None
                and existing_telegram_id != str(telegram_id)
            ):
                raise ValueError(
                    "Этот аккаунт Intervals.icu уже зарегистрирован "
                    "другим пользователем Telegram"
                )

        else:
            # Проверяем, не зарегистрирован ли аккаунт под другим ID
            existing_account = connection.execute(
                """
                SELECT athlete_id
                FROM athletes
                WHERE intervals_athlete_id = ?
                """,
                (athlete_id,)
            ).fetchone()

            if existing_account:
                raise ValueError("Аккаунт уже зарегистрирован")

    # Сохраняем API-ключ только после успешной проверки
    save_api_key(
        athlete_id=athlete_id,
        provider="intervals",
        api_key=api_key.strip()
    )

    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO athletes (
                athlete_id,
                telegram_id,
                intervals_athlete_id,
                name,
                data_sources,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(athlete_id)
            DO UPDATE SET
                telegram_id = COALESCE(
                    excluded.telegram_id,
                    athletes.telegram_id
                ),
                name = excluded.name,
                data_sources = excluded.data_sources
            """,
            (
                athlete_id,
                str(telegram_id) if telegram_id is not None else None,
                athlete_id,
                name,
                json.dumps(sources, ensure_ascii=False),
                created_at
            )
        )

    return {
        "athlete_id": athlete_id,
        "intervals_athlete_id": athlete_id,
        "name": name,
        "telegram_id": telegram_id,
        "data_sources": sources,
        "registered": True
    }


def get_athlete(athlete_id):
    initialize_athletes_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM athletes
            WHERE athlete_id = ?
            """,
            (str(athlete_id),)
        ).fetchone()

    if row is None:
        return None

    return {
        "athlete_id": row["athlete_id"],
        "telegram_id": row["telegram_id"],
        "intervals_athlete_id": row["intervals_athlete_id"],
        "name": row["name"],
        "data_sources": json.loads(row["data_sources"]),
        "created_at": row["created_at"]
    }


def get_all_athletes():
    initialize_athletes_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT athlete_id
            FROM athletes
            ORDER BY name
            """
        ).fetchall()

    return [
        get_athlete(row[0])
        for row in rows
    ]

def delete_athlete(athlete_id):
    initialize_athletes_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "DELETE FROM credentials WHERE athlete_id = ?",
            (str(athlete_id),)
        )

        cursor = connection.execute(
            "DELETE FROM athletes WHERE athlete_id = ?",
            (str(athlete_id),)
        )

    return cursor.rowcount > 0


def get_registered_athlete_data(athlete_id):
    """
    Загружает данные конкретного зарегистрированного спортсмена
    из Intervals.icu, используя его сохранённый API-ключ.
    """

    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    api_key = get_stored_api_key(
        athlete_id=str(athlete_id),
        provider="intervals"
    )

    if api_key is None:
        raise ValueError("Для спортсмена не найден API-ключ Intervals.icu")

    athlete_data = get_athlete_data(api_key=api_key)

    expected_id = str(athlete["intervals_athlete_id"])
    actual_id = str(athlete_data.get("id"))

    if actual_id != expected_id:
        raise ValueError(
            "ID спортсмена из Intervals.icu не совпадает с зарегистрированным"
        )

    return athlete_data


def get_normalized_athlete_profile(athlete_id):
    """
    Возвращает профиль спортсмена в едином формате
    для аналитических модулей AI Cycling Coach.
    """

    data = get_registered_athlete_data(athlete_id)

    height = data.get("height")

    if height is not None:
        # Intervals.icu возвращает рост в метрах.
        # В проекте используем сантиметры.
        height = round(height * 100)

    ftp = data.get("ftp")
    weight = data.get("weight")

    ftp_per_kg = None

    if ftp is not None and weight is not None and weight > 0:
        ftp_per_kg = round(ftp / weight, 2)

    return {
        "athlete_id": str(data["id"]),
        "name": data.get("name"),
        "weight": weight,
        "height": height,
        "ftp": ftp,
        "indoor_ftp": data.get("indoor_ftp"),
        "ftp_per_kg": ftp_per_kg,
        "lthr": data.get("lthr"),
        "max_heart_rate": data.get("max_hr"),
        "power_zones": data.get("power_zones"),
        "power_zone_names": data.get("power_zone_names"),
        "hr_zones": data.get("hr_zones"),
        "hr_zone_names": data.get("hr_zone_names"),
    }


def get_registered_athlete_wellness(athlete_id, days=30):
    """
    Получает данные восстановления конкретного спортсмена
    из Intervals.icu с использованием его сохранённого API-ключа.
    """

    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    api_key = get_stored_api_key(
        athlete_id=str(athlete_id),
        provider="intervals"
    )

    if api_key is None:
        raise ValueError("Для спортсмена не найден API-ключ Intervals.icu")

    return get_intervals_wellness(
        days=days,
        api_key=api_key
    )


def get_registered_athlete_activities(athlete_id, days=30):
    """
    Загружает Garmin-активности конкретного спортсмена
    по его индивидуальному API-ключу.
    """

    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    api_key = get_stored_api_key(
        athlete_id=str(athlete_id),
        provider="garmin"
    )

    if api_key is None:
        raise ValueError("Для спортсмена не найден API-ключ Garmin")

    return get_garmin_activities(
        days=days,
        api_key=api_key
    )
