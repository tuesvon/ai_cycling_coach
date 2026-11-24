
from datetime import datetime, timedelta, timezone

from src.analytics.fit_workout_comparison import (
    analyze_fit_workout_comparison,
)


def make_activity(
    activity_id,
    day,
    heart_rate=130,
):
    return {
        "id": activity_id,
        "name": f"Workout {activity_id}",
        "type": "cycling",
        "start_date": datetime(
            2026, 11, day, 10, 0,
            tzinfo=timezone.utc,
        ).isoformat(),
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": heart_rate,
    }


def make_records(
    count=3600,
    power=200,
    heart_rate=130,
    gap_seconds=0,
):
    start = datetime(
        2026, 11, 10, 10, 0,
        tzinfo=timezone.utc,
    )

    records = []

    for index in range(count):
        offset = index

        if index >= count // 2:
            offset += gap_seconds

        records.append({
            "timestamp": start + timedelta(
                seconds=offset
            ),
            "power": power,
            "heart_rate": heart_rate,
            "cadence": 85,
        })

    return records


def test_previous_workout_with_gap():
    latest = make_activity(
        "latest", 23, 130
    )

    previous = make_activity(
        "previous", 18, 135
    )

    result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[latest, previous],
        activity_records={
            "latest": make_records(
                heart_rate=130,
            ),
            "previous": make_records(
                heart_rate=135,
                gap_seconds=27,
            ),
        },
    )

    quality = result["fit_data_quality"][
        "all_workouts"
    ]["previous"]

    assert quality["time_gaps_count"] == 1

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is True

    assert quality[
        "suitable_for_continuous_analysis"
    ] is False

    assert result["power_hr_comparison"][
        "status"
    ] == "ok"

    assert result["power_hr_comparison"][
        "compared_workouts"
    ] == 1

    assert result["aerobic_drift"][
        "status"
    ] == "ok"

    assert result["aerobic_drift"][
        "compared_workouts"
    ] == 0

    assert result["aerobic_drift"][
        "skipped_workouts_count"
    ] == 1

    print(
        "PREVIOUS WORKOUT WITH GAP TEST PASSED"
    )


def test_latest_workout_with_gap():
    latest = make_activity(
        "latest", 23
    )

    previous = make_activity(
        "previous", 18
    )

    result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[latest, previous],
        activity_records={
            "latest": make_records(
                gap_seconds=27,
            ),
            "previous": make_records(),
        },
    )

    assert result["power_hr_comparison"][
        "status"
    ] == "ok"

    assert result["power_hr_comparison"][
        "compared_workouts"
    ] == 1

    assert result["aerobic_drift"][
        "status"
    ] == "insufficient_data"

    assert result["aerobic_drift"][
        "compared_workouts"
    ] == 0

    print(
        "LATEST WORKOUT WITH GAP TEST PASSED"
    )


def test_excessive_gap():
    latest = make_activity(
        "latest", 23
    )

    previous = make_activity(
        "previous", 18
    )

    result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[latest, previous],
        activity_records={
            "latest": make_records(),
            "previous": make_records(
                gap_seconds=1800,
            ),
        },
    )

    assert result["power_hr_comparison"][
        "status"
    ] == "insufficient_data"

    assert result["power_hr_comparison"][
        "compared_workouts"
    ] == 0

    assert result["power_hr_comparison"][
        "skipped_workouts_count"
    ] == 1

    print("EXCESSIVE GAP TEST PASSED")


def test_regular_workouts():
    latest = make_activity(
        "latest", 23
    )

    previous = make_activity(
        "previous", 18
    )

    result = analyze_fit_workout_comparison(
        latest_workout=latest,
        activities=[latest, previous],
        activity_records={
            "latest": make_records(),
            "previous": make_records(),
        },
    )

    assert result["power_hr_comparison"][
        "compared_workouts"
    ] == 1

    assert result["aerobic_drift"][
        "status"
    ] == "ok"

    assert result["aerobic_drift"][
        "compared_workouts"
    ] == 1

    eligibility = result["fit_data_quality"][
        "analysis_eligibility"
    ]

    assert eligibility[
        "power_hr_workouts_count"
    ] == 2

    assert eligibility[
        "continuous_workouts_count"
    ] == 2

    print("REGULAR WORKOUTS TEST PASSED")


if __name__ == "__main__":
    test_previous_workout_with_gap()
    test_latest_workout_with_gap()
    test_excessive_gap()
    test_regular_workouts()

    print(
        "\nВсе тесты пригодности FIT-данных "
        "для анализа пройдены!"
    )
