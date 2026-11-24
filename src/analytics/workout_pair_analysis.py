from collections import Counter
from datetime import timedelta
from statistics import median, mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    compare_matched_effort,
    prepare_effort_records,
    extract_record_window,
    get_valid_field,
    MIN_HEART_RATE_COVERAGE,
)

from src.analytics.workout_recovery_analysis import (
    compare_effort_recovery,
    RECOVERY_CHECKPOINTS,
)


def prepare_comparison_records(
    records,
    ignore_heart_rate=False,
):
    """
    Подготавливает записи для сравнения.

    Соблюдает настройки спортсмена
    и не изменяет исходные данные.
    """
    if not isinstance(records, list):
        raise ValueError(
            "FIT-записи должны быть списком"
        )

    prepared = []

    for record in records:
        if not isinstance(record, dict):
            continue

        copied = dict(record)

        if ignore_heart_rate:
            copied.pop("heart_rate", None)

        prepared.append(copied)

    return prepared


def get_signature_efforts(signature):
    """
    Возвращает корневые усилия
    в хронологическом порядке.
    """
    structure = signature.get(
        "effort_structure",
        {},
    )

    return sorted(
        structure.get("root_efforts", []),

        key=lambda effort: parse_activity_date(
            effort["start"]
        ),
    )


def find_next_effort(
    current_effort,
    efforts,
):
    """
    Ищет следующее корневое усилие.

    Учитывает все усилия тренировки,
    а не только сопоставленные пары.

    При пересечении усилий восстановление
    будет ограничено до нуля секунд.
    """
    current_start = parse_activity_date(
        current_effort["start"]
    )

    current_end = parse_activity_date(
        current_effort["end"]
    )

    current_id = current_effort[
        "effort_id"
    ]

    following = []

    for effort in efforts:
        if effort["effort_id"] == current_id:
            continue

        start = parse_activity_date(
            effort["start"]
        )

        end = parse_activity_date(
            effort["end"]
        )

        if (
            start >= current_start
            or end > current_end
        ):
            following.append(effort)

    if not following:
        return None

    return min(
        following,

        key=lambda effort: parse_activity_date(
            effort["start"]
        ),
    )


def compare_aligned_heart_rate(
    reference_effort,
    candidate_effort,
    reference_index,
    candidate_index,
):
    """
    Сравнивает пульс на совпадающих
    относительных секундах усилий.

    Пропущенные измерения не заменяются
    нулём и не интерполируются.
    """
    duration = min(
        reference_effort["duration_seconds"],
        candidate_effort["duration_seconds"],
    )

    reference_window = extract_record_window(
        indexed_records=reference_index,

        start=reference_effort["start"],

        duration_seconds=duration,
    )

    candidate_window = extract_record_window(
        indexed_records=candidate_index,

        start=candidate_effort["start"],

        duration_seconds=duration,
    )

    reference_values = []
    candidate_values = []

    for first, second in zip(
        reference_window,
        candidate_window,
    ):
        first_hr = get_valid_field(
            first,
            "heart_rate",
        )

        second_hr = get_valid_field(
            second,
            "heart_rate",
        )

        if (
            first_hr is None
            or second_hr is None
        ):
            continue

        reference_values.append(first_hr)
        candidate_values.append(second_hr)

    matched_seconds = len(
        reference_values
    )

    coverage = matched_seconds / duration

    result = {
        "status": "insufficient_data",

        "expected_seconds": duration,

        "matched_seconds": matched_seconds,

        "coverage_ratio": round(
            coverage,
            4,
        ),

        "reference_average_hr": None,

        "candidate_average_hr": None,

        "difference_bpm": None,
    }

    if (
        not matched_seconds
        or coverage < MIN_HEART_RATE_COVERAGE
    ):
        return result

    reference_average = mean(
        reference_values
    )

    candidate_average = mean(
        candidate_values
    )

    return {
        **result,

        "status": "ok",

        "reference_average_hr": round(
            reference_average,
            2,
        ),

        "candidate_average_hr": round(
            candidate_average,
            2,
        ),

        "difference_bpm": round(
            reference_average
            - candidate_average,
            2,
        ),
    }


