
import json
from unittest.mock import patch

from src.assistant.weekly_planner import (
    generate_weekly_adaptation,
)


def build_context():
    return {
        "athlete": {
            "profile": {
                "name": "Test Athlete",
                "ftp": 304
            },
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
            "week_start": "2099-01-05",
            "goal_description": "Подготовка к шоссейной гонке",
            "workouts": [
                {
                    "id": 10,
                    "date": "2099-01-06",
                    "status": "planned",
                    "current_workout": {
                        "date": "2099-01-06",
                        "type": "Endurance",
                        "duration_minutes": 60,
                        "power_zone": "Endurance",
                        "purpose": "Аэробная работа"
                    }
                }
            ]
        }
    }


def test_gemma_keep():
    response = {
        "decision": "keep",
        "explanation": "План соответствует состоянию спортсмена",
        "changes": []
    }

    with patch(
        "src.assistant.llm.ask_gemma",
        return_value=json.dumps(response, ensure_ascii=False)
    ) as mock_gemma:
        result = generate_weekly_adaptation(build_context())

    assert result["decision"] == "keep"
    assert result["changes"] == []
    mock_gemma.assert_called_once()

    print("GEMMA KEEP INTEGRATION TEST PASSED")


def test_gemma_adapt():
    response = {
        "decision": "adapt",
        "explanation": "Требуется снизить нагрузку",
        "changes": [
            {
                "workout_id": 10,
                "new_workout": {
                    "date": "2099-01-06",
                    "type": "rest",
                    "duration_minutes": None,
                    "power_zone": None,
                    "power_range_watts": None,
                    "purpose": "Восстановление"
                },
                "change_reason": "Недостаточное восстановление",
                "impact_on_goal": "Временное снижение нагрузки"
            }
        ]
    }

    with patch(
        "src.assistant.llm.ask_gemma",
        return_value=json.dumps(response, ensure_ascii=False)
    ):
        result = generate_weekly_adaptation(build_context())

    assert result["decision"] == "adapt"
    assert result["changes"][0]["new_workout"]["type"] == "rest"

    print("GEMMA ADAPT INTEGRATION TEST PASSED")


def test_gemma_invalid_response():
    response = {
        "decision": "invalid",
        "explanation": "Некорректное решение",
        "changes": []
    }

    with patch(
        "src.assistant.llm.ask_gemma",
        return_value=json.dumps(response, ensure_ascii=False)
    ):
        try:
            generate_weekly_adaptation(build_context())
        except ValueError:
            print("GEMMA INVALID RESPONSE TEST PASSED")
        else:
            raise AssertionError(
                "Некорректное решение Gemma не было отклонено"
            )


if __name__ == "__main__":
    test_gemma_keep()
    test_gemma_adapt()
    test_gemma_invalid_response()

    print("Все тесты интеграции Gemma пройдены!")
