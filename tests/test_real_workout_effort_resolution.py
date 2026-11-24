
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

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_resolution import (
    analyze_resolved_workout_efforts,
)


ATHLETE_ID = "i280488"

# Рабочее допущение для диагностики.
FTP = 304

HISTORY_DAYS = 30


def test_real_workout_effort_resolution():
    print("Получаем историю тренировок...")

    training = (
        get_registered_athlete_unified_training(
            athlete_id=ATHLETE_ID,
            days=HISTORY_DAYS,
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
            parse_activity_date(
                activity["start_date"]
            )

        except (KeyError, TypeError, ValueError):
            continue

        selected.append(activity)

    selected.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    print("\n=== HISTORY STATISTICS ===")
    pprint(training.get("statistics"))

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

    for index, activity in enumerate(
        selected,
        start=1,
    ):
        print("\n" + "=" * 70)

        print(
            f"WORKOUT {index}/{len(selected)}"
        )

        print("NAME:", activity.get("name"))
        print("DATE:", activity["start_date"])
        print("ID:", activity["id"])

        try:
            content = downloader(activity)

            records = read_fit_bytes(
                content
            )

            result = analyze_resolved_workout_efforts(
                records=records,
                ftp=FTP,
            )

        except Exception as error:
            errors.append({
                "workout_id": activity["id"],

                "name": activity.get("name"),

                "date": activity["start_date"],

                "error_type": type(error).__name__,
            })

            print(
                "ANALYSIS ERROR:",
                type(error).__name__,
            )

            continue

        status = result.get("status")

        print("\n=== ANALYSIS STATUS ===")
        print(status)

        if status != "ok":
            pprint({
                "reason": result.get("reason"),
            })

            summaries.append({
                "date": activity["start_date"],

                "name": activity.get("name"),

                "status": status,

                "reason": result.get("reason"),
            })

            continue

        detection = result[
            "original_detection"
        ]

        classification = detection[
            "classification"
        ]

        resolution_summary = result[
            "summary"
        ]

        print("\n=== CLASSIFICATION ===")

        pprint({
            "workout_type": classification.get(
                "workout_type"
            ),

            "dominant_power_zone": classification.get(
                "dominant_power_zone"
            ),

            "duration_seconds": classification.get(
                "duration_seconds"
            ),

            "average_power": classification.get(
                "average_power"
            ),

            "power_cv_percent": classification.get(
                "power_cv_percent"
            ),
        })

        print("\n=== DETECTION SUMMARY ===")

        pprint(
            detection["summary"]
        )

        print("\n=== RESOLUTION SUMMARY ===")

        pprint(
            resolution_summary
        )

        print("\n=== RESOLVED EFFORTS ===")

        efforts = result["efforts"]

        for effort in efforts:
            pprint({
                "effort_id": effort["effort_id"],

                "primary_profile": effort[
                    "primary_profile"
                ],

                "matched_profiles": effort[
                    "matched_profiles"
                ],

                "start": effort["start"],

                "end": effort["end"],

                "duration_seconds": effort[
                    "duration_seconds"
                ],

                "average_power": effort.get(
                    "average_power"
                ),

                "average_power_ftp_percent": (
                    effort.get(
                        "average_power_ftp_percent"
                    )
                ),

                "average_heart_rate": effort.get(
                    "average_heart_rate"
                ),

                "max_heart_rate": effort.get(
                    "max_heart_rate"
                ),

                "average_cadence": effort.get(
                    "average_cadence"
                ),

                "parent_effort_id": effort[
                    "parent_effort_id"
                ],

                "child_effort_ids": effort[
                    "child_effort_ids"
                ],

                "overlapping_effort_ids": effort[
                    "overlapping_effort_ids"
                ],
            })

            print()

        # Проверяем уникальность идентификаторов.
        effort_ids = [
            effort["effort_id"]
            for effort in efforts
        ]

        assert len(effort_ids) == len(
            set(effort_ids)
        )

        # Проверяем отсутствие двойного учёта.
        assert (
            resolution_summary[
                "unique_work_seconds"
            ]
            <=
            resolution_summary[
                "source_duration_seconds"
            ]
        )

        # Уникальное время работы не может
        # превышать время валидной записи мощности.
        assert (
            resolution_summary[
                "unique_work_seconds"
            ]
            <=
            classification[
                "duration_seconds"
            ]
        )

        # Проверяем ссылки между усилиями.
        efforts_by_id = {
            effort["effort_id"]: effort
            for effort in efforts
        }

        for effort in efforts:
            parent_id = effort[
                "parent_effort_id"
            ]

            if parent_id is not None:
                assert parent_id in efforts_by_id

                parent = efforts_by_id[
                    parent_id
                ]

                assert effort["effort_id"] in (
                    parent["child_effort_ids"]
                )

                assert parse_activity_date(
                    parent["start"]
                ) <= parse_activity_date(
                    effort["start"]
                )

                assert parse_activity_date(
                    parent["end"]
                ) >= parse_activity_date(
                    effort["end"]
                )

            for child_id in effort[
                "child_effort_ids"
            ]:
                assert child_id in efforts_by_id

                assert efforts_by_id[child_id][
                    "parent_effort_id"
                ] == effort["effort_id"]

            for overlap_id in effort[
                "overlapping_effort_ids"
            ]:
                assert overlap_id in efforts_by_id

                assert effort["effort_id"] in (
                    efforts_by_id[overlap_id][
                        "overlapping_effort_ids"
                    ]
                )

        profiles = {}

        for profile, profile_summary in (
            detection["summary"].items()
        ):
            if profile_summary["efforts_count"] == 0:
                continue

            profiles[profile] = {
                "count": profile_summary[
                    "efforts_count"
                ],

                "duration_seconds": profile_summary[
                    "total_duration_seconds"
                ],

                "average_power": profile_summary[
                    "average_power"
                ],

                "average_duration_seconds": (
                    profile_summary[
                        "average_duration_seconds"
                    ]
                ),
            }

        summaries.append({
            "date": activity["start_date"],

            "name": activity.get("name"),

            "status": status,

            "workout_type": classification.get(
                "workout_type"
            ),

            "dominant_zone": classification.get(
                "dominant_power_zone"
            ),

            "duration_seconds": classification.get(
                "duration_seconds"
            ),

            "average_power": classification.get(
                "average_power"
            ),

            "power_cv_percent": classification.get(
                "power_cv_percent"
            ),

            "unique_efforts_count": (
                resolution_summary[
                    "unique_efforts_count"
                ]
            ),

            "root_efforts_count": (
                resolution_summary[
                    "root_efforts_count"
                ]
            ),

            "nested_efforts_count": (
                resolution_summary[
                    "nested_efforts_count"
                ]
            ),

            "partially_overlapping_efforts_count": (
                resolution_summary[
                    "partially_overlapping_efforts_count"
                ]
            ),

            "unique_work_seconds": (
                resolution_summary[
                    "unique_work_seconds"
                ]
            ),

            "profiles": profiles,
        })

    print("\n" + "=" * 70)

    print("\n=== FINAL WORKOUT PROFILES ===")

    for summary in summaries:
        pprint(summary)
        print()

    successful = [
        summary
        for summary in summaries
        if summary["status"] == "ok"
    ]

    insufficient = [
        summary
        for summary in summaries
        if summary["status"] != "ok"
    ]

    print("\n=== ANALYSIS STATISTICS ===")

    pprint({
        "selected_workouts": len(selected),

        "successfully_processed": len(
            successful
        ),

        "insufficient_data_workouts": len(
            insufficient
        ),

        "failed_workouts": len(errors),

        "processed_workouts": len(
            summaries
        ),
    })

    print("\n=== INSUFFICIENT DATA WORKOUTS ===")
    pprint(insufficient)

    print("\n=== ERRORS ===")
    pprint(errors)

    assert selected, (
        "Не выбраны велосипедные тренировки"
    )

    assert successful, (
        "Нет успешно проанализированных тренировок"
    )

    assert (
        len(summaries) + len(errors)
        == len(selected)
    )

    print(
        "\nREAL WORKOUT EFFORT RESOLUTION "
        "DIAGNOSTIC TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_effort_resolution()
