
from datetime import datetime, timedelta, timezone

from src.analytics.fit_workout_comparison import (
    analyze_fit_workout_comparison,
)


def make_records(
    first_hr,
    second_hr,
    count_per_half=1800,
    interval_seconds=1,
):
    start = datetime(
        2027, 3, 15, 10, 0,
        tzinfo=timezone.utc,
    )

    records = []

    for index in range(count_per_half * 2):
        heart_rate = (
            first_hr
            if index < count_per_half
            else second_hr
        )

        records.append({
            "timestamp": start + timedelta(
                seconds=index * interval_seconds
            ),
            "power": 200,
            "heart_rate": heart_rate,
            "cadence": 85,
        })

    return records


def test_fit_workout_comparison():
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

    latest_records = make_records(135, 140)
    previous_records = make_records(135, 145)

    result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[previous],
        activity_records={
            "latest": latest_records,
            "previous": previous_records,
        },
    )

    assert result["fit_data_quality"][
        "latest_workout"
    ]["suitable_for_sample_based_analysis"] is True

    assert result["aerobic_drift"]["status"] == "ok"

    assert result["aerobic_drift"][
        "compared_workouts"
    ] == 1

    assert result["power_hr_comparison"][
        "status"
    ] == "ok"

    print("VALID FIT COMPARISON TEST PASSED")

    irregular_records = make_records(
        135,
        140,
        interval_seconds=3,
    )

    invalid_result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[previous],
        activity_records={
            "latest": irregular_records,
            "previous": previous_records,
        },
    )

    assert invalid_result["fit_data_quality"][
        "latest_workout"
    ]["suitable_for_sample_based_analysis"] is False

    assert invalid_result["aerobic_drift"][
        "status"
    ] == "insufficient_data"

    assert invalid_result["power_hr_comparison"][
        "status"
    ] == "insufficient_data"

    print("INVALID FIT TIMING TEST PASSED")

    missing_result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[previous],
        activity_records={},
    )

    assert missing_result["aerobic_drift"][
        "status"
    ] == "insufficient_data"

    assert missing_result["fit_data_quality"][
        "latest_workout"
    ] is None

    print("MISSING FIT RECORDS TEST PASSED")

    print(
        "Все тесты интеграции FIT и сравнения "
        "тренировок пройдены!"
    )


if __name__ == "__main__":
    test_fit_workout_comparison()
