from datetime import date, timedelta

from src.assistant.weekly_planner import (
    build_weekly_planning_context,
    build_weekly_adaptation_prompt,
)


def test_weekly_planning_context():
    monday = date(2026, 11, 23)

    analysis = {
        "profile": {
            "name": "Test Athlete",
            "ftp": 304,
            "power_zones": [55, 75, 90, 105, 120, 150, 999],
            "power_zone_names": [
                "Active Recovery", "Endurance", "Tempo",
                "Threshold", "VO2 Max", "Anaerobic",
                "Neuromuscular"
            ]
        },
        "readiness": {
            "overall": "mixed"
        },
        "capabilities": {
            "power_measurement_available": True,
            "power_source": None,
            "has_indoor_trainer": False,
            "has_heart_rate_monitor": True,
            "has_cadence_sensor": False
        }
    }

    workouts = []

    for day in range(7):
        workout_date = (monday + timedelta(days=day)).isoformat()

        workout = {
            "date": workout_date,
            "type": "Threshold" if day == 1 else "Endurance",
            "duration_minutes": 60,
            "power_zone": "Threshold" if day == 1 else "Endurance",
            "purpose": "Тренировка по плану"
        }

        workouts.append({
            "id": day + 1,
            "workout_date": workout_date,
            "status": "planned",
            "original_workout": workout.copy(),
            "current_workout": workout.copy()
        })

    weekly_plan = {
        "id": 1,
        "week_start": monday.isoformat(),
        "goal_description": "Подготовка к шоссейной гонке",
        "workouts": workouts
    }

    context = build_weekly_planning_context(analysis, weekly_plan)

    assert context["weekly_plan"]["id"] == 1
    assert len(context["weekly_plan"]["workouts"]) == 7
    assert context["athlete"]["capabilities"]["power_measurement_available"]

    prompt = build_weekly_adaptation_prompt(context)

    assert "Test Athlete" in prompt
    assert "Threshold" in prompt
    assert "Подготовка к шоссейной гонке" in prompt
    assert "power_zones_watts" in prompt

    print("WEEKLY PLANNING CONTEXT TEST PASSED")


if __name__ == "__main__":
    test_weekly_planning_context()
    print("Все тесты контекста недельного планирования пройдены!")