from collections import Counter
from copy import deepcopy
from pprint import pprint

from src.athletes.data_loader import (
    get_registered_athlete_unified_training,
)

from src.athletes.workout_analysis import (
    prepare_comparison_activities,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_context import (
    classify_workout_context,
    get_activity_source_metadata,
)


ATHLETE_ID = "i280488"
HISTORY_DAYS = 30


def test_real_workout_context():
    print("Получаем историю тренировок...")

    training = get_registered_athlete_unified_training(
        athlete_id=ATHLETE_ID,
        days=HISTORY_DAYS,
    )

    activities = prepare_comparison_activities(
        training["activities"]
    )

    cycling_activities = [
        activity
        for activity in activities
        if activity.get("type") == "cycling"
    ]

    cycling_activities.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    print("\n=== HISTORY STATISTICS ===")
    pprint(training.get("statistics"))

    results = []

    context_counts = Counter()
    confidence_counts = Counter()

    intervals_metadata_fields = Counter()
    garmin_metadata_fields = Counter()

    paired_events_count = 0

    unknown_activities = []
    conflicting_activities = []
    race_activities = []

    print("\n=== ACTIVITY CONTEXTS ===")

    for activity in cycling_activities:
        original = deepcopy(activity)

        context = classify_workout_context(
            activity
        )

        metadata = get_activity_source_metadata(
            activity
        )

        intervals = metadata["intervals"]
        garmin = metadata["garmin"]

        intervals_metadata_fields.update(
            intervals.keys()
        )

        garmin_metadata_fields.update(
            garmin.keys()
        )

        context_counts[
            context["activity_context"]
        ] += 1

        confidence_counts[
            context["confidence"]
        ] += 1

        if context["has_paired_event"]:
            paired_events_count += 1

        result = {
            "id": activity["id"],
            "date": activity["start_date"],
            "name": activity.get("name"),

            "context": context[
                "activity_context"
            ],

            "confidence": context[
                "confidence"
            ],

            "evidence": context[
                "evidence"
            ],

            "conflicting_evidence": context[
                "conflicting_evidence"
            ],

            "has_paired_event": context[
                "has_paired_event"
            ],

            "intervals_metadata_available": bool(
                intervals
            ),

            "garmin_metadata_available": bool(
                garmin
            ),
        }

        pprint(result)
        print()

        results.append(result)

        if context["activity_context"] == "unknown":
            unknown_activities.append(result)

        if context["conflicting_evidence"]:
            conflicting_activities.append(result)

        if context["activity_context"] == "race":
            race_activities.append(result)

        # Проверяем сохранение исходной активности.
        assert activity == original

        # Проверяем корректность результата.
        assert context["status"] == "ok"

        assert context["confidence"] in {
            "high",
            "medium",
            "low",
        }

    print("\n=== CONTEXT DISTRIBUTION ===")
    pprint(dict(context_counts))

    print("\n=== CONFIDENCE DISTRIBUTION ===")
    pprint(dict(confidence_counts))

    print("\n=== INTERVALS METADATA FIELDS ===")
    pprint(
        dict(
            sorted(
                intervals_metadata_fields.items()
            )
        )
    )

    print("\n=== GARMIN METADATA FIELDS ===")
    pprint(
        dict(
            sorted(
                garmin_metadata_fields.items()
            )
        )
    )

    print("\n=== RACE ACTIVITIES ===")
    pprint(race_activities)

    print("\n=== UNKNOWN ACTIVITIES ===")
    pprint(unknown_activities)

    print("\n=== CONFLICTING ACTIVITIES ===")
    pprint(conflicting_activities)

    print("\n=== FINAL STATISTICS ===")

    pprint({
        "cycling_activities": len(
            cycling_activities
        ),

        "processed_activities": len(results),

        "structured_workouts": context_counts[
            "structured_workout"
        ],

        "race_activities": context_counts[
            "race"
        ],

        "warmup_activities": context_counts[
            "warmup"
        ],

        "cooldown_activities": context_counts[
            "cooldown"
        ],

        "group_ride_activities": context_counts[
            "group_ride"
        ],

        "free_ride_activities": context_counts[
            "free_ride"
        ],

        "unknown_activities": len(
            unknown_activities
        ),

        "conflicting_activities": len(
            conflicting_activities
        ),

        "paired_events_count": (
            paired_events_count
        ),

        "intervals_metadata_available": sum(
            result["intervals_metadata_available"]
            for result in results
        ),

        "garmin_metadata_available": sum(
            result["garmin_metadata_available"]
            for result in results
        ),
    })

    assert cycling_activities, (
        "Не найдены велосипедные тренировки"
    )

    assert len(results) == len(
        cycling_activities
    )

    assert sum(
        context_counts.values()
    ) == len(results)

    assert sum(
        confidence_counts.values()
    ) == len(results)

    print(
        "\nREAL WORKOUT CONTEXT "
        "DIAGNOSTIC TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_context()