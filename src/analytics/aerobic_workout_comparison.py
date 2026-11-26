from collections import Counter
from datetime import timedelta
from statistics import mean

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.aerobic_segment_comparison import (
    compare_aerobic_segments,
    compare_aerobic_progression,
    calculate_relative_difference,
    get_segment_profile,
)


DEFAULT_HISTORY_DAYS = 30

DEFAULT_MAX_HISTORICAL_WORKOUTS = 5


SIMILARITY_WEIGHTS = {
    "power": 30,
    "duration": 20,
    "accumulated_work": 20,
    "previous_work": 15,
    "ftp_intensity": 10,
    "cadence": 5,
}


def calculate_component_score(
    difference,
    maximum_difference,
    weight,
):
    """
    Рассчитывает вклад отдельного
    критерия в общую оценку сходства.

    Неизвестное значение получает
    половину максимального балла.
    """
    if difference is None:
        return weight * 0.5

    similarity = max(
        0.0,
        1.0 - abs(difference) / maximum_difference,
    )

    return similarity * weight


def get_valid_segments(workout):
    """
    Возвращает проанализированные
    сегменты в хронологическом порядке.
    """
    analysis = workout.get("analysis") or {}

    segments = []

    seen_ids = set()

    for segment in analysis.get("segments", []):
        if not isinstance(segment, dict):
            continue

        if segment.get("status") not in {
            "ok",
            "partial",
        }:
            continue

        segment_id = segment.get("segment_id")

        if not segment_id or segment_id in seen_ids:
            continue

        start = parse_activity_date(
            segment.get("analysis_start")
        )

        end = parse_activity_date(
            segment.get("analysis_end")
        )

        if (
            start is None
            or end is None
            or end < start
        ):
            continue

        seen_ids.add(segment_id)

        segments.append(segment)

    segments.sort(
        key=lambda segment: (
            parse_activity_date(
                segment["analysis_start"]
            ),
            segment["segment_id"],
        )
    )

    return segments


def calculate_segment_similarity(comparison):
    """
    Оценивает сходство сегментов
    независимо от величины ЧСС,
    EF и аэробного дрейфа.

    Использует только характеристики
    нагрузки и контекст выполнения.
    """
    quality = comparison["comparison_quality"]

    if not quality["heart_rate_comparable"]:
        return {
            "eligible": False,
            "score": None,
            "components": {},
        }

    reference = comparison["reference"]

    candidate = comparison["candidate"]

    power_difference = (
        calculate_relative_difference(
            reference["average_power"],
            candidate["average_power"],
        )
    )

    duration_difference = (
        calculate_relative_difference(
            reference["duration_seconds"],
            candidate["duration_seconds"],
        )
    )

    accumulated_difference = (
        calculate_relative_difference(
            reference["accumulated_work_kj"],
            candidate["accumulated_work_kj"],
        )
    )

    previous_difference = (
        calculate_relative_difference(
            reference["previous_work_kj"],
            candidate["previous_work_kj"],
        )
    )

    ftp_difference = None

    if (
        reference["ftp_intensity_percent"] is not None
        and candidate["ftp_intensity_percent"] is not None
    ):
        ftp_difference = abs(
            reference["ftp_intensity_percent"]
            - candidate["ftp_intensity_percent"]
        )

    cadence_difference = None

    if (
        reference["average_cadence"] is not None
        and candidate["average_cadence"] is not None
        and reference["cadence_coverage_ratio"] is not None
        and candidate["cadence_coverage_ratio"] is not None
        and reference["cadence_coverage_ratio"] >= 0.90
        and candidate["cadence_coverage_ratio"] >= 0.90
    ):
        cadence_difference = abs(
            reference["average_cadence"]
            - candidate["average_cadence"]
        )

    components = {
        "power": calculate_component_score(
            power_difference,
            0.05,
            SIMILARITY_WEIGHTS["power"],
        ),

        "duration": calculate_component_score(
            duration_difference,
            0.20,
            SIMILARITY_WEIGHTS["duration"],
        ),

        "accumulated_work": calculate_component_score(
            accumulated_difference,
            0.20,
            SIMILARITY_WEIGHTS["accumulated_work"],
        ),

        "previous_work": calculate_component_score(
            previous_difference,
            0.15,
            SIMILARITY_WEIGHTS["previous_work"],
        ),

        "ftp_intensity": calculate_component_score(
            ftp_difference,
            5,
            SIMILARITY_WEIGHTS["ftp_intensity"],
        ),

        "cadence": calculate_component_score(
            cadence_difference,
            10,
            SIMILARITY_WEIGHTS["cadence"],
        ),
    }

    score = sum(components.values())

    return {
        "eligible": True,

        "score": round(score, 4),

        "components": {
            key: round(value, 4)

            for key, value in components.items()
        },
    }


