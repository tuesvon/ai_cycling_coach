
from src.assistant.coach import build_power_zones_watts
from src.assistant.weekly_adaptation_validator import (
    validate_weekly_adaptation,
)


def test_real_weekly_power_zones():
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

    assert len(zones) == 7

    print("\n=== POWER ZONES ===")
    for zone in zones:
        print(zone)

    endurance = next(
        zone for zone in zones
        if zone["name"] == "Endurance"
    )

    assert endurance["min_watts"] == 168
    assert endurance["max_watts"] == 228

    context = {
        "athlete": {
            "power_zones_watts": zones
        },
        "weekly_plan": {
            "workouts": [
                {
                    "id": 10,
                    "date": "2026-11-24",
                    "status": "planned"
                }
            ]
        }
    }

    decision = {
        "decision": "adapt",
        "explanation": "Корректировка аэробной нагрузки",
        "changes": [
            {
                "workout_id": 10,
                "new_workout": {
                    "date": "2026-11-24",
                    "type": "Endurance",
                    "duration_minutes": 60,
                    "power_zone": "Endurance",
                    "power_range_watts": "168-228",
                    "purpose": "Развитие аэробной выносливости"
                },
                "change_reason": "Корректировка нагрузки",
                "impact_on_goal": "Поддержание аэробной подготовки"
            }
        ]
    }

    result = validate_weekly_adaptation(
        decision,
        context,
        today="2026-11-23"
    )

    assert result["decision"] == "adapt"

    print("\nREAL WEEKLY POWER ZONES TEST PASSED")


if __name__ == "__main__":
    test_real_weekly_power_zones()
