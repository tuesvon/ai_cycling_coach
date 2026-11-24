
from datetime import datetime, timedelta
from unittest.mock import patch

from src.analytics.workout_comparison_loader import (
    select_latest_cycling_workout,
    load_comparison_records,
    analyze_workout_with_fit_loader,
)


def create_activity(
    activity_id,
    start_date,
    power=200,
    duration=3600,
    heart_rate=130,
    activity_type="cycling",
):
    return {
        "id": activity_id,
        "name": f"Workout {activity_id}",
        "start_date": start_date,
        "type": activity_type,
        "duration_seconds": duration,
        "average_power": power,
        "average_hr": heart_rate,
    }


def create_records(
    power=200,
    heart_rate=130,
    count=3600,
):
    start = datetime(2026, 11, 23, 10, 0)

    return [
        {
            "timestamp": start + timedelta(seconds=i),
            "power": power,
            "heart_rate": heart_rate,
            "cadence": 85,
        }
        for i in range(count)
    ]


def create_test_activities():
    return [
        create_activity(
            "previous_1",
            "2026-11-20T10:00:00+00:00",
        ),
        create_activity(
            "latest",
            "2026-11-23T10:00:00+00:00",
        ),
        create_activity(
            "previous_2",
            "2026-11-18T10:00:00+00:00",
        ),
        create_activity(
            "different_power",
            "2026-11-21T10:00:00+00:00",
            power=300,
        ),
        create_activity(
            "old_workout",
            "2026-09-01T10:00:00+00:00",
        ),
        create_activity(
            "walking",
            "2026-11-24T10:00:00+00:00",
            activity_type="walking",
        ),
    ]


def test_latest_workout_selection():
    activities = create_test_activities()

    latest = select_latest_cycling_workout(
        activities
    )

    assert latest["id"] == "latest"

    print("LATEST WORKOUT SELECTION TEST PASSED")


def test_selective_fit_loading():
    activities = create_test_activities()

    latest = select_latest_cycling_workout(
        activities
    )

    downloaded_ids = []

    def fake_downloader(workout):
        downloaded_ids.append(workout["id"])
        return b"FAKE_FIT"

    with patch(
        "src.analytics.workout_comparison_loader"
        ".read_fit_bytes",
        return_value=create_records(),
    ):
        result = load_comparison_records(
            latest_workout=latest,
            activities=activities,
            fit_downloader=fake_downloader,
            days=30,
        )

    assert set(downloaded_ids) == {
        "latest",
        "previous_1",
        "previous_2",
    }

    assert len(downloaded_ids) == 3

    assert result["statistics"] == {
        "selected_workouts": 3,
        "loaded_workouts": 3,
        "failed_workouts": 0,
    }

    print("SELECTIVE FIT LOADING TEST PASSED")


def test_failed_fit_download():
    activities = create_test_activities()

    latest = select_latest_cycling_workout(
        activities
    )

    def fake_downloader(workout):
        if workout["id"] == "previous_1":
            raise RuntimeError(
                "FIT unavailable"
            )

        return b"FAKE_FIT"

    with patch(
        "src.analytics.workout_comparison_loader"
        ".read_fit_bytes",
        return_value=create_records(),
    ):
        result = load_comparison_records(
            latest_workout=latest,
            activities=activities,
            fit_downloader=fake_downloader,
        )

    assert result["statistics"]["loaded_workouts"] == 2

    assert result["statistics"]["failed_workouts"] == 1

    assert result["download_errors"][0][
        "activity_id"
    ] == "previous_1"

    print("FAILED FIT DOWNLOAD TEST PASSED")


def test_full_workout_analysis():
    activities = create_test_activities()

    def fake_downloader(workout):
        return b"FAKE_FIT"

    with patch(
        "src.analytics.workout_comparison_loader"
        ".read_fit_bytes",
        return_value=create_records(),
    ):
        result = analyze_workout_with_fit_loader(
            activities=activities,
            fit_downloader=fake_downloader,
        )

    assert result["status"] == "ok"

    assert result["latest_workout"]["id"] == "latest"

    assert result["download_statistics"][
        "loaded_workouts"
    ] == 3

    assert result["analysis"][
        "similar_workouts_found"
    ] == 2

    assert result["analysis"][
        "power_hr_comparison"
    ]["status"] == "ok"

    print("FULL WORKOUT ANALYSIS TEST PASSED")


def test_missing_latest_fit():
    activities = create_test_activities()

    def fake_downloader(workout):
        if workout["id"] == "latest":
            raise RuntimeError(
                "Latest FIT unavailable"
            )

        return b"FAKE_FIT"

    with patch(
        "src.analytics.workout_comparison_loader"
        ".read_fit_bytes",
        return_value=create_records(),
    ):
        result = analyze_workout_with_fit_loader(
            activities=activities,
            fit_downloader=fake_downloader,
        )

    assert result["status"] == "insufficient_data"

    print("MISSING LATEST FIT TEST PASSED")


def test_no_cycling_activities():
    result = analyze_workout_with_fit_loader(
        activities=[],
        fit_downloader=lambda workout: b"",
    )

    assert result["status"] == "insufficient_data"

    print("NO CYCLING ACTIVITIES TEST PASSED")


if __name__ == "__main__":
    test_latest_workout_selection()
    test_selective_fit_loading()
    test_failed_fit_download()
    test_full_workout_analysis()
    test_missing_latest_fit()
    test_no_cycling_activities()

    print(
        "\nВсе тесты загрузчика сравнения "
        "тренировок пройдены!"
    )