def evaluate_segment_pairs(
    reference_workout,
    candidate_workout,
    reference_segments,
    candidate_segments,
):
    """
    Формирует матрицу всех возможных
    сравнений двух тренировок.
    """
    matrix = []

    for reference_segment in reference_segments:
        row = []

        for candidate_segment in candidate_segments:

            comparison = compare_aerobic_segments(
                reference_segment=reference_segment,

                candidate_segment=candidate_segment,

                mode="between_workouts",

                reference_conditions=reference_workout.get(
                    "conditions"
                ),

                candidate_conditions=candidate_workout.get(
                    "conditions"
                ),
            )

            similarity = calculate_segment_similarity(
                comparison
            )

            row.append({
                "comparison": comparison,

                "similarity": similarity,
            })

        matrix.append(row)

    return matrix


def find_optimal_segment_pairs(
    matrix,
    reference_count,
    candidate_count,
):
    """
    Сопоставляет сегменты один к одному
    с сохранением хронологического порядка.

    Сначала максимизирует количество
    сопоставимых пар.

    При одинаковом количестве пар
    максимизирует суммарное сходство.
    """
    dp = [
        [
            (0, 0.0)

            for _ in range(candidate_count + 1)
        ]

        for _ in range(reference_count + 1)
    ]

    actions = [
        [
            None

            for _ in range(candidate_count + 1)
        ]

        for _ in range(reference_count + 1)
    ]

    for i in range(1, reference_count + 1):
        actions[i][0] = "skip_reference"

    for j in range(1, candidate_count + 1):
        actions[0][j] = "skip_candidate"

    for i in range(1, reference_count + 1):

        for j in range(1, candidate_count + 1):

            options = [
                (
                    dp[i - 1][j],
                    "skip_reference",
                ),

                (
                    dp[i][j - 1],
                    "skip_candidate",
                ),
            ]

            similarity = matrix[i - 1][j - 1][
                "similarity"
            ]

            if similarity["eligible"]:

                previous_count, previous_score = (
                    dp[i - 1][j - 1]
                )

                options.append((
                    (
                        previous_count + 1,

                        round(
                            previous_score
                            + similarity["score"],
                            4,
                        ),
                    ),

                    "match",
                ))

            best_value, best_action = max(
                options,

                key=lambda option: (
                    option[0][0],

                    option[0][1],

                    option[1] == "match",
                ),
            )

            dp[i][j] = best_value

            actions[i][j] = best_action

    pairs = []

    i = reference_count
    j = candidate_count

    while i > 0 or j > 0:

        action = actions[i][j]

        if action == "match":

            pairs.append((
                i - 1,
                j - 1,
            ))

            i -= 1
            j -= 1

        elif action == "skip_reference":
            i -= 1

        elif action == "skip_candidate":
            j -= 1

        else:
            break

    pairs.reverse()

    return pairs


