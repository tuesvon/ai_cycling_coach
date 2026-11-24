from collections import Counter
from datetime import datetime, timedelta, timezone
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

from src.analytics.workout_signature import (
    build_workout_signature,
)

from src.analytics.workout_similarity import (
    find_similar_workout_signatures,
    get_comparison_family,
)


ATHLETE_ID = "i280488"

FALLBACK_FTP = 304

COMPARISON_DAYS = 30


REFERENCE_WORKOUTS = {
    "intervals:i213726048": {
        "label": "ANAEROBIC INTERVALS",
        "date": "2026-11-23",
    },

    "intervals:i210870369": {
        "label": "SHORT HIGH INTENSITY",
        "date": "2026-11-16",
    },

    "intervals:i212166682": {
        "label": "MIXED ENDURANCE",
        "date": "2026-11-19",
    },

    "intervals:i212444728": {
        "label": "RACE",
        "date": "2026-11-20",
    },
}


def get_history_days():
    """
    Загружает достаточно истории,
    чтобы у каждой референсной
    тренировки было полных 30 дней
    для поиска предыдущих активностей.
    """
    oldest_date = min(
        datetime.fromisoformat(
            workout["date"]
        ).replace(tzinfo=timezone.utc)

        for workout in REFERENCE_WORKOUTS.values()
    )

    now = datetime.now(
        timezone.utc
    )

    return max(
        COMPARISON_DAYS,

        (
            now - oldest_date
        ).days + COMPARISON_DAYS + 2,
    )


