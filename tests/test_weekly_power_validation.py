
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
                },
                {
                    "zone": 4,
                    "name": "Threshold",
                    "min_watts": 274,
                    "max_watts": 319
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


def build_decision(power_range):
    return {
        "decision": "adapt",
        "explanation": "Корректировка тренировочной нагрузки",
        "changes": [
            {
                "workout_id": 10,
                "new_workout": {
                    "date": "2026-11-24",
                    "type": "Endurance",
                    "duration_minutes": 60,
                    "power_zone": "Endurance",
                    "power_range_watts": power_range,
                    "purpose": "Аэробная выносливость"
                },
                "change_reason": "Адаптация нагрузки",
                "impact_on_goal": "Поддержание аэробной формы"
            }
        ]
    }


def test_valid_power_range():
    result = validate_weekly_adaptation(
        build_decision("168-228"),
        build_context(),
        today="2026-11-23"
    )

    assert result["decision"] == "adapt"
    print("VALID POWER RANGE TEST PASSED")


def test_invalid_power_range():
    try:
        validate_weekly_adaptation(
            build_decision("250-300"),
            build_context(),
            today="2026-11-23"
        )
    except ValueError:
        print("INVALID POWER RANGE TEST PASSED")
    else:
        raise AssertionError(
            "Некорректный диапазон мощности был принят"
        )


def test_optional_power_range():
    decision = build_decision(None)

    result = validate_weekly_adaptation(
        decision,
        build_context(),
        today="2026-11-23"
    )

    assert result["decision"] == "adapt"
    print("OPTIONAL POWER RANGE TEST PASSED")


def test_rest_with_power_range():
    decision = build_decision("168-228")
    workout = decision["changes"][0]["new_workout"]

    workout["type"] = "rest"
    workout["duration_minutes"] = None
    workout["power_zone"] = None

    try:
        validate_weekly_adaptation(
            decision,
            build_context(),
            today="2026-11-23"
        )
    except ValueError:
        print("REST POWER RANGE TEST PASSED")
    else:
        raise AssertionError(
            "Отдых с диапазоном мощности был принят"
        )


if __name__ == "__main__":
    test_valid_power_range()
    test_invalid_power_range()
    test_optional_power_range()
    test_rest_with_power_range()

    print("Все тесты диапазонов мощности пройдены!")
