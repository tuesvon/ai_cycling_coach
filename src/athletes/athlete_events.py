
import sqlite3
import uuid

from datetime import date, datetime, timezone

from src.athletes.athlete_manager import get_athlete


DB_PATH = "data/athletes.db"


EVENT_TYPES = {
    "vacation",
    "illness",
    "business_trip",
    "planned_rest",
    "alcohol",
    "late_night",
    "other",
}


def validate_event_dates(start_date, end_date):
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        raise ValueError("Даты должны быть в формате YYYY-MM-DD")

    if end < start:
        raise ValueError(
            "Дата окончания не может быть раньше даты начала"
        )


def add_athlete_event(
    athlete_id,
    event_type,
    start_date,
    end_date=None,
    description=None
):
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Неизвестный тип события: {event_type}")

    if end_date is None:
        end_date = start_date

    validate_event_dates(start_date, end_date)

    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    event = {
        "event_id": str(uuid.uuid4()),
        "athlete_id": str(athlete_id),
        "event_type": event_type,
        "start_date": start_date,
        "end_date": end_date,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO athlete_events (
                event_id,
                athlete_id,
                event_type,
                start_date,
                end_date,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["athlete_id"],
                event["event_type"],
                event["start_date"],
                event["end_date"],
                event["description"],
                event["created_at"],
            )
        )

    return event


def get_athlete_events(
    athlete_id,
    start_date=None,
    end_date=None
):
    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    query = """
        SELECT
            event_id,
            athlete_id,
            event_type,
            start_date,
            end_date,
            description,
            created_at
        FROM athlete_events
        WHERE athlete_id = ?
    """

    params = [str(athlete_id)]

    if start_date:
        query += " AND end_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND start_date <= ?"
        params.append(end_date)

    query += " ORDER BY start_date"

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            query,
            params
        ).fetchall()

    return [dict(row) for row in rows]


def update_athlete_event(
    athlete_id,
    event_id,
    event_type=None,
    start_date=None,
    end_date=None,
    description=None
):
    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM athlete_events
            WHERE event_id = ? AND athlete_id = ?
            """,
            (event_id, str(athlete_id))
        ).fetchone()

        if row is None:
            raise ValueError("Событие не найдено")

        event = dict(row)

        new_type = event_type if event_type is not None else event["event_type"]
        new_start = start_date if start_date is not None else event["start_date"]
        new_end = end_date if end_date is not None else event["end_date"]
        new_description = (
            description if description is not None
            else event["description"]
        )

        if new_type not in EVENT_TYPES:
            raise ValueError(f"Неизвестный тип события: {new_type}")

        validate_event_dates(new_start, new_end)

        connection.execute(
            """
            UPDATE athlete_events
            SET event_type = ?,
                start_date = ?,
                end_date = ?,
                description = ?
            WHERE event_id = ? AND athlete_id = ?
            """,
            (
                new_type,
                new_start,
                new_end,
                new_description,
                event_id,
                str(athlete_id)
            )
        )

    return get_athlete_events(athlete_id)


def delete_athlete_event(athlete_id, event_id):
    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            DELETE FROM athlete_events
            WHERE event_id = ? AND athlete_id = ?
            """,
            (event_id, str(athlete_id))
        )

        if cursor.rowcount == 0:
            raise ValueError("Событие не найдено")

    return True
