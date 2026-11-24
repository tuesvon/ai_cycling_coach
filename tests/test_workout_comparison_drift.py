
from src.analytics.workout_comparison import (
    analyze_latest_workout_detailed,
)


def make_records(power, heart_rate, count):
    return [
        {
            "power": power,
            "heart_rate": heart_rate,
        }
        for _ in range(count)
    ]


def test_workout_comparison_drift():
    latest = {
        "id": "latest",
        "start_date": "2027-03-15T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 138,
    }

    previous = {
        "id": "previous",
        "start_date": "2027-03-01T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 140,
    }

    activity_records = {
        "latest": (
            make_records(200, 135, 1800)
            + make_records(200, 140, 1800)
        ),
        "previous": (
            make_records(200, 135, 1800)
            + make_records(200, 145, 1800)
        ),
    }

    result = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records=activity_records,
    )

    drift = result["aerobic_drift"]

    assert drift["status"] == "ok"
    assert drift["compared_workouts"] == 1

    assert abs(drift["drift_percent"] - 3.70) < 0.01

    print("LATEST AEROBIC DRIFT TEST PASSED")

    comparison = drift["previous_comparisons"][0]

    assert comparison["workout_id"] == "previous"

    assert abs(
        comparison["previous_drift_percent"] - 7.41
    ) < 0.01

    assert abs(
        comparison["difference_percentage_points"] - (-3.71)
    ) < 0.01

    print("AEROBIC DRIFT COMPARISON TEST PASSED")

    power_hr = result["power_hr_comparison"]

    assert power_hr["status"] == "ok"
    assert power_hr["compared_workouts"] == 1

    print("POWER HR COMPATIBILITY TEST PASSED")

    missing_records = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records={},
    )

    assert missing_records["aerobic_drift"][
        "status"
    ] == "insufficient_data"

    print("MISSING RECORDS TEST PASSED")

    print(
        "Все тесты интеграции аэробного дрейфа пройдены!"
    )


if __name__ == "__main__":
    test_workout_comparison_drift()
