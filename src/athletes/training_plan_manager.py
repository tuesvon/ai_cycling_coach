import json
import sqlite3
from datetime import datetime, timezone

from src.athletes.credentials import DATABASE_PATH, initialize_database


def initialize_training_plans_table():
    """Создаёт таблицы недельных планов и тренировок."""
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS weekly_training_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id TEXT NOT NULL,
                week_start TEXT NOT NULL,
                goal_description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                UNIQUE(athlete_id, week_start)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS planned_workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekly_plan_id INTEGER NOT NULL,
                workout_date TEXT NOT NULL,
                original_workout TEXT NOT NULL,
                current_workout TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                change_reason TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (weekly_plan_id)
                    REFERENCES weekly_training_plans(id)
                    ON DELETE CASCADE,
                UNIQUE(weekly_plan_id, workout_date)
            )
        """)


def create_weekly_plan(athlete_id, week_start, workouts, goal_description=None):
    """Сохраняет недельный план с первоначальными тренировками."""
    initialize_training_plans_table()

    if len(workouts) != 7:
        raise ValueError("Недельный план должен содержать ровно 7 дней")

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute("""
            INSERT INTO weekly_training_plans (
                athlete_id, week_start, goal_description, created_at
            )
            VALUES (?, ?, ?, ?)
        """, (athlete_id, week_start, goal_description, now))

        plan_id = cursor.lastrowid

        for workout in workouts:
            connection.execute("""
                INSERT INTO planned_workouts (
                    weekly_plan_id,
                    workout_date,
                    original_workout,
                    current_workout,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                plan_id,
                workout["date"],
                json.dumps(workout, ensure_ascii=False),
                json.dumps(workout, ensure_ascii=False),
                now
            ))

    return plan_id


def get_weekly_plan(plan_id):
    """Возвращает недельный план и все его тренировки."""
    initialize_training_plans_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        plan = connection.execute("""
            SELECT *
            FROM weekly_training_plans
            WHERE id = ?
        """, (plan_id,)).fetchone()

        if plan is None:
            return None

        workouts = connection.execute("""
            SELECT *
            FROM planned_workouts
            WHERE weekly_plan_id = ?
            ORDER BY workout_date
        """, (plan_id,)).fetchall()

    result = dict(plan)
    result["workouts"] = []

    for row in workouts:
        workout = dict(row)
        workout["original_workout"] = json.loads(workout["original_workout"])
        workout["current_workout"] = json.loads(workout["current_workout"])
        result["workouts"].append(workout)

    return result


def initialize_workout_revisions_table():
    """Создаёт таблицу истории изменений тренировок."""
    initialize_training_plans_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS workout_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                previous_workout TEXT NOT NULL,
                new_workout TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                impact_on_goal TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workout_id)
                    REFERENCES planned_workouts(id)
                    ON DELETE CASCADE
            )
        """)


def adapt_planned_workout(
    workout_id,
    new_workout,
    change_reason,
    impact_on_goal
):
    """
    Изменяет запланированную тренировку и сохраняет
    предыдущую версию в истории.
    """
    initialize_workout_revisions_table()

    if not isinstance(new_workout, dict):
        raise ValueError("Новая тренировка должна быть словарём")

    if not isinstance(change_reason, str) or not change_reason.strip():
        raise ValueError("Необходимо указать причину изменения")

    if not isinstance(impact_on_goal, str) or not impact_on_goal.strip():
        raise ValueError("Необходимо указать влияние на цель")

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        existing = connection.execute("""
            SELECT current_workout
            FROM planned_workouts
            WHERE id = ?
        """, (workout_id,)).fetchone()

        if existing is None:
            raise ValueError("Запланированная тренировка не найдена")

        previous_workout = json.loads(existing["current_workout"])

        connection.execute("""
            INSERT INTO workout_revisions (
                workout_id,
                previous_workout,
                new_workout,
                change_reason,
                impact_on_goal,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            workout_id,
            json.dumps(previous_workout, ensure_ascii=False),
            json.dumps(new_workout, ensure_ascii=False),
            change_reason,
            impact_on_goal,
            now
        ))

        connection.execute("""
            UPDATE planned_workouts
            SET current_workout = ?,
                change_reason = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(new_workout, ensure_ascii=False),
            change_reason,
            now,
            workout_id
        ))


def get_workout_revisions(workout_id):
    """Возвращает историю изменений тренировки."""
    initialize_workout_revisions_table()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT *
            FROM workout_revisions
            WHERE workout_id = ?
            ORDER BY id
        """, (workout_id,)).fetchall()

    revisions = []

    for row in rows:
        revision = dict(row)
        revision["previous_workout"] = json.loads(
            revision["previous_workout"]
        )
        revision["new_workout"] = json.loads(
            revision["new_workout"]
        )
        revisions.append(revision)

    return revisions


def adapt_weekly_plan(plan_id, changes):
    """
    Применяет несколько изменений тренировок одной транзакцией.

    changes = [
        {
            "workout_id": 123,
            "new_workout": {...},
            "change_reason": "...",
            "impact_on_goal": "..."
        }
    ]
    """
    initialize_workout_revisions_table()

    if not isinstance(changes, list) or not changes:
        raise ValueError("Необходим непустой список изменений")

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        plan = connection.execute(
            "SELECT id FROM weekly_training_plans WHERE id = ?",
            (plan_id,)
        ).fetchone()

        if plan is None:
            raise ValueError("Недельный план не найден")

        # Сначала проверяем ВСЕ изменения.
        prepared_changes = []
        seen_workout_ids = set()

        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Изменение должно быть словарём")

            workout_id = change.get("workout_id")
            new_workout = change.get("new_workout")
            reason = change.get("change_reason")
            impact = change.get("impact_on_goal")

            if type(workout_id) is not int:
                raise ValueError("workout_id должен быть целым числом")

            if workout_id in seen_workout_ids:
                raise ValueError(
                    "Одна тренировка не может изменяться дважды "
                    "в одном пересмотре"
                )

            seen_workout_ids.add(workout_id)

            if not isinstance(new_workout, dict):
                raise ValueError("new_workout должен быть словарём")

            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("Не указана причина изменения")

            if not isinstance(impact, str) or not impact.strip():
                raise ValueError("Не указано влияние на цель")

            existing = connection.execute("""
                SELECT id, workout_date, current_workout
                FROM planned_workouts
                WHERE id = ? AND weekly_plan_id = ?
            """, (workout_id, plan_id)).fetchone()

            if existing is None:
                raise ValueError(
                    f"Тренировка {workout_id} не принадлежит плану {plan_id}"
                )

            if new_workout.get("date") != existing["workout_date"]:
                raise ValueError(
                    f"Нельзя изменить дату тренировки {workout_id}"
                )

            prepared_changes.append({
                "workout_id": workout_id,
                "previous_workout": existing["current_workout"],
                "new_workout": json.dumps(
                    new_workout, ensure_ascii=False
                ),
                "reason": reason.strip(),
                "impact": impact.strip()
            })

        # Все изменения проверены. Теперь сохраняем.
        for change in prepared_changes:
            connection.execute("""
                INSERT INTO workout_revisions (
                    workout_id,
                    previous_workout,
                    new_workout,
                    change_reason,
                    impact_on_goal,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                change["workout_id"],
                change["previous_workout"],
                change["new_workout"],
                change["reason"],
                change["impact"],
                now
            ))

            connection.execute("""
                UPDATE planned_workouts
                SET current_workout = ?,
                    change_reason = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                change["new_workout"],
                change["reason"],
                now,
                change["workout_id"]
            ))

    return len(prepared_changes)