
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

from src.analytics.workout_comparison_loader import (
    read_fit_bytes,
)

from src.analytics.workout_structure import (
    analyze_workout_structure,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


ATHLETE_ID = "i280488"

# Рабочее допущение для диагностического теста.
FTP = 304

TARGET_DATES = {
    "2026-11-09",
    "2026-11-12",
    "2026-11-16",
    "2026-11-18",
    "2026-11-23",
}


def test_real_workout_structure():
    print("Получаем историю тренировок...")

    training = (
        get_registered_athlete_unified_training(
            athlete_id=ATHLETE_ID,
            days=30,
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

            result = analyze_workout_structure(
                records=records,
                ftp=FTP,
            )

        except Exception as error:
            errors.append({
                "workout_id": activity["id"],
                "error_type": type(error).__name__,
            })

            continue

        print("\n=== STRUCTURE STATUS ===")
        print(result["status"])

        print("\n=== STRUCTURE SUMMARY ===")

        structure_summary = result.get(
            "structure_summary", {}
        )

        pprint(structure_summary)

        intervals = result.get(
            "intervals", []
        )

        transitions = result.get(
            "transitions", []
        )

        print("\n=== DETECTED INTERVALS ===")

        for index, interval in enumerate(
            intervals,
            start=1,
        ):
            print(f"\nInterval {index}")
            pprint(interval)

        print("\n=== TRANSITIONS ===")

        for transition in transitions:
            previous = transition[
                "previous_interval_number"
            ]

            following = transition[
                "next_interval_number"
            ]

            print(
                f"\nInterval {previous} "
                f"-> Interval {following}"
            )

            pprint({
                "type": transition.get(
                    "transition_type"
                ),

                "duration_seconds": transition.get(
                    "duration_seconds"
                ),

                "recorded_seconds": transition.get(
                    "recorded_seconds"
                ),

                "average_power": transition.get(
                    "average_power"
                ),

                "min_power": transition.get(
                    "min_power"
                ),

                "max_power": transition.get(
                    "max_power"
                ),

                "ftp_percent": transition.get(
                    "average_power_ftp_percent"
                ),

                "power_drop_percent": transition.get(
                    "power_drop_percent"
                ),

                "average_heart_rate": transition.get(
                    "average_heart_rate"
                ),

                "possible_power_dip": transition.get(
                    "possible_power_dip"
                ),
            })

        short_dips = [
            transition
            for transition in transitions
            if transition["transition_type"]
            == "short_power_dip"
        ]

        print("\n=== SHORT POWER DIPS ===")

        for dip in short_dips:
            start = parse_activity_date(
                dip["previous_interval_end"]
            )

            end = parse_activity_date(
                dip["next_interval_start"]
            )

            print(
                f"\nBetween intervals "
                f"{dip['previous_interval_number']} "
                f"and {dip['next_interval_number']}"
            )

            for record in records:
                timestamp = record.get(
                    "timestamp"
                )

                try:
                    timestamp = parse_activity_date(
                        timestamp
                    )

                except (TypeError, ValueError):
                    continue

                if start < timestamp < end:
                    pprint({
                        "timestamp": (
                            timestamp.isoformat()
                        ),

                        "power": record.get(
                            "power"
                        ),

                        "heart_rate": record.get(
                            "heart_rate"
                        ),

                        "cadence": record.get(
                            "cadence"
                        ),
                    })

        if not short_dips:
            print("No short power dips detected")

        summaries.append({
            "date": activity["start_date"],
            "name": activity.get("name"),
            "status": result["status"],

            "intervals_count": len(intervals),

            "short_dips_count": len(short_dips),

            "lower_power_segments_count": (
                structure_summary.get(
                    "lower_power_segments_count"
                )
            ),

            "data_gaps_count": (
                structure_summary.get(
                    "data_gaps_count"
                )
            ),

            "requires_structure_refinement": (
                structure_summary.get(
                    "requires_structure_refinement"
                )
            ),
        })

    print("\n" + "=" * 65)

    print("\n=== FINAL STRUCTURE SUMMARY ===")

    for summary in summaries:
        pprint(summary)
        print()

    print("\n=== ERRORS ===")
    pprint(errors)

    print("\n=== MISSING DATES ===")
    pprint(sorted(missing_dates))

    assert not missing_dates, (
        "Не найдены тренировки за некоторые даты"
    )

    assert selected, (
        "Не выбраны тренировки"
    )

    assert not errors, (
        "Некоторые тренировки не обработаны"
    )

    assert len(summaries) == len(selected)

    print(
        "\nREAL WORKOUT STRUCTURE "
        "DIAGNOSTIC TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_structure()
