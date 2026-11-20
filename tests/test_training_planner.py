from src.assistant.training_planner import (
    extract_json,
    validate_training_decision,
    build_training_decision_prompt
)


def test_extract_json():
    response = """
    ```json
    {
        "today": {
            "decision": "rest",
            "reason": "Недостаточное восстановление",
            "workout_focus": "rest",
            "intensity": "rest"
        },
        "next_days": [
            {
                "day": "tomorrow",
                "recommendation": "Endurance",
                "duration_minutes": 60,
                "power_zone": "Endurance",
                "power_range_watts": "168-228",
                "intensity": "easy",
                "purpose": "Аэробная работа",
                "conditions": "Если восстановление улучшится"
            },
            {
                "day": "day_after_tomorrow",
                "recommendation": "Recovery",
                "duration_minutes": 40,
                "power_zone": "Active Recovery",
                "power_range_watts": "1-167",
                "intensity": "recovery",
                "purpose": "Восстановление",
                "conditions": "Если сохраняется усталость"
            }
        ]
    }
    ```
    """

    result = extract_json(response)

    assert result["today"]["decision"] == "rest"
    assert len(result["next_days"]) == 2

    print("\n=== JSON EXTRACTION TEST PASSED ===")


def test_validate_training_decision():
    data = {
        "today": {
            "decision": "training",
            "reason": "Состояние позволяет выполнить лёгкую работу",
            "workout_focus": "Endurance",
            "intensity": "easy"
        },
        "next_days": [
            {
                "day": "tomorrow",
                "recommendation": "Endurance",
                "duration_minutes": 60,
                "power_zone": "Endurance",
                "power_range_watts": "168-228",
                "intensity": "easy",
                "purpose": "Аэробная работа",
                "conditions": "При нормальном восстановлении"
            },
            {
                "day": "day_after_tomorrow",
                "recommendation": "Recovery",
                "duration_minutes": 40,
                "power_zone": "Active Recovery",
                "power_range_watts": "1-167",
                "intensity": "recovery",
                "purpose": "Восстановление",
                "conditions": "При наличии усталости"
            }
        ]
    }

    power_zones = [
        {
            "zone": 1,
            "name": "Active Recovery",
            "min_watts": 1,
            "max_watts": 167
        },
        {
            "zone": 2,
            "name": "Endurance",
            "min_watts": 168,
            "max_watts": 228
        },
        {
            "zone": 3,
            "name": "Tempo",
            "min_watts": 229,
            "max_watts": 273
        },
        {
            "zone": 4,
            "name": "Threshold",
            "min_watts": 274,
            "max_watts": 319
        },
        {
            "zone": 5,
            "name": "VO2 Max",
            "min_watts": 320,
            "max_watts": 364
        },
        {
            "zone": 6,
            "name": "Anaerobic",
            "min_watts": 365,
            "max_watts": 456
        },
        {
            "zone": 7,
            "name": "Neuromuscular",
            "min_watts": 457,
            "max_watts": None
        }
    ]

    result = validate_training_decision(
        data,
        power_zones=power_zones
    )

    assert result["today"]["decision"] == "training"
    assert result["next_days"][0]["day"] == "tomorrow"
    assert result["next_days"][1]["day"] == "day_after_tomorrow"

    print("\n=== DECISION VALIDATION TEST PASSED ===")


def test_invalid_decision():
    data = {
        "today": {
            "decision": "maybe",
            "reason": "Неопределённость",
            "workout_focus": "unknown",
            "intensity": "easy"
        },
        "next_days": []
    }

    try:
        validate_training_decision(data)
    except ValueError:
        print("\n=== INVALID DECISION TEST PASSED ===")
    else:
        raise AssertionError("Некорректное решение не было отклонено")


def test_build_prompt():
    analysis = {
        "profile": {
            "name": "Test Athlete",
            "ftp": 304,
            "power_zones": [55, 75, 90, 105, 120, 150, 999],
            "power_zone_names": [
                "Active Recovery",
                "Endurance",
                "Tempo",
                "Threshold",
                "VO2 Max",
                "Anaerobic",
                "Neuromuscular"
            ]
        },
        "readiness": {
            "overall": "mixed"
        }
    }

    prompt = build_training_decision_prompt(analysis)

    assert "Test Athlete" in prompt
    assert "cycling_training_load" in prompt
    assert "power_zones_watts" in prompt

    print("\n=== PLANNING PROMPT TEST PASSED ===")


if __name__ == "__main__":
    test_extract_json()
    test_validate_training_decision()
    test_invalid_decision()
    test_build_prompt()

    print("\nВсе тесты планировщика пройдены!")