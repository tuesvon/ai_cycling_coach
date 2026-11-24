import sqlite3

from datetime import date, datetime, timezone

from src.athletes.credentials import (
    DATABASE_PATH,
    initialize_database,
)



def initialize_training_goals_table():
    """
    Создаёт таблицу главных целей спортсменов.
    """
    initialize_database()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS training_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                distance_km REAL,
                elevation_m INTEGER,
                target_result TEXT,
                weekly_hours REAL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()

    finally:
        connection.close()


def create_training_goal(
    athlete_id,
    event_name,
    event_date,
    event_type,
    distance_km=None,
    elevation_m=None,
    target_result=None,
    weekly_hours=None,
    description=None,
):
    """
    Сохраняет главную цель спортсмена.
    """
    initialize_training_goals_table()

    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise ValueError("Не указан спортсмен")

    if not isinstance(event_name, str) or not event_name.strip():
        raise ValueError("Не указано название соревнования")

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("Не указан тип соревнования")

    if isinstance(event_date, str):
        try:
            parsed_date = date.fromisoformat(event_date)
        except ValueError as error:
            raise ValueError(
                "Дата должна быть в формате YYYY-MM-DD"
            ) from error

    elif isinstance(event_date, date) and not isinstance(
        event_date, datetime
    ):
        parsed_date = event_date

    else:
        raise ValueError("Некорректная дата соревнования")

    if parsed_date < date.today():
        raise ValueError("Дата соревнования уже прошла")

    for field_name, value in (
        ("distance_km", distance_km),
        ("elevation_m", elevation_m),
        ("weekly_hours", weekly_hours),
    ):
        if value is not None:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < value < float("inf")
            ):
                raise ValueError(
                    f"{field_name} должен быть положительным числом"
                )

    if elevation_m is not None and (
        not isinstance(elevation_m, int)
        or isinstance(elevation_m, bool)
    ):
        raise ValueError(
            "elevation_m должен быть целым числом"
        )

    for field_name, value in (
        ("target_result", target_result),
        ("description", description),
    ):
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"{field_name} должен быть строкой"
            )

    created_at = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.execute(
            """
            INSERT INTO training_goals (
                athlete_id,
                event_name,
                event_date,
                event_type,
                distance_km,
                elevation_m,
                target_result,
                weekly_hours,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                athlete_id.strip(),
                event_name.strip(),
                parsed_date.isoformat(),
                event_type.strip(),
                distance_km,
                elevation_m,
                target_result,
                weekly_hours,
                description,
                created_at,
            ),
        )

        goal_id = cursor.lastrowid

        connection.commit()

        return goal_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def get_training_goal(goal_id):
    """
    Возвращает сохранённую цель по её ID.
    """
    initialize_training_goals_table()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM training_goals WHERE id = ?",
            (goal_id,),
        ).fetchone()

        return dict(row) if row is not None else None

    finally:
        connection.close()



def get_active_training_goals(athlete_id):
    """
    Возвращает активные цели спортсмена.
    """
    initialize_training_goals_table()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT *
            FROM training_goals
            WHERE athlete_id = ?
              AND status = 'active'
            ORDER BY event_date ASC
            """,
            (athlete_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()