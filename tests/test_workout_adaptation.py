
from datetime import date, timedelta
from uuid import uuid4

from src.athletes.training_plan_manager import (
    create_weekly_plan,
    get_weekly_plan,
    adapt_planned_workout,
    get_workout_revisions,
)


def test_workout_adaptation():
    athlete_id = f"test_{uuid4().hex}"
    monday = date(2026, 11, 23)

    workouts = []

    for day in range(7):
        workout_date = monday + timedelta(days=day)

        workouts.append({
            "date": workout_date.isoformat(),
            "type": "Threshold" if day == 1 else "Endurance",
            "duration_minutes": 60,
            "power_zone": "Threshold" if day == 1 else "Endurance",
            "purpose": "Развитие пороговой мощности"
            if day == 1 else "Аэробная работа"
        })

    plan_id = create_weekly_plan(
        athlete_id=athlete_id,
        week_start=monday.isoformat(),
        workouts=workouts,
        goal_description="Подготовка к шоссейной гонке"
    )

    plan = get_weekly_plan(plan_id)

    tuesday = plan["workouts"][1]
    workout_id = tuesday["id"]

    original_workout = tuesday["original_workout"]

    new_workout = {
        "date": tuesday["workout_date"],
        "type": "rest",
        "duration_minutes": None,
        "power_zone": None,
        "purpose": "Восстановление после накопленной усталости"
    }

    adapt_planned_workout(
        workout_id=workout_id,
        new_workout=new_workout,
        change_reason="Недостаточный сон и признаки неполного восстановления",
        impact_on_goal=(
            "Пороговая тренировка пропущена, но долгосрочная "
            "цель подготовки сохраняется"
        )
    )

    updated_plan = get_weekly_plan(plan_id)
    updated_tuesday = updated_plan["workouts"][1]

    assert updated_tuesday["original_workout"] == original_workout
    assert updated_tuesday["current_workout"] == new_workout

    revisions = get_workout_revisions(workout_id)

    assert len(revisions) == 1
    assert revisions[0]["previous_workout"] == original_workout
    assert revisions[0]["new_workout"] == new_workout
    assert revisions[0]["change_reason"]
    assert revisions[0]["impact_on_goal"]

    print("WORKOUT ADAPTATION TEST PASSED")


if __name__ == "__main__":
    test_workout_adaptation()
    print("Все тесты адаптации тренировок пройдены!")