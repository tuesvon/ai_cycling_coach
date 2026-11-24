
from copy import deepcopy

from src.assistant.weekly_adaptation_validator import (
    validate_weekly_adaptation,
)


def build_test_context():
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
                        "type": "Threshold",
                        "duration_minutes": 60,
                        "power_zone": "Threshold",
                        "purpose": "Пороговая работа"
                    }
                }
            ]
        }
    }


def test_keep_plan():
    decision = {
        "decision": "keep",
        "explanation": "Текущий план соответствует состоянию спортсмена",
        "changes": []
    }

    result = validate_weekly_adaptation(
        decision,
        build_test_context()
    )

    assert result["decision"] == "keep"
    print("KEEP PLAN TEST PASSED")


def test_adapt_plan():
    decision = {
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
                "change_reason": "Недостаточное восстановление",
                "impact_on_goal": "Интенсивная работа будет пересмотрена"
            }
        ]
    }

    result = validate_weekly_adaptation(
        decision,
        build_test_context()
    )

    assert result["decision"] == "adapt"
    assert result["changes"][0]["new_workout"]["type"] == "rest"

    print("ADAPT PLAN TEST PASSED")


def test_invalid_workout_id():
    decision = {
        "decision": "adapt",
        "explanation": "Изменение расписания",
        "changes": [
            {
                "workout_id": 999,
                "new_workout": {
                    "date": "2026-11-24",
                    "type": "rest",
                    "duration_minutes": None,
                    "power_zone": None,
                    "purpose": "Восстановление"
                },
                "change_reason": "Усталость",
                "impact_on_goal": "Нагрузка снижена"
            }
        ]
    }

    try:
        validate_weekly_adaptation(decision, build_test_context())
    except ValueError:
        print("INVALID WORKOUT ID TEST PASSED")
    else:
        raise AssertionError("Неизвестный workout_id не был отклонён")



def test_invalid_power_zone():
    decision = {
        "decision": "adapt",
        "explanation": "Изменение интенсивности",
        "changes": [
            {
                "workout_id": 10,
                "new_workout": {
                    "date": "2026-11-24",
                    "type": "VO2 Max",
                    "duration_minutes": 60,
                    "power_zone": "Unknown Zone",
                    "purpose": "Интенсивная работа"
                },
                "change_reason": "Корректировка нагрузки",
                "impact_on_goal": "Изменение тренировочного стимула"
            }
        ]
    }

    try:
        validate_weekly_adaptation(
            decision,
            build_test_context(),
            today="2026-11-23"
        )
    except ValueError:
        print("INVALID POWER ZONE TEST PASSED")
    else:
        raise AssertionError(
            "Неизвестная зона мощности не была отклонена"
        )


if __name__ == "__main__":
    test_keep_plan()
    test_adapt_plan()
    test_invalid_workout_id()
    test_invalid_power_zone()
    print("Все тесты недельного валидатора пройдены!")