def load_workout_signatures():
    """
    Загружает FIT каждой выбранной
    активности только один раз.

    Использует FTP из метаданных,
    если он доступен.
    """
    history_days = get_history_days()

    print(
        "Загружаем историю за",
        history_days,
        "дней..."
    )

    training = get_registered_athlete_unified_training(
        athlete_id=ATHLETE_ID,
        days=history_days,
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

    now = datetime.now(
        timezone.utc
    )

    selected = []
    seen_ids = set()

    for activity in activities:
        if activity.get("type") != "cycling":
            continue

        activity_id = activity.get("id")

        if activity_id is None:
            continue

        if activity_id in seen_ids:
            continue

        try:
            activity_date = parse_activity_date(
                activity["start_date"]
            )

        except (KeyError, TypeError, ValueError):
            continue

        if activity_date > now:
            continue

        selected.append(activity)

        seen_ids.add(activity_id)

    selected.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    signatures = []
    errors = []

    print("\n=== HISTORY STATISTICS ===")
    pprint(training.get("statistics"))

    print("\n=== LOADING WORKOUT SIGNATURES ===")

    for index, activity in enumerate(
        selected,
        start=1,
    ):
        print(
            f"\n[{index}/{len(selected)}]",
            activity.get("name"),
        )

        try:
            content = downloader(activity)

            records = read_fit_bytes(
                content
            )

            signature = build_workout_signature(
                activity=activity,
                records=records,
                fallback_ftp=FALLBACK_FTP,
            )

        except Exception as error:
            errors.append({
                "activity_id": activity["id"],
                "name": activity.get("name"),
                "start_date": activity["start_date"],
                "error_type": type(error).__name__,
            })

            print(
                "ERROR:",
                type(error).__name__,
            )

            continue

        signatures.append(signature)

        ftp_info = signature.get(
            "ftp_info",
            {},
        )

        structure = signature.get(
            "effort_structure",
            {},
        )

        pprint({
            "activity_id": signature.get(
                "activity_id"
            ),

            "status": signature.get(
                "status"
            ),

            "reason": signature.get(
                "reason"
            ),

            "ftp": ftp_info.get("ftp"),

            "ftp_source": ftp_info.get(
                "source"
            ),

            "comparison_family": (
                get_comparison_family(
                    signature
                )
            ),

            "context": signature.get(
                "activity_context",
                {},
            ).get("activity_context"),

            "root_efforts_count": structure.get(
                "root_efforts_count"
            ),

            "unique_work_seconds": structure.get(
                "unique_work_seconds"
            ),
        })

    assert len(signatures) + len(errors) == len(
        selected
    )

    return {
        "signatures": signatures,
        "errors": errors,
        "selected_workouts_count": len(selected),
    }


def print_reference_signature(signature):
    """
    Выводит основные характеристики
    референсной тренировки.
    """
    print("\n=== REFERENCE WORKOUT ===")

    pprint({
        "activity_id": signature.get(
            "activity_id"
        ),

        "name": signature.get(
            "activity_name"
        ),

        "date": signature.get(
            "start_date"
        ),

        "ftp_info": signature.get(
            "ftp_info"
        ),

        "comparison_family": (
            get_comparison_family(
                signature
            )
        ),

        "activity_context": signature.get(
            "activity_context"
        ),

        "conditions": signature.get(
            "conditions"
        ),

        "load_profile": signature.get(
            "load_profile"
        ),

        "data_quality": signature.get(
            "data_quality"
        ),
    })

    structure = signature.get(
        "effort_structure",
        {},
    )

    print("\n=== REFERENCE EFFORT SUMMARY ===")

    pprint({
        "root_efforts_count": structure.get(
            "root_efforts_count"
        ),

        "nested_efforts_count": structure.get(
            "nested_efforts_count"
        ),

        "unique_work_seconds": structure.get(
            "unique_work_seconds"
        ),

        "work_fraction": structure.get(
            "work_fraction"
        ),

        "root_effort_summary": structure.get(
            "root_effort_summary"
        ),

        "between_effort_gaps": structure.get(
            "between_effort_gaps"
        ),
    })


def print_candidate_summary(candidate):
    """
    Выводит результат оценки сходства.
    """
    pprint({
        "activity_id": candidate.get(
            "candidate_activity_id"
        ),

        "name": candidate.get(
            "candidate_activity_name"
        ),

        "date": candidate.get(
            "candidate_start_date"
        ),

        "status": candidate.get(
            "status"
        ),

        "score": candidate.get(
            "score"
        ),

        "raw_score": candidate.get(
            "raw_score"
        ),

        "similarity_level": candidate.get(
            "similarity_level"
        ),

        "comparison_type": candidate.get(
            "comparison_type"
        ),

        "comparison_scope": candidate.get(
            "comparison_scope"
        ),

        "candidate_context": candidate.get(
            "candidate_context"
        ),

        "candidate_family": candidate.get(
            "candidate_family"
        ),

        "matched_efforts_count": candidate.get(
            "matched_efforts_count"
        ),

        "reference_match_coverage": candidate.get(
            "reference_match_coverage"
        ),

        "candidate_match_coverage": candidate.get(
            "candidate_match_coverage"
        ),

        "criteria_coverage": candidate.get(
            "criteria_coverage"
        ),

        "full_workout_comparison_candidate": (
            candidate.get(
                "full_workout_comparison_candidate"
            )
        ),

        "components": candidate.get(
            "components"
        ),

        "conditions": candidate.get(
            "conditions"
        ),

        "limitations": candidate.get(
            "limitations"
        ),
    })


def validate_similarity_result(
    reference,
    result,
):
    """
    Проверяет обязательные ограничения
    алгоритма поиска похожих тренировок.
    """
    reference_date = parse_activity_date(
        reference["start_date"]
    )

    cutoff_date = reference_date - timedelta(
        days=COMPARISON_DAYS
    )

    evaluations = result["evaluations"]

    candidate_ids = [
        evaluation["candidate_activity_id"]
        for evaluation in evaluations
    ]

    assert len(candidate_ids) == len(
        set(candidate_ids)
    )

    assert reference["activity_id"] not in (
        candidate_ids
    )

    for evaluation in evaluations:
        score = evaluation.get(
            "score"
        )

        if score is not None:
            assert 0 <= score <= 100

        candidate_date = parse_activity_date(
            evaluation["candidate_start_date"]
        )

        assert (
            cutoff_date
            <= candidate_date
            < reference_date
        )

        pairs = evaluation.get(
            "matched_efforts",
            [],
        )

        reference_ids = [
            pair["reference_effort_id"]
            for pair in pairs
        ]

        candidate_effort_ids = [
            pair["candidate_effort_id"]
            for pair in pairs
        ]

        assert len(reference_ids) == len(
            set(reference_ids)
        )

        assert len(candidate_effort_ids) == len(
            set(candidate_effort_ids)
        )

        assert all(
            pair["can_match"]
            for pair in pairs
        )

    similar = result["similar_workouts"]

    for candidate in similar:
        assert candidate["score"] >= result[
            "minimum_similarity_score"
        ]

        assert candidate[
            "comparison_scope"
        ] != "none"

    scores = [
        candidate["score"]
        for candidate in similar
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )

    assert result[
        "similar_workouts_count"
    ] == len(similar)

    assert result[
        "evaluated_workouts_count"
    ] == len(evaluations)


def test_real_workout_similarity():
    loaded = load_workout_signatures()

    signatures = loaded["signatures"]

    signatures_by_id = {
        signature["activity_id"]: signature
        for signature in signatures
    }

    successful = [
        signature
        for signature in signatures
        if signature["status"] == "ok"
    ]

    insufficient = [
        signature
        for signature in signatures
        if signature["status"] != "ok"
    ]

    print("\n=== SIGNATURE STATISTICS ===")

    pprint({
        "selected_workouts": loaded[
            "selected_workouts_count"
        ],

        "successful_signatures": len(
            successful
        ),

        "insufficient_data": len(
            insufficient
        ),

        "download_or_analysis_errors": len(
            loaded["errors"]
        ),

        "ftp_sources": dict(
            Counter(
                signature.get(
                    "ftp_info",
                    {},
                ).get("source")

                for signature in signatures
            )
        ),

        "ftp_values": dict(
            Counter(
                signature.get(
                    "ftp_info",
                    {},
                ).get("ftp")

                for signature in signatures
            )
        ),

        "comparison_families": dict(
            Counter(
                get_comparison_family(signature)
                for signature in successful
            )
        ),
    })

    print("\n=== INSUFFICIENT DATA WORKOUTS ===")

    for signature in insufficient:
        pprint({
            "id": signature["activity_id"],
            "name": signature.get("activity_name"),
            "reason": signature.get("reason"),
        })

    print("\n=== LOADING ERRORS ===")
    pprint(loaded["errors"])

    scenario_summaries = []

    missing_references = []
    insufficient_references = []

    for reference_id, settings in (
        REFERENCE_WORKOUTS.items()
    ):
        print("\n" + "=" * 75)

        print(
            "SCENARIO:",
            settings["label"],
        )

        reference = signatures_by_id.get(
            reference_id
        )

        if reference is None:
            missing_references.append(
                reference_id
            )

            print(
                "REFERENCE NOT FOUND:",
                reference_id,
            )

            continue

        if reference["status"] != "ok":
            insufficient_references.append(
                reference_id
            )

            print(
                "REFERENCE INSUFFICIENT DATA:",
                reference.get("reason"),
            )

            continue

        print_reference_signature(
            reference
        )

        result = find_similar_workout_signatures(
            reference=reference,
            candidates=signatures,
            days=COMPARISON_DAYS,
        )

        validate_similarity_result(
            reference,
            result,
        )

        print("\n=== SEARCH RESULT ===")

        pprint({
            "status": result["status"],

            "evaluated_workouts_count": result[
                "evaluated_workouts_count"
            ],

            "similar_workouts_count": result[
                "similar_workouts_count"
            ],

            "skipped_workouts_count": result[
                "skipped_workouts_count"
            ],
        })

        print("\n=== SIMILAR WORKOUTS ===")

        for candidate in result[
            "similar_workouts"
        ]:
            print_candidate_summary(
                candidate
            )

            print("\nMATCHED EFFORTS:")

            pprint(
                candidate.get(
                    "matched_efforts",
                    [],
                )
            )

            print()

        print("\n=== ALL CANDIDATE SCORES ===")

        for evaluation in result[
            "evaluations"
        ]:
            print(
                evaluation.get(
                    "candidate_start_date"
                ),

                "|",

                evaluation.get(
                    "candidate_activity_name"
                ),

                "| SCORE:",

                evaluation.get("score"),

                "| LEVEL:",

                evaluation.get(
                    "similarity_level"
                ),

                "| MATCHED:",

                evaluation.get(
                    "matched_efforts_count"
                ),

                "| SCOPE:",

                evaluation.get(
                    "comparison_scope"
                ),
            )

        print("\n=== SKIPPED WORKOUTS ===")

        pprint(
            result["skipped_workouts"]
        )

        scenario_summaries.append({
            "scenario": settings["label"],

            "reference_name": reference[
                "activity_name"
            ],

            "status": result["status"],

            "evaluated_workouts": result[
                "evaluated_workouts_count"
            ],

            "similar_workouts": result[
                "similar_workouts_count"
            ],

            "best_candidates": [
                {
                    "name": candidate.get(
                        "candidate_activity_name"
                    ),

                    "date": candidate.get(
                        "candidate_start_date"
                    ),

                    "score": candidate.get(
                        "score"
                    ),

                    "similarity_level": candidate.get(
                        "similarity_level"
                    ),

                    "matched_efforts_count": (
                        candidate.get(
                            "matched_efforts_count"
                        )
                    ),

                    "comparison_scope": candidate.get(
                        "comparison_scope"
                    ),
                }

                for candidate in result[
                    "similar_workouts"
                ][:5]
            ],
        })

    print("\n" + "=" * 75)

    print("\n=== FINAL SCENARIO SUMMARIES ===")

    for summary in scenario_summaries:
        pprint(summary)
        print()

    print("\n=== FINAL TEST STATISTICS ===")

    pprint({
        "requested_scenarios": len(
            REFERENCE_WORKOUTS
        ),

        "processed_scenarios": len(
            scenario_summaries
        ),

        "missing_references": (
            missing_references
        ),

        "insufficient_references": (
            insufficient_references
        ),
    })

    assert successful, (
        "Нет успешно сформированных профилей"
    )

    assert not missing_references, (
        "Не найдены референсные тренировки"
    )

    assert not insufficient_references, (
        "Недостаточно данных "
        "референсных тренировок"
    )

    assert len(scenario_summaries) == len(
        REFERENCE_WORKOUTS
    )

    print(
        "\nREAL WORKOUT SIMILARITY "
        "DIAGNOSTIC TEST PASSED"
    )


if __name__ == "__main__":
    test_real_workout_similarity()