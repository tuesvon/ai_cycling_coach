from datetime import date, timedelta
from uuid import uuid4

from src.athletes.training_plan_manager import (
    create_weekly_plan,
    get_weekly_plan,
)


def test_create_weekly_plan():
    athlete_id = f"test_{uuid4().hex}"
    monday = date(2026, 11, 23)

    workouts = []

    for day in range(7):
        workout_date = monday + timedelta(days=day)

        workouts.append({
            "date": workout_date.isoformat(),
            "type": "Endurance" if day % 2 else "rest",
            "duration_minutes": 60 if day % 2 else None,
            "power_zone": "Endurance" if day % 2 else None,
            "purpose": "Развитие аэробной выносливости"
        })

    plan_id = create_weekly_plan(
        athlete_id=athlete_id,
        week_start=monday.isoformat(),
        workouts=workouts,
        goal_description="Подготовка к шоссейной гонке"
    )

    plan = get_weekly_plan(plan_id)

    assert plan is not None
    assert plan["athlete_id"] == athlete_id
    assert plan["week_start"] == monday.isoformat()
    assert len(plan["workouts"]) == 7

    for index, workout in enumerate(plan["workouts"]):
        assert workout["original_workout"] == workouts[index]
        assert workout["current_workout"] == workouts[index]

    print("CREATE WEEKLY PLAN TEST PASSED")


if __name__ == "__main__":
    test_create_weekly_plan()
    print("Все тесты недельного плана пройдены!")