def compare_aerobic_workouts(
    reference_workout,
    candidate_workout,
):
    """
    Сравнивает аэробные сегменты
    двух тренировок.

    Каждый сегмент используется
    не более одного раза.
    """
    reference_id = reference_workout.get(
        "activity_id"
    )

    candidate_id = candidate_workout.get(
        "activity_id"
    )

    reference_segments = get_valid_segments(
        reference_workout
    )

    candidate_segments = get_valid_segments(
        candidate_workout
    )

    result = {
        "status": "insufficient_data",

        "reference_activity_id": reference_id,

        "candidate_activity_id": candidate_id,

        "candidate_activity_name": candidate_workout.get(
            "activity_name"
        ),

        "candidate_start_date": candidate_workout.get(
            "start_date"
        ),

        "comparison_method": (
            "chronological_one_to_one"
        ),

        "pairs": [],

        "unmatched_reference_segment_ids": [
            segment["segment_id"]

            for segment in reference_segments
        ],

        "unmatched_candidate_segment_ids": [
            segment["segment_id"]

            for segment in candidate_segments
        ],

        "summary": {
            "reference_segments_count": len(
                reference_segments
            ),

            "candidate_segments_count": len(
                candidate_segments
            ),

            "evaluated_pairs_count": 0,

            "eligible_pairs_count": 0,

            "matched_pairs_count": 0,

            "reference_coverage_ratio": 0,

            "candidate_coverage_ratio": 0,

            "average_similarity_score": None,

            "drift_comparable_pairs_count": 0,

            "comparison_quality_counts": {},

            "blocker_counts": {},
        },

        "fitness_change": None,
    }

    if (
        not reference_id
        or not candidate_id
    ):
        return {
            **result,
            "reason": "missing_activity_id",
        }

    if reference_id == candidate_id:
        return {
            **result,

            "status": "not_comparable",

            "reason": "same_activity",
        }

    reference_date = parse_activity_date(
        reference_workout.get("start_date")
    )

    candidate_date = parse_activity_date(
        candidate_workout.get("start_date")
    )

    if (
        reference_date is None
        or candidate_date is None
    ):
        return {
            **result,
            "reason": "missing_activity_date",
        }

    if candidate_date >= reference_date:
        return {
            **result,

            "status": "not_comparable",

            "reason": "candidate_not_historical",
        }

    if (
        not reference_segments
        or not candidate_segments
    ):
        return {
            **result,
            "reason": "missing_aerobic_segments",
        }

    matrix = evaluate_segment_pairs(
        reference_workout=reference_workout,

        candidate_workout=candidate_workout,

        reference_segments=reference_segments,

        candidate_segments=candidate_segments,
    )

    optimal_pairs = find_optimal_segment_pairs(
        matrix=matrix,

        reference_count=len(reference_segments),

        candidate_count=len(candidate_segments),
    )

    matched = []

    matched_reference_ids = set()

    matched_candidate_ids = set()

    quality_counts = Counter()

    blocker_counts = Counter()

    eligible_count = 0

    for row in matrix:

        for item in row:

            if item["similarity"]["eligible"]:
                eligible_count += 1

            else:
                blocker_counts.update(
                    item["comparison"][
                        "comparison_quality"
                    ]["blockers"]
                )

    for i, j in optimal_pairs:

        item = matrix[i][j]

        reference_segment = reference_segments[i]

        candidate_segment = candidate_segments[j]

        reference_segment_id = reference_segment[
            "segment_id"
        ]

        candidate_segment_id = candidate_segment[
            "segment_id"
        ]

        matched_reference_ids.add(
            reference_segment_id
        )

        matched_candidate_ids.add(
            candidate_segment_id
        )

        comparison = item["comparison"]

        quality_counts.update([
            comparison["comparison_quality"][
                "quality"
            ]
        ])

        matched.append({
            "reference_segment_id": (
                reference_segment_id
            ),

            "candidate_segment_id": (
                candidate_segment_id
            ),

            "similarity": item["similarity"],

            "comparison": comparison,
        })

    matched_count = len(matched)

    if not matched:
        status = "not_comparable"

    elif (
        matched_count < len(reference_segments)

        or matched_count < len(candidate_segments)

        or any(
            pair["comparison"]["status"] != "ok"

            for pair in matched
        )
    ):
        status = "partial"

    else:
        status = "ok"

    average_score = (
        round(
            mean(
                pair["similarity"]["score"]

                for pair in matched
            ),
            4,
        )

        if matched
        else None
    )

    return {
        **result,

        "status": status,

        "pairs": matched,

        "unmatched_reference_segment_ids": [
            segment["segment_id"]

            for segment in reference_segments

            if segment["segment_id"]
            not in matched_reference_ids
        ],

        "unmatched_candidate_segment_ids": [
            segment["segment_id"]

            for segment in candidate_segments

            if segment["segment_id"]
            not in matched_candidate_ids
        ],

        "summary": {
            "reference_segments_count": len(
                reference_segments
            ),

            "candidate_segments_count": len(
                candidate_segments
            ),

            "evaluated_pairs_count": (
                len(reference_segments)
                * len(candidate_segments)
            ),

            "eligible_pairs_count": eligible_count,

            "matched_pairs_count": matched_count,

            "reference_coverage_ratio": round(
                matched_count
                / len(reference_segments),
                4,
            ),

            "candidate_coverage_ratio": round(
                matched_count
                / len(candidate_segments),
                4,
            ),

            "average_similarity_score": average_score,

            "drift_comparable_pairs_count": sum(
                pair["comparison"]["drift_comparable"]

                for pair in matched
            ),

            "comparison_quality_counts": dict(
                quality_counts
            ),

            "blocker_counts": dict(
                blocker_counts
            ),
        },
    }


