from datetime import date, timedelta
from uuid import uuid4

from src.athletes.training_plan_manager import (
    create_weekly_plan,
    get_weekly_plan,
    adapt_weekly_plan,
    get_workout_revisions,
)


def test_weekly_plan_adaptation():
    athlete_id = f"test_{uuid4().hex}"
    monday = date(2026, 11, 23)

    workouts = []

    for day in range(7):
        current_date = (monday + timedelta(days=day)).isoformat()

        workouts.append({
            "date": current_date,
            "type": "Threshold" if day == 1 else "Endurance",
            "duration_minutes": 60,
            "power_zone": "Threshold" if day == 1 else "Endurance",
            "purpose": "Тренировка по плану"
        })

    plan_id = create_weekly_plan(
        athlete_id=athlete_id,
        week_start=monday.isoformat(),
        workouts=workouts,
        goal_description="Подготовка к гонке"
    )

    plan = get_weekly_plan(plan_id)

    tuesday = plan["workouts"][1]
    thursday = plan["workouts"][3]

    changes = [
        {
            "workout_id": tuesday["id"],
            "new_workout": {
                "date": tuesday["workout_date"],
                "type": "rest",
                "duration_minutes": None,
                "power_zone": None,
                "purpose": "Восстановление"
            },
            "change_reason": "Недостаточное восстановление",
            "impact_on_goal": "Пороговая работа перенесена"
        },
        {
            "workout_id": thursday["id"],
            "new_workout": {
                "date": thursday["workout_date"],
                "type": "Threshold",
                "duration_minutes": 60,
                "power_zone": "Threshold",
                "purpose": "Перенесённая пороговая тренировка"
            },
            "change_reason": "Перенос тренировки со вторника",
            "impact_on_goal": "Ключевая работа недели сохранена"
        }
    ]

    count = adapt_weekly_plan(plan_id, changes)

    assert count == 2

    updated = get_weekly_plan(plan_id)

    assert updated["workouts"][1]["current_workout"]["type"] == "rest"
    assert updated["workouts"][3]["current_workout"]["type"] == "Threshold"

    assert updated["workouts"][1]["original_workout"] == workouts[1]
    assert updated["workouts"][3]["original_workout"] == workouts[3]

    assert len(get_workout_revisions(tuesday["id"])) == 1
    assert len(get_workout_revisions(thursday["id"])) == 1

    print("WEEKLY PLAN ADAPTATION TEST PASSED")


def test_atomic_rollback():
    athlete_id = f"test_{uuid4().hex}"
    monday = date(2026, 11, 23)

    workouts = [
        {
            "date": (monday + timedelta(days=day)).isoformat(),
            "type": "Endurance",
            "duration_minutes": 60,
            "power_zone": "Endurance",
            "purpose": "Аэробная работа"
        }
        for day in range(7)
    ]

    plan_id = create_weekly_plan(
        athlete_id=athlete_id,
        week_start=monday.isoformat(),
        workouts=workouts
    )

    plan = get_weekly_plan(plan_id)
    first = plan["workouts"][0]
    second = plan["workouts"][1]

    changes = [
        {
            "workout_id": first["id"],
            "new_workout": {
                **first["current_workout"],
                "type": "rest",
                "power_zone": None
            },
            "change_reason": "Нужен отдых",
            "impact_on_goal": "Нагрузка снижена"
        },
        {
            "workout_id": second["id"],
            "new_workout": {
                **second["current_workout"],
                "date": "2099-01-01"
            },
            "change_reason": "Некорректный перенос",
            "impact_on_goal": "Проверка отката"
        }
    ]

    try:
        adapt_weekly_plan(plan_id, changes)
    except ValueError:
        pass
    else:
        raise AssertionError("Некорректное изменение не было отклонено")

    updated = get_weekly_plan(plan_id)

    assert updated["workouts"][0]["current_workout"] == workouts[0]
    assert updated["workouts"][1]["current_workout"] == workouts[1]

    assert get_workout_revisions(first["id"]) == []
    assert get_workout_revisions(second["id"]) == []

    print("ATOMIC ROLLBACK TEST PASSED")


if __name__ == "__main__":
    test_weekly_plan_adaptation()
    test_atomic_rollback()
    print("Все тесты пакетной адаптации пройдены!")