def apply_aligned_heart_rate_comparison(
    effort_comparison,
    aligned_comparison,
):
    """
    Заменяет разницу средних значений
    пульса результатом сравнения
    совпадающих временных отсчётов.

    Не отменяет ограничения мощности
    и качества исходных записей.
    """
    result = {
        **effort_comparison,

        "aligned_heart_rate": (
            aligned_comparison
        ),
    }

    if "comparison_quality" not in result:
        return result

    quality = dict(
        result["comparison_quality"]
    )

    differences = dict(
        result["differences"]
    )

    limitations = list(
        quality["limitations"]
    )

    if aligned_comparison["status"] != "ok":
        limitations.append(
            "insufficient_aligned_heart_rate"
        )

        quality[
            "heart_rate_comparable"
        ] = False

        quality["quality"] = (
            "not_comparable"
        )

    elif (
        aligned_comparison["coverage_ratio"]
        < 1.0
    ):
        limitations.append(
            "partial_aligned_heart_rate"
        )

        if quality["quality"] != (
            "not_comparable"
        ):
            quality["quality"] = "limited"

    if quality["heart_rate_comparable"]:
        differences[
            "average_heart_rate_bpm"
        ] = aligned_comparison[
            "difference_bpm"
        ]

    else:
        differences[
            "average_heart_rate_bpm"
        ] = None

        result["status"] = "partial"

    quality["limitations"] = list(
        dict.fromkeys(limitations)
    )

    result["comparison_quality"] = quality
    result["differences"] = differences

    return result


def summarize_numeric_values(values):
    """
    Формирует описательную статистику.

    None и некорректные числа
    исключаются из расчёта.
    """
    valid = [
        value
        for value in values
        if is_valid_number(value)
    ]

    if not valid:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "count": len(valid),

        "mean": round(
            mean(valid),
            2,
        ),

        "median": round(
            median(valid),
            2,
        ),

        "minimum": min(valid),

        "maximum": max(valid),
    }


def summarize_pair_analysis(pairs):
    """
    Обобщает результаты всех пар.

    Несопоставимые значения пульса
    не участвуют в общей статистике.
    """
    quality_counts = Counter()

    limitations_counts = Counter()

    hr_differences = []

    preliminary_hr_differences = []
    limited_hr_differences = []

    power_differences = []

    baseline_differences = []

    previous_load_differences = []

    recovery_differences = {
        str(seconds): []

        for seconds in RECOVERY_CHECKPOINTS
    }

    recovery_quality_counts = {
        str(seconds): Counter()

        for seconds in RECOVERY_CHECKPOINTS
    }

    for pair in pairs:
        effort = pair.get(
            "effort_comparison",
            {},
        )

        quality = effort.get(
            "comparison_quality",
            {},
        )

        quality_name = quality.get(
            "quality",
            "unknown",
        )

        quality_counts[quality_name] += 1

        differences = effort.get(
            "differences",
            {},
        )

        limitations_counts.update(
            quality.get("limitations", [])
        )

        reference_metrics = effort.get(
            "reference",
            {},
        ).get("window_metrics", {})

        candidate_metrics = effort.get(
            "candidate",
            {},
        ).get("window_metrics", {})

        if (
            reference_metrics.get(
                "complete_power"
            )

            and candidate_metrics.get(
                "complete_power"
            )

            and reference_metrics.get(
                "complete_timing"
            )

            and candidate_metrics.get(
                "complete_timing"
            )
        ):
            power_differences.append(
                differences.get(
                    "average_power_watts"
                )
            )

        baseline_differences.append(
            quality.get(
                "baseline_hr_difference_bpm"
            )
        )

        previous_load_differences.append(
            quality.get(
                "previous_load_difference_kj"
            )
        )

        hr_difference = differences.get(
            "average_heart_rate_bpm"
        )

        if (
            quality.get(
                "heart_rate_comparable"
            )

            and is_valid_number(
                hr_difference
            )
        ):
            hr_differences.append(
                hr_difference
            )

            if quality_name == "preliminary":
                preliminary_hr_differences.append(
                    hr_difference
                )

            elif quality_name == "limited":
                limited_hr_differences.append(
                    hr_difference
                )

        recovery = pair.get(
            "recovery_comparison",
            {},
        )

        for seconds in RECOVERY_CHECKPOINTS:
            key = str(seconds)

            checkpoint = recovery.get(
                "checkpoints",
                {},
            ).get(key, {})

            checkpoint_quality = (
                checkpoint.get(
                    "comparison_quality",
                    "unknown",
                )
            )

            recovery_quality_counts[
                key
            ][checkpoint_quality] += 1

            if checkpoint.get("status") != "ok":
                continue

            value = checkpoint.get(
                "heart_rate_drop_difference_bpm"
            )

            if is_valid_number(value):
                recovery_differences[
                    key
                ].append(value)

    return {
        "analyzed_pairs_count": len(pairs),

        "heart_rate_comparable_pairs": len(
            hr_differences
        ),

        "quality_distribution": dict(
            quality_counts
        ),

        "power_difference_watts": (
            summarize_numeric_values(
                power_differences
            )
        ),

        "heart_rate_difference_bpm": (
            summarize_numeric_values(
                hr_differences
            )
        ),

        "heart_rate_by_quality": {
            "preliminary": (
                summarize_numeric_values(
                    preliminary_hr_differences
                )
            ),

            "limited": (
                summarize_numeric_values(
                    limited_hr_differences
                )
            ),
        },

        "baseline_hr_difference_bpm": (
            summarize_numeric_values(
                baseline_differences
            )
        ),

        "previous_load_difference_kj": (
            summarize_numeric_values(
                previous_load_differences
            )
        ),

        "recovery": {
            key: {
                "heart_rate_drop_difference_bpm": (
                    summarize_numeric_values(
                        values
                    )
                ),

                "quality_distribution": dict(
                    recovery_quality_counts[key]
                ),
            }

            for key, values
            in recovery_differences.items()
        },

        "limitations_distribution": dict(
            limitations_counts
        ),

        "fitness_change": None,

        "interpretation": (
            "Описательная статистика "
            "сопоставленных усилий. "
            "Пары не являются независимыми "
            "наблюдениями. "
            "Результат не доказывает "
            "изменение физической формы."
        ),
    }


def analyze_workout_pair(
    reference_signature,
    candidate_signature,
    similarity,
    reference_records,
    candidate_records,
):
    """
    Сравнивает все сопоставленные усилия
    двух тренировок.

    Объединяет анализ рабочих окон,
    предшествующей нагрузки
    и восстановления.
    """
    result = {
        "status": "insufficient_data",

        "reference_activity_id": (
            reference_signature.get(
                "activity_id"
            )
        ),

        "candidate_activity_id": (
            candidate_signature.get(
                "activity_id"
            )
        ),

        "similarity_score": similarity.get(
            "score"
        ),

        "comparison_scope": similarity.get(
            "comparison_scope"
        ),

        "pairs": [],

        "skipped_pairs": [],

        "fitness_change": None,
    }

    if (
        reference_signature.get("status") != "ok"
        or candidate_signature.get("status") != "ok"
    ):
        return {
            **result,

            "reason": (
                "Недостаточное качество "
                "профилей тренировок"
            ),
        }

    if (
        similarity.get("reference_activity_id")
        != reference_signature.get("activity_id")

        or similarity.get("candidate_activity_id")
        != candidate_signature.get("activity_id")
    ):
        raise ValueError(
            "Результат сходства относится "
            "к другим тренировкам"
        )

    if (
        similarity.get("status") != "ok"
        or similarity.get("comparison_scope")
        != "matched_efforts_only"
    ):
        return {
            **result,

            "status": "not_comparable",

            "reason": (
                "Не предусмотрено сравнение "
                "сопоставленных усилий"
            ),
        }

    matched_pairs = similarity.get(
        "matched_efforts",
        [],
    )

    if not matched_pairs:
        return {
            **result,

            "status": "no_matched_efforts",

            "reason": (
                "Нет сопоставленных усилий"
            ),
        }

    reference_conditions = (
        reference_signature.get(
            "conditions",
            {},
        )
    )

    candidate_conditions = (
        candidate_signature.get(
            "conditions",
            {},
        )
    )

    if (
        reference_conditions.get("ignore_power")
        or candidate_conditions.get("ignore_power")
    ):
        return {
            **result,

            "status": "not_comparable",

            "reason": (
                "Мощность исключена "
                "из анализа"
            ),
        }

    reference_ignore_hr = (
        reference_conditions.get(
            "ignore_heart_rate"
        ) is True
    )

    candidate_ignore_hr = (
        candidate_conditions.get(
            "ignore_heart_rate"
        ) is True
    )

    reference_records = prepare_comparison_records(
        records=reference_records,

        ignore_heart_rate=reference_ignore_hr,
    )

    candidate_records = prepare_comparison_records(
        records=candidate_records,

        ignore_heart_rate=candidate_ignore_hr,
    )

    reference_index = prepare_effort_records(
        reference_records
    )

    candidate_index = prepare_effort_records(
        candidate_records
    )

    reference_efforts = get_signature_efforts(
        reference_signature
    )

    candidate_efforts = get_signature_efforts(
        candidate_signature
    )

    reference_by_id = {
        effort["effort_id"]: effort

        for effort in reference_efforts
    }

    candidate_by_id = {
        effort["effort_id"]: effort

        for effort in candidate_efforts
    }

    conditions = dict(
        similarity.get("conditions") or {}
    )

    condition_limitations = list(
        conditions.get("limitations", [])
    )

    condition_limitations.extend(
        similarity.get("limitations", [])
    )

    if reference_ignore_hr or candidate_ignore_hr:
        condition_limitations.append(
            "heart_rate_excluded_by_settings"
        )

    conditions["limitations"] = list(
        dict.fromkeys(condition_limitations)
    )

    analyzed_pairs = []
    skipped_pairs = []

    used_reference_ids = set()
    used_candidate_ids = set()

    for pair in matched_pairs:
        reference_id = pair.get(
            "reference_effort_id"
        )

        candidate_id = pair.get(
            "candidate_effort_id"
        )

        pair_info = {
            "reference_effort_id": reference_id,

            "candidate_effort_id": candidate_id,

            "pair_score": pair.get(
                "pair_score"
            ),
        }

        if pair.get("can_match") is not True:
            skipped_pairs.append({
                **pair_info,

                "reason": "pair_not_matchable",
            })

            continue

        if (
            reference_id in used_reference_ids
            or candidate_id in used_candidate_ids
        ):
            skipped_pairs.append({
                **pair_info,

                "reason": "duplicate_effort",
            })

            continue

        reference_effort = reference_by_id.get(
            reference_id
        )

        candidate_effort = candidate_by_id.get(
            candidate_id
        )

        if (
            reference_effort is None
            or candidate_effort is None
        ):
            skipped_pairs.append({
                **pair_info,

                "reason": "effort_not_found",
            })

            continue

        try:
            effort_comparison = (
                compare_matched_effort(
                    reference_effort=reference_effort,

                    candidate_effort=candidate_effort,

                    reference_records=reference_records,

                    candidate_records=candidate_records,

                    conditions=conditions,
                )
            )

            if "comparison_quality" not in (
                effort_comparison
            ):
                skipped_pairs.append({
                    **pair_info,

                    "reason": (
                        "insufficient_effort_data"
                    ),

                    "details": effort_comparison.get(
                        "reason"
                    ),
                })

                continue

            aligned_hr = compare_aligned_heart_rate(
                reference_effort=reference_effort,

                candidate_effort=candidate_effort,

                reference_index=reference_index,

                candidate_index=candidate_index,
            )

            effort_comparison = (
                apply_aligned_heart_rate_comparison(
                    effort_comparison=effort_comparison,

                    aligned_comparison=aligned_hr,
                )
            )

            reference_next = find_next_effort(
                current_effort=reference_effort,

                efforts=reference_efforts,
            )

            candidate_next = find_next_effort(
                current_effort=candidate_effort,

                efforts=candidate_efforts,
            )

        except (ValueError, KeyError, TypeError) as error:
            skipped_pairs.append({
                **pair_info,

                "reason": "effort_analysis_error",

                "error_type": type(error).__name__,
            })

            continue

        # Ошибка анализа восстановления
        # не должна уничтожить уже
        # рассчитанное сравнение усилий.
        try:
            recovery_comparison = (
                compare_effort_recovery(
                    reference_effort=reference_effort,

                    candidate_effort=candidate_effort,

                    reference_records=reference_records,

                    candidate_records=candidate_records,

                    reference_next_effort=reference_next,

                    candidate_next_effort=candidate_next,

                    conditions=conditions,

                    reference_ignore_heart_rate=(
                        reference_ignore_hr
                    ),

                    candidate_ignore_heart_rate=(
                        candidate_ignore_hr
                    ),
                )
            )

        except (ValueError, KeyError, TypeError) as error:
            recovery_comparison = {
                "status": "analysis_error",

                "error_type": type(error).__name__,

                "checkpoints": {},

                "fitness_change": None,
            }

        analyzed_pairs.append({
            **pair_info,

            "effort_comparison": (
                effort_comparison
            ),

            "recovery_comparison": (
                recovery_comparison
            ),
        })

        used_reference_ids.add(
            reference_id
        )

        used_candidate_ids.add(
            candidate_id
        )

    summary = summarize_pair_analysis(
        analyzed_pairs
    )

    if not analyzed_pairs:
        status = "insufficient_data"

    elif (
        skipped_pairs

        or summary[
            "heart_rate_comparable_pairs"
        ] < len(analyzed_pairs)

        or any(
            pair["recovery_comparison"]["status"]
            != "ok"

            for pair in analyzed_pairs
        )
    ):
        status = "partial"

    else:
        status = "ok"

    return {
        **result,

        "status": status,

        "matched_pairs_count": len(
            matched_pairs
        ),

        "analyzed_pairs_count": len(
            analyzed_pairs
        ),

        "skipped_pairs_count": len(
            skipped_pairs
        ),

        "pairs": analyzed_pairs,

        "skipped_pairs": skipped_pairs,

        "conditions": conditions,

        "summary": summary,

        "reference_ignore_heart_rate": (
            reference_ignore_hr
        ),

        "candidate_ignore_heart_rate": (
            candidate_ignore_hr
        ),

        "limitations": [
            (
                "Сравнение выполняется "
                "по обнаруженным границам усилий"
            ),
            (
                "Средняя мощность окна "
                "не описывает полностью "
                "динамику нагрузки"
            ),
            (
                "Одинаковая длительность окна "
                "не гарантирует одинаковую "
                "физиологическую нагрузку"
            ),
            (
                "Аэробные сегменты "
                "анализируются отдельно"
            ),
            (
                "Автоматическая оценка "
                "изменения физической формы "
                "не выполняется"
            ),
        ],
    }