def select_historical_workouts(
    reference_workout,
    historical_workouts,
    days=DEFAULT_HISTORY_DAYS,
):
    """
    Отбирает уникальные тренировки
    за заданный исторический период.

    Период отсчитывается от даты
    анализируемой тренировки.
    """
    if (
        not isinstance(days, int)
        or isinstance(days, bool)
        or days <= 0
    ):
        raise ValueError(
            "days должен быть положительным целым числом"
        )

    reference_date = parse_activity_date(
        reference_workout.get("start_date")
    )

    if reference_date is None:
        return {
            "selected": [],

            "skipped": [],

            "reason": "missing_reference_date",
        }

    cutoff_date = (
        reference_date
        - timedelta(days=days)
    )

    reference_id = reference_workout.get(
        "activity_id"
    )

    selected = []
    skipped = []

    seen_ids = set()

    for workout in historical_workouts:

        if not isinstance(workout, dict):
            skipped.append({
                "activity_id": None,
                "reason": "invalid_workout",
            })

            continue

        activity_id = workout.get(
            "activity_id"
        )

        start_date = parse_activity_date(
            workout.get("start_date")
        )

        reason = None

        if not activity_id:
            reason = "missing_activity_id"

        elif activity_id == reference_id:
            reason = "same_activity"

        elif activity_id in seen_ids:
            reason = "duplicate_activity"

        elif start_date is None:
            reason = "missing_activity_date"

        elif start_date >= reference_date:
            reason = "not_historical"

        elif start_date < cutoff_date:
            reason = "outside_history_period"

        if reason is not None:
            skipped.append({
                "activity_id": activity_id,
                "reason": reason,
            })

            continue

        seen_ids.add(activity_id)

        selected.append(workout)

    selected.sort(
        key=lambda workout: (
            parse_activity_date(
                workout["start_date"]
            ),

            workout["activity_id"],
        ),

        reverse=True,
    )

    return {
        "selected": selected,

        "skipped": skipped,

        "reference_date": (
            reference_date.isoformat()
        ),

        "cutoff_date": cutoff_date.isoformat(),

        "history_days": days,
    }


def summarize_historical_comparison(comparison):
    """
    Формирует статистику одной
    исторической тренировки.

    Не объединяет пары разных
    тренировок в независимую выборку.
    """
    differences = [
        pair["comparison"]["differences"]

        for pair in comparison["pairs"]
    ]

    def average_field(field):

        values = [
            item[field]

            for item in differences

            if item.get(field) is not None
        ]

        return (
            round(mean(values), 2)
            if values
            else None
        )

    return {
        "activity_id": comparison[
            "candidate_activity_id"
        ],

        "activity_name": comparison[
            "candidate_activity_name"
        ],

        "start_date": comparison[
            "candidate_start_date"
        ],

        "matched_pairs_count": len(
            comparison["pairs"]
        ),

        "average_power_difference_watts": (
            average_field("average_power_watts")
        ),

        "average_heart_rate_difference_bpm": (
            average_field("heart_rate_bpm")
        ),

        "average_efficiency_change_percent": (
            average_field(
                "efficiency_change_percent"
            )
        ),

        "average_drift_difference_pp": (
            average_field("drift_difference_pp")
        ),

        "average_similarity_score": comparison[
            "summary"
        ]["average_similarity_score"],

        "fitness_change": None,
    }


