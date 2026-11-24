
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

from src.analytics.workout_interval_refinement import (
    refine_workout_intervals,
)


ATHLETE_ID = "i280488"

# FTP для диагностического теста.
FTP = 304

TARGET_DATES = {
    "2026-11-09",
    "2026-11-12",
    "2026-11-16",
    "2026-11-18",
    "2026-11-23",
}


def test_real_workout_interval_refinement():
    print("Получаем историю тренировок...")

    oldest_date = datetime.fromisoformat(
        min(TARGET_DATES)
    ).replace(tzinfo=timezone.utc)

    history_days = max(
        30,
        (
            datetime.now(timezone.utc)
            - oldest_date
        ).days + 2,
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

    downloader = create_intervals_fit_downloader(
        api_key
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

        if activity_date.date().isoformat() in TARGET_DATES:
            selected.append(activity)

    selected.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    found_dates = {
        parse_activity_date(
            activity["start_date"]
        ).date().isoformat()
        for activity in selected
    }

    missing_dates = TARGET_DATES - found_dates

    print("\n=== SELECTED WORKOUTS ===")

    for activity in selected:
        print(
            activity["start_date"],
            "|",
            activity.get("name"),
            "|",
            activity["id"],
        )

    summaries = []
    errors = []

    for activity in selected:
        print("\n" + "=" * 65)

        print("WORKOUT:", activity.get("name"))
        print("DATE:", activity["start_date"])
        print("ID:", activity["id"])

        try:
            content = downloader(activity)

            records = read_fit_bytes(content)

            result = refine_workout_intervals(
                records=records,
                ftp=FTP,
            )

        except Exception as error:
            errors.append({
                "workout_id": activity["id"],
                "error_type": type(error).__name__,
            })

            continue

        print("\n=== REFINEMENT STATUS ===")
        print(result["status"])

        summary = result.get("summary", {})

        print("\n=== REFINEMENT SUMMARY ===")
        pprint(summary)

        print("\n=== ORIGINAL INTERVALS ===")

        original_intervals = result.get(
            "original_intervals", []
        )

        for index, interval in enumerate(
            original_intervals,
            start=1,
        ):
            print(f"\nOriginal interval {index}")

            pprint({
                "start": interval.get("start"),
                "end": interval.get("end"),
                "duration_seconds": interval.get(
                    "duration_seconds"
                ),
                "average_power": interval.get(
                    "average_power"
                ),
            })

        print("\n=== REFINED INTERVALS ===")

        refined_intervals = result.get(
            "refined_intervals", []
        )

        for index, interval in enumerate(
            refined_intervals,
            start=1,
        ):
            print(f"\nRefined interval {index}")
            pprint(interval)

        print("\n=== CONNECTION DECISIONS ===")

        for decision in result.get(
            "connection_decisions", []
        ):
            previous = decision[
                "previous_interval_number"
            ]

            following = decision[
                "next_interval_number"
            ]

            print(
                f"\nInterval {previous} "
                f"-> Interval {following}"
            )

            pprint(decision)

        if result["status"] == "ok":
            # Проверяем сохранение исходных отрезков.
            assert len(original_intervals) == (
                summary["original_intervals_count"]
            )

            assert len(refined_intervals) == (
                summary["refined_intervals_count"]
            )

            # Уточнение не должно увеличивать
            # количество интервалов.
            assert len(refined_intervals) <= len(
                original_intervals
            )

            # Каждый исходный отрезок должен
            # присутствовать ровно один раз.
            source_numbers = [
                number
                for interval in refined_intervals
                for number in interval[
                    "source_interval_numbers"
                ]
            ]

            assert source_numbers == list(
                range(
                    1,
                    len(original_intervals) + 1,
                )
            )

            # Проверяем сохранение времени работы.
            assert (
                summary["refined_work_seconds"]
                ==
                summary[
                    "original_high_intensity_seconds"
                ]
                + summary[
                    "included_transition_seconds"
                ]
            )

        summaries.append({
            "date": activity["start_date"],
            "name": activity.get("name"),
            "status": result["status"],

            "original_intervals": len(
                original_intervals
            ),

            "refined_intervals": len(
                refined_intervals
            ),

            "connected_transitions": summary.get(
                "connected_transitions_count"
            ),

            "original_high_intensity_seconds": (
                summary.get(
                    "original_high_intensity_seconds"
                )
            ),

            "refined_work_seconds": summary.get(
                "refined_work_seconds"
            ),

            "included_transition_seconds": (
                summary.get(
                    "included_transition_seconds"
                )
            ),

            "average_interval_duration": summary.get(
                "average_interval_duration_seconds"
            ),

            "average_interval_power": summary.get(
                "average_interval_power"
            ),
        })

    print("\n" + "=" * 65)

    print("\n=== FINAL REFINEMENT SUMMARY ===")

    for summary in summaries:
        pprint(summary)
        print()

    print("\n=== ANALYSIS STATISTICS ===")

    pprint({
        "selected_workouts": len(selected),
        "processed_workouts": len(summaries),

        "successfully_processed": sum(
            summary["status"] == "ok"
            for summary in summaries
        ),

        "failed_workouts": len(errors),
        "missing_dates": sorted(missing_dates),
    })

    print("\n=== ERRORS ===")
    pprint(errors)

    assert selected, (
        "Не выбраны тренировки"
    )

    assert not missing_dates, (
        "Не найдены тренировки за некоторые даты"
    )

    assert not errors, (
        "Некоторые FIT-файлы не обработаны"
    )

    assert len(summaries) == len(selected)

    assert all(
        summary["status"] == "ok"
        for summary in summaries
    ), "Не все тренировки успешно проанализированы"

    print(
        "\nREAL WORKOUT INTERVAL REFINEMENT "
        "TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_interval_refinement()
