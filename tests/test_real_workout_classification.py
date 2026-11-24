
from datetime import datetime, timezone
from pprint import pprint

from src.athletes.data_loader import (
    get_registered_athlete_unified_training,
)

from src.athletes.credentials import (
    get_api_key as get_stored_api_key,
)

from src.athletes.workout_analysis import (
    prepare_comparison_activities,
    create_intervals_fit_downloader,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_comparison_loader import (
    read_fit_bytes,
)

from src.analytics.workout_classification import (
    classify_workout,
)


ATHLETE_ID = "i280488"

# FTP для диагностического теста.
# Используем 304 Вт как рабочее допущение.
FTP = 304

TARGET_DATES = {
    "2026-11-09",
    "2026-11-12",
    "2026-11-16",
    "2026-11-18",
    "2026-11-23",
}


def test_real_workout_classification():
    print("Получаем историю тренировок...")

    oldest_date = datetime.fromisoformat(
        min(TARGET_DATES)
    ).replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    history_days = max(
        30,
        (now - oldest_date).days + 2,
    )

    training = (
        get_registered_athlete_unified_training(
            athlete_id=ATHLETE_ID,
            days=history_days,
        )
    )

    activities = prepare_comparison_activities(
        training["activities"]
    )

    api_key = get_stored_api_key(
        athlete_id=ATHLETE_ID,
        provider="intervals",
    )

    if not api_key:
        raise ValueError(
            "API-ключ Intervals.icu не найден"
        )

    fit_downloader = (
        create_intervals_fit_downloader(
            api_key
        )
    )

    selected = []

    for activity in activities:
        if activity.get("type") != "cycling":
            continue

        try:
            activity_date = parse_activity_date(
                activity["start_date"]
            )
        except (KeyError, TypeError, ValueError):
            continue

        date_string = (
            activity_date.date().isoformat()
        )

        if date_string in TARGET_DATES:
            selected.append(activity)

    selected.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    print("\n=== HISTORY STATISTICS ===")
    pprint(training.get("statistics"))

    print("\n=== CLASSIFICATION SETTINGS ===")
    print("FTP:", FTP)
    print("History days:", history_days)
    print("Selected workouts:", len(selected))

    print("\n=== SELECTED WORKOUTS ===")

    for activity in selected:
        print(
            activity["start_date"],
            "|",
            activity.get("name"),
            "|",
            activity["id"],
        )

    found_dates = {
        parse_activity_date(
            activity["start_date"]
        ).date().isoformat()
        for activity in selected
    }

    missing_dates = TARGET_DATES - found_dates

    summary = []
    errors = []

    for activity in selected:
        print("\n" + "=" * 65)

        print("WORKOUT:", activity.get("name"))
        print("DATE:", activity["start_date"])
        print("ID:", activity["id"])

        try:
            content = fit_downloader(activity)

            records = read_fit_bytes(content)

            result = classify_workout(
                records=records,
                ftp=FTP,
            )

        except Exception as error:
            errors.append({
                "workout_id": activity["id"],
                "error_type": type(error).__name__,
            })

            print(
                "ANALYSIS ERROR:",
                type(error).__name__,
            )

            continue

        print("\n=== CLASSIFICATION ===")

        pprint({
            "status": result.get("status"),
            "reason": result.get("reason"),
            "workout_type": result.get(
                "workout_type"
            ),
            "dominant_power_zone": result.get(
                "dominant_power_zone"
            ),
            "duration_seconds": result.get(
                "duration_seconds"
            ),
            "average_power": result.get(
                "average_power"
            ),
            "average_power_ftp_percent": result.get(
                "average_power_ftp_percent"
            ),
            "power_cv_percent": result.get(
                "power_cv_percent"
            ),
        })

        print("\n=== DATA QUALITY ===")
        pprint(result.get("data_quality"))

        print("\n=== POWER ZONE DISTRIBUTION ===")
        pprint(
            result.get("power_zone_distribution")
        )

        intensity = result.get(
            "high_intensity", {}
        )

        print("\n=== HIGH INTENSITY SUMMARY ===")

        pprint({
            "threshold_watts": intensity.get(
                "threshold_watts"
            ),
            "intervals_count": intensity.get(
                "intervals_count"
            ),
            "total_duration_seconds": intensity.get(
                "total_duration_seconds"
            ),
            "average_interval_duration_seconds": (
                intensity.get(
                    "average_interval_duration_seconds"
                )
            ),
            "average_interval_power": intensity.get(
                "average_interval_power"
            ),
        })

        print("\n=== DETECTED INTERVALS ===")

        for index, interval in enumerate(
            intensity.get("intervals", []),
            start=1,
        ):
            print(f"\nInterval {index}")
            pprint(interval)

        summary.append({
            "date": activity["start_date"],
            "name": activity.get("name"),
            "status": result.get("status"),
            "workout_type": result.get(
                "workout_type"
            ),
            "dominant_zone": result.get(
                "dominant_power_zone"
            ),
            "intervals_count": intensity.get(
                "intervals_count"
            ),
            "high_intensity_seconds": intensity.get(
                "total_duration_seconds"
            ),
            "average_interval_power": intensity.get(
                "average_interval_power"
            ),
            "average_interval_duration": intensity.get(
                "average_interval_duration_seconds"
            ),
        })

    print("\n" + "=" * 65)

    print("\n=== FINAL CLASSIFICATION SUMMARY ===")

    for workout in summary:
        pprint(workout)
        print()

    print("\n=== ANALYSIS STATISTICS ===")

    pprint({
        "selected_workouts": len(selected),
        "processed_workouts": len(summary),
        "successfully_classified": sum(
            workout["status"] == "ok"
            for workout in summary
        ),
        "failed_workouts": len(errors),
        "missing_dates": sorted(missing_dates),
    })

    print("\n=== ERRORS ===")
    pprint(errors)

    assert not missing_dates, (
        "Не найдены тренировки за некоторые даты"
    )

    assert len(selected) > 0, (
        "Не выбраны тренировки"
    )

    assert not errors, (
        "Некоторые FIT-файлы не удалось обработать"
    )

    assert len(summary) == len(selected)

    print(
        "\nREAL WORKOUT CLASSIFICATION "
        "DIAGNOSTIC TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_classification()