def analyze_aerobic_workout_history(
    reference_workout,
    historical_workouts,
    days=DEFAULT_HISTORY_DAYS,
    max_workouts=DEFAULT_MAX_HISTORICAL_WORKOUTS,
):
    """
    Сравнивает анализируемую тренировку
    с историей аэробных тренировок.

    Принимает уже рассчитанную
    аэробную аналитику.

    Не загружает FIT и не обращается
    к внешним API.
    """
    if (
        not isinstance(max_workouts, int)
        or isinstance(max_workouts, bool)
        or max_workouts <= 0
    ):
        raise ValueError(
            "max_workouts должен быть положительным целым числом"
        )

    selection = select_historical_workouts(
        reference_workout=reference_workout,

        historical_workouts=historical_workouts,

        days=days,
    )

    reference_segments = get_valid_segments(
        reference_workout
    )

    progression = compare_aerobic_progression({
        "segments": reference_segments,
    })

    result = {
        "status": "insufficient_data",

        "reference_activity_id": reference_workout.get(
            "activity_id"
        ),

        "history_days": days,

        "within_workout_progression": progression,

        "historical_comparisons": [],

        "historical_workout_summaries": [],

        "skipped_workouts": selection["skipped"],

        "non_comparable_workouts": [],

        "summary": {
            "reference_segments_count": len(
                reference_segments
            ),

            "selected_historical_workouts_count": len(
                selection["selected"]
            ),

            "compared_workouts_count": 0,

            "comparable_workouts_found": 0,

            "returned_workouts_count": 0,

            "matched_pairs_count": 0,

            "unique_reference_segments_matched": 0,

            "drift_comparable_pairs_count": 0,
        },

        "fitness_change": None,
    }

    if selection.get("reason"):
        return {
            **result,

            "reason": selection["reason"],
        }

    if not reference_workout.get("activity_id"):
        return {
            **result,

            "reason": "missing_reference_activity_id",
        }

    if not reference_segments:
        return {
            **result,

            "reason": "missing_reference_segments",
        }

    comparisons = []

    non_comparable = []

    for workout in selection["selected"]:

        comparison = compare_aerobic_workouts(
            reference_workout,

            workout,
        )

        if comparison["pairs"]:
            comparisons.append(comparison)

        else:
            non_comparable.append({
                "activity_id": comparison[
                    "candidate_activity_id"
                ],

                "status": comparison["status"],

                "reason": comparison.get(
                    "reason",
                    "no_eligible_pairs",
                ),

                "summary": comparison["summary"],
            })

    # Приоритет:
    # 1. Количество сопоставимых сегментов.
    # 2. Средняя оценка сходства.
    # 3. Более свежая тренировка.
    #
    # ЧСС, EF и дрейф не используются
    # для ранжирования.

    comparisons.sort(
        key=lambda comparison: (
            comparison["summary"][
                "matched_pairs_count"
            ],

            comparison["summary"][
                "average_similarity_score"
            ],

            parse_activity_date(
                comparison["candidate_start_date"]
            ),

            comparison["candidate_activity_id"],
        ),

        reverse=True,
    )

    returned = comparisons[:max_workouts]

    unique_reference_ids = {
        pair["reference_segment_id"]

        for comparison in returned

        for pair in comparison["pairs"]
    }

    total_pairs = sum(
        comparison["summary"][
            "matched_pairs_count"
        ]

        for comparison in returned
    )

    total_drift_pairs = sum(
        comparison["summary"][
            "drift_comparable_pairs_count"
        ]

        for comparison in returned
    )

    if not returned:
        status = "no_comparable_workouts"

    elif (
        len(unique_reference_ids)
        < len(reference_segments)

        or any(
            comparison["status"] != "ok"

            for comparison in returned
        )
    ):
        status = "partial"

    else:
        status = "ok"

    return {
        **result,

        "status": status,

        "historical_comparisons": returned,

        "historical_workout_summaries": [
            summarize_historical_comparison(
                comparison
            )

            for comparison in returned
        ],

        "non_comparable_workouts": non_comparable,

        "summary": {
            "reference_segments_count": len(
                reference_segments
            ),

            "selected_historical_workouts_count": len(
                selection["selected"]
            ),

            "compared_workouts_count": len(
                selection["selected"]
            ),

            "comparable_workouts_found": len(
                comparisons
            ),

            "returned_workouts_count": len(
                returned
            ),

            "matched_pairs_count": total_pairs,

            "unique_reference_segments_matched": len(
                unique_reference_ids
            ),

            "drift_comparable_pairs_count": (
                total_drift_pairs
            ),
        },

        "limitations": [
            (
                "Используются полные аэробные "
                "сегменты без выравнивания окон"
            ),
            (
                "Сопоставление сохраняет "
                "хронологический порядок"
            ),
            (
                "Каждый сегмент используется "
                "однократно внутри сравнения "
                "двух тренировок"
            ),
            (
                "Один новый сегмент может "
                "сравниваться с несколькими "
                "историческими тренировками"
            ),
            (
                "Количество пар не является "
                "количеством независимых "
                "физиологических наблюдений"
            ),
            (
                "Величина ЧСС, EF и дрейфа "
                "не используется для ранжирования"
            ),
            (
                "Отсутствие изменений ЧСС "
                "не доказывает отсутствие "
                "изменений физической формы"
            ),
        ],
    }