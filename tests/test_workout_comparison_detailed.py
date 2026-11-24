
from src.analytics.workout_comparison import (
    analyze_latest_workout_detailed,
)


def make_records(power, heart_rate, count=120):
    return [
        {
            "power": power,
            "heart_rate": heart_rate,
        }
        for _ in range(count)
    ]


def test_workout_comparison_detailed():
    latest = {
        "id": "latest",
        "start_date": "2027-03-15T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 137,
    }

    previous = {
        "id": "previous",
        "start_date": "2027-03-01T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 145,
    }

    activity_records = {
        "latest": (
            make_records(200, 137)
            + make_records(220, 145)
        ),
        "previous": (
            make_records(200, 145)
            + make_records(220, 150)
        ),
    }

    result = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records=activity_records,
    )

    assert result["similar_workouts_found"] == 1

    print("SIMILAR WORKOUT INTEGRATION TEST PASSED")

    power_hr = result["power_hr_comparison"]

    assert power_hr["status"] == "ok"
    assert power_hr["compared_workouts"] == 1

    comparison = power_hr["comparisons"][0][
        "comparison"
    ]

    ranges = {
        item["power_min"]: item
        for item in comparison["ranges"]
    }

    assert ranges[200]["difference_bpm"] == -8
    assert ranges[220]["difference_bpm"] == -5

    print("DETAILED POWER HR INTEGRATION TEST PASSED")

    missing_records = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records={},
    )

    assert missing_records["power_hr_comparison"][
        "status"
    ] == "insufficient_data"

    print("MISSING DETAILED RECORDS TEST PASSED")

    no_previous_records = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records={
            "latest": activity_records["latest"],
        },
    )

    assert no_previous_records["power_hr_comparison"][
        "status"
    ] == "insufficient_data"

    print("MISSING PREVIOUS RECORDS TEST PASSED")

    print(
        "Все тесты расширенного сравнения тренировок пройдены!"
    )


if __name__ == "__main__":
    test_workout_comparison_detailed()