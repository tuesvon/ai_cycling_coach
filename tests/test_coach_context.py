from src.assistant.coach import (
    build_coach_context,
    build_coach_prompt
)


def test_build_coach_context():
    analysis = {
        "profile": {
            "name": "Test Athlete",
            "ftp": 250
        },
        "readiness": {
            "overall": "good"
        },
        "training_load": {
            "7_days": {
                "total_duration_hours": 5.5
            }
        },
        "recovery": {
            "7_days": {
                "average_sleep_hours": 7.5
            }
        },
        "training_history": {
            "days_since_last_ride": 1
        },
        "training_trends": {
            "overall_trend": "increasing"
        },
        "training_load_trends": {
            "comparison": {}
        },
        "training_consistency": {
            "objective": {
                "training_days_count": 20
            }
        },
        "raw_api_data": {
            "secret": "should_not_be_transmitted"
        }
    }

    context = build_coach_context(analysis)

    assert "profile" in context
    assert "readiness" in context
    assert "cycling_training_load" in context
    assert "training_load" not in context
    assert "recovery" in context
    assert "training_history" in context
    assert "training_trends" in context
    assert "last_7_days_vs_previous_23_days" in context["cycling_training_load"]
    assert "training_consistency" in context

    assert "raw_api_data" not in context


def test_build_coach_prompt():
    analysis = {
        "profile": {
            "ftp": 250
        },
        "readiness": {
            "overall": "good"
        }
    }

    question = "Как мне тренироваться сегодня?"

    prompt = build_coach_prompt(analysis, question)

    assert "ДАННЫЕ СПОРТСМЕНА" in prompt
    assert "ВОПРОС СПОРТСМЕНА" in prompt
    assert question in prompt
    assert '"ftp_watts": 250' in prompt

    print("\n=== COACH PROMPT ===")
    print(prompt)

def test_power_zones():
    from src.assistant.coach import build_power_zones_watts

    profile = {
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
    }

    zones = build_power_zones_watts(profile)

    print("\n=== POWER ZONES ===")
    for zone in zones:
        print(zone)

    assert zones[0]["min_watts"] == 1
    assert zones[0]["max_watts"] == 167

    assert zones[1]["min_watts"] == 168
    assert zones[1]["max_watts"] == 228

    assert zones[2]["min_watts"] == 229
    assert zones[2]["max_watts"] == 273

    assert zones[3]["min_watts"] == 274
    assert zones[3]["max_watts"] == 319

    assert zones[4]["min_watts"] == 320
    assert zones[4]["max_watts"] == 364

    assert zones[5]["min_watts"] == 365
    assert zones[5]["max_watts"] == 456

    assert zones[6]["min_watts"] == 457
    assert zones[6]["max_watts"] is None

if __name__ == "__main__":
    test_build_coach_context()
    test_build_coach_prompt()
    test_power_zones()
    print("\nВсе тесты контекста тренера пройдены!")