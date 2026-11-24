
from src.analytics.aerobic_drift import (
    analyze_aerobic_drift_quality,
)

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


def test_aerobic_drift_quality():
    stable_records = (
        make_records(200, 135, 1800)
        + make_records(200, 145, 1800)
    )

    stable = analyze_aerobic_drift_quality(
        stable_records
    )

    assert stable["status"] == "ok"
    assert stable["power_stability"]["is_stable"] is True
    assert abs(stable["drift_percent"] - 7.41) < 0.01

    print("STABLE AEROBIC DRIFT TEST PASSED")

    interval_records = (
        make_records(100, 120, 900)
        + make_records(300, 160, 900)
    )

    intervals = analyze_aerobic_drift_quality(
        interval_records
    )

    assert intervals["status"] == "not_comparable"
    assert intervals["power_stability"]["is_stable"] is False

    print("INTERVAL WORKOUT REJECTION TEST PASSED")

    short_records = make_records(
        200, 140, 100
    )

    short = analyze_aerobic_drift_quality(
        short_records
    )

    assert short["status"] == "insufficient_data"

    print("INSUFFICIENT DATA TEST PASSED")

    latest = {
        "id": "latest",
        "start_date": "2027-03-15T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 140,
    }

    previous = {
        "id": "previous",
        "start_date": "2027-03-01T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 140,
    }

    result = analyze_latest_workout_detailed(
        latest_workout=latest,
        activities=[previous],
        activity_records={
            "latest": stable_records,
            "previous": interval_records,
        },
    )

    assert result["aerobic_drift"]["status"] == "ok"
    assert result["aerobic_drift"]["compared_workouts"] == 0

    print("WORKOUT COMPARISON QUALITY TEST PASSED")

    print(
        "Все тесты проверки качества аэробного дрейфа пройдены!"
    )


if __name__ == "__main__":
    test_aerobic_drift_quality()
