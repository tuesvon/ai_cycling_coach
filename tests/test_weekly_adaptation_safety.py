
from copy import deepcopy

from src.assistant.weekly_adaptation_validator import (
    validate_weekly_adaptation,
)


def build_context():
    return {
        "athlete": {
            "power_zones_watts": [
                {
                    "zone": 2,
                    "name": "Endurance",
                    "min_watts": 168,
                    "max_watts": 228
                }
            ]
        },
        "weekly_plan": {
            "id": 1,
            "workouts": [
                {
                    "id": 10,
                    "date": "2026-11-24",
                    "status": "planned",
                    "current_workout": {
                        "date": "2026-11-24",
                        "type": "Endurance",
                        "duration_minutes": 60,
                        "power_zone": "Endurance",
                        "purpose": "Аэробная работа"
                    }
                }
            ]
        }
    }


def build_decision():
    return {
        "decision": "adapt",
        "explanation": "Требуется дополнительное восстановление",
        "changes": [
            {
                "workout_id": 10,
                "new_workout": {
                    "date": "2026-11-24",
                    "type": "rest",
                    "duration_minutes": None,
                    "power_zone": None,
                    "purpose": "Восстановление"
                },
                "change_reason": "Недостаточный сон",
                "impact_on_goal": "Нагрузка временно снижена"
            }
        ]
    }


def expect_rejection(decision, context, today):
    try:
        validate_weekly_adaptation(
            decision,
            context,
            today=today
        )
    except ValueError:
        return

    raise AssertionError("Некорректное изменение принято")


def test_future_workout():
    result = validate_weekly_adaptation(
        build_decision(),
        build_context(),
        today="2026-11-23"
    )

    assert result["decision"] == "adapt"
    print("FUTURE WORKOUT TEST PASSED")


def test_past_workout():
    expect_rejection(
        build_decision(),
        build_context(),
        today="2026-11-25"
    )

    print("PAST WORKOUT TEST PASSED")


def test_completed_workout():
    context = build_context()
    context["weekly_plan"]["workouts"][0]["status"] = "completed"

    expect_rejection(
        build_decision(),
        context,
        today="2026-11-23"
    )

    print("COMPLETED WORKOUT TEST PASSED")


def test_invalid_status():
    context = deepcopy(build_context())
    context["weekly_plan"]["workouts"][0]["status"] = "cancelled"

    expect_rejection(
        build_decision(),
        context,
        today="2026-11-23"
    )

    print("INVALID STATUS TEST PASSED")


if __name__ == "__main__":
    test_future_workout()
    test_past_workout()
    test_completed_workout()
    test_invalid_status()

    print("Все тесты безопасности недельного плана пройдены!")
