
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.athletes.workout_analysis import (
    normalize_workout_for_comparison,
    prepare_comparison_activities,
    create_intervals_fit_downloader,
    analyze_registered_athlete_workout,
)


def create_activity(
    intervals_id=None,
    garmin_id=None,
    has_details=True,
):
    return {
        "name": "Test workout",
        "activity_type": "cycling",
        "duration": 3600,
        "average_power": 200,
        "average_hr": 130,
        "start_date": (
            datetime.now(timezone.utc)
            - timedelta(hours=2)
        ).isoformat(),
        "intervals_has_details": has_details,
        "source_ids": {
            "intervals": intervals_id,
            "garmin": garmin_id,
        },
    }


def test_intervals_normalization():
    original = create_activity(
        intervals_id="i123",
        garmin_id=456,
    )

    result = normalize_workout_for_comparison(
        original
    )

    assert result["id"] == "intervals:i123"
    assert result["type"] == "cycling"
    assert result["duration_seconds"] == 3600
    assert result["average_power"] == 200
    assert result["average_hr"] == 130

    assert result["source_ids"]["intervals"] == "i123"
    assert result["source_ids"]["garmin"] == 456

    assert "duration_seconds" not in original
    assert "type" not in original

    print("INTERVALS NORMALIZATION TEST PASSED")


def test_garmin_normalization():
    activity = create_activity(
        garmin_id=789,
        has_details=False,
    )

    result = normalize_workout_for_comparison(
        activity
    )

    assert result["id"] == "garmin:789"
    assert result["type"] == "cycling"
    assert result["duration_seconds"] == 3600

    print("GARMIN NORMALIZATION TEST PASSED")


def test_missing_source_ids():
    activity = create_activity()

    result = prepare_comparison_activities(
        [activity]
    )

    assert result == []

    print("MISSING SOURCE IDS TEST PASSED")


def test_intervals_fit_downloader():
    activity = create_activity(
        intervals_id="i123",
        garmin_id=456,
    )

    workout = normalize_workout_for_comparison(
        activity
    )

    downloader = create_intervals_fit_downloader(
        "test_api_key"
    )

    with patch(
        "src.athletes.workout_analysis"
        ".download_activity_fit",
        return_value=b"FAKE_FIT",
    ) as mocked_download:

        result = downloader(workout)

    assert result == b"FAKE_FIT"

    mocked_download.assert_called_once_with(
        activity_id="i123",
        api_key="test_api_key",
    )

    print("INTERVALS FIT DOWNLOADER TEST PASSED")


def test_unavailable_intervals_details():
    activity = create_activity(
        intervals_id="123456",
        garmin_id=789,
        has_details=False,
    )

    workout = normalize_workout_for_comparison(
        activity
    )

    downloader = create_intervals_fit_downloader(
        "test_api_key"
    )

    with patch(
        "src.athletes.workout_analysis"
        ".download_activity_fit",
    ) as mocked_download:

        try:
            downloader(workout)

        except ValueError:
            pass

        else:
            raise AssertionError(
                "Ожидалась ошибка недоступности FIT"
            )

        mocked_download.assert_not_called()

    print("UNAVAILABLE INTERVALS DETAILS TEST PASSED")


def test_registered_workout_analysis():
    activity = create_activity(
        intervals_id="i123",
        garmin_id=456,
    )

    fake_training = {
        "athlete_id": "test_athlete",
        "activities": [activity],
        "statistics": {
            "matched_count": 1,
        },
    }

    fake_analysis = {
        "status": "ok",
        "latest_workout": {
            "id": "intervals:i123",
        },
    }

    with patch(
        "src.athletes.workout_analysis"
        ".get_registered_athlete_unified_training",
        return_value=fake_training,
    ) as mocked_training:

        with patch(
            "src.athletes.workout_analysis"
            ".get_stored_api_key",
            return_value="test_api_key",
        ) as mocked_key:

            with patch(
                "src.athletes.workout_analysis"
                ".analyze_workout_with_fit_loader",
                return_value=fake_analysis,
            ) as mocked_analysis:

                result = analyze_registered_athlete_workout(
                    athlete_id="test_athlete",
                    days=30,
                )

    assert result["status"] == "ok"
    assert result["athlete_id"] == "test_athlete"

    assert result["history_statistics"] == {
        "matched_count": 1,
    }

    mocked_training.assert_called_once_with(
        athlete_id="test_athlete",
        days=30,
    )

    mocked_key.assert_called_once_with(
        athlete_id="test_athlete",
        provider="intervals",
    )

    mocked_analysis.assert_called_once()

    arguments = mocked_analysis.call_args.kwargs

    assert arguments["days"] == 30

    assert arguments["activities"][0]["id"] == (
        "intervals:i123"
    )

    assert callable(arguments["fit_downloader"])

    print("REGISTERED WORKOUT ANALYSIS TEST PASSED")


def test_extended_history():
    activity = create_activity(
        intervals_id="i123",
    )

    activity["start_date"] = (
        datetime.now(timezone.utc)
        - timedelta(days=5, hours=1)
    ).isoformat()

    fake_training = {
        "activities": [activity],
        "statistics": {},
    }

    with patch(
        "src.athletes.workout_analysis"
        ".get_registered_athlete_unified_training",
        return_value=fake_training,
    ) as mocked_training:

        with patch(
            "src.athletes.workout_analysis"
            ".get_stored_api_key",
            return_value="test_api_key",
        ):

            with patch(
                "src.athletes.workout_analysis"
                ".analyze_workout_with_fit_loader",
                return_value={"status": "ok"},
            ):

                analyze_registered_athlete_workout(
                    athlete_id="test_athlete",
                    days=30,
                )

    assert mocked_training.call_count == 2

    assert mocked_training.call_args.kwargs[
        "days"
    ] == 36

    print("EXTENDED HISTORY TEST PASSED")


if __name__ == "__main__":
    test_intervals_normalization()
    test_garmin_normalization()
    test_missing_source_ids()
    test_intervals_fit_downloader()
    test_unavailable_intervals_details()
    test_registered_workout_analysis()
    test_extended_history()

    print(
        "\nВсе тесты анализа тренировок "
        "зарегистрированного спортсмена пройдены!"
    )
