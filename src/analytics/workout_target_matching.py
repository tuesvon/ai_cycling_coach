from collections import Counter
from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    analyze_effort_window,
)

from src.analytics.workout_target_structure import (
    analyze_workout_target_structure,
)


WORK_INTENSITY_CATEGORIES = {
    "threshold",
    "vo2max_power",
    "anaerobic_power",
    "very_high_intensity",
}

MIN_TARGET_EFFORT_SECONDS = 5

MIN_STRONG_OVERLAP_RATIO = 0.80

MIN_PARTIAL_OVERLAP_RATIO = 0.50

MAX_MATCH_POWER_DIFFERENCE_RATIO = 0.20

MIN_POWER_COVERAGE_RATIO = 0.90

MIN_WITHIN_TARGET_PERCENT = 80

MAX_EXECUTION_DIFFERENCE_PERCENT = 10


def get_target_work_blocks(
    target_structure,
):
    """
    Возвращает постоянные целевые блоки
    высокой интенсивности.

    Ramp и аэробные блоки пока
    анализируются отдельно.
    """
    if target_structure.get("status") != "ok":
        return []

    return sorted(
        [
            block

            for block in target_structure.get(
                "structure_blocks", []
            )

            if (
                block["block_type"] == "steady"

                and block["intensity_category"]
                in WORK_INTENSITY_CATEGORIES

                and block["duration_seconds"]
                >= MIN_TARGET_EFFORT_SECONDS
            )
        ],

        key=lambda block: parse_activity_date(
            block["start"]
        ),
    )


def get_actual_root_efforts(signature):
    """
    Возвращает фактически обнаруженные
    основные усилия.
    """
    if not isinstance(signature, dict):
        return []

    if signature.get("status") != "ok":
        return []

    efforts = signature.get(
        "effort_structure", {}
    ).get(
        "root_efforts", []
    )

    return sorted(
        efforts,

        key=lambda effort: parse_activity_date(
            effort["start"]
        ),
    )


def calculate_temporal_overlap(
    target_block,
    actual_effort,
):
    """
    Рассчитывает пересечение
    целевого и фактического окна.
    """
    target_start = parse_activity_date(
        target_block["start"]
    )

    target_end = parse_activity_date(
        target_block["end"]
    )

    actual_start = parse_activity_date(
        actual_effort["start"]
    )

    actual_end = parse_activity_date(
        actual_effort["end"]
    )

    overlap_start = max(
        target_start,
        actual_start,
    )

    overlap_end = min(
        target_end,
        actual_end,
    )

    overlap_seconds = 0

    if overlap_end >= overlap_start:
        overlap_seconds = int(
            (
                overlap_end
                - overlap_start
            ).total_seconds()
        ) + 1

    target_duration = target_block[
        "duration_seconds"
    ]

    actual_duration = actual_effort[
        "duration_seconds"
    ]

    target_coverage = (
        overlap_seconds / target_duration
    )

    actual_coverage = (
        overlap_seconds / actual_duration
    )

    union_seconds = (
        target_duration
        + actual_duration
        - overlap_seconds
    )

    intersection_over_union = (
        overlap_seconds / union_seconds
    )

    return {
        "overlap_seconds": overlap_seconds,

        "target_coverage_ratio": round(
            target_coverage,
            4,
        ),

        "actual_coverage_ratio": round(
            actual_coverage,
            4,
        ),

        "intersection_over_union": round(
            intersection_over_union,
            4,
        ),

        "start_difference_seconds": (
            actual_start - target_start
        ).total_seconds(),

        "end_difference_seconds": (
            actual_end - target_end
        ).total_seconds(),
    }


def evaluate_target_actual_match(
    target_block,
    actual_effort,
):
    """
    Оценивает возможность сопоставления
    целевого и фактического усилия.
    """
    temporal = calculate_temporal_overlap(
        target_block,
        actual_effort,
    )

    target_power = target_block[
        "average_target_power"
    ]

    actual_power = actual_effort.get(
        "average_power"
    )

    power_difference_ratio = None

    power_similarity = None

    if (
        is_valid_number(target_power)

        and target_power > 0

        and is_valid_number(actual_power)

        and actual_power > 0
    ):
        power_difference_ratio = (
            abs(actual_power - target_power)
            / target_power
        )

        power_similarity = (
            min(target_power, actual_power)
            / max(target_power, actual_power)
        )

    target_coverage = temporal[
        "target_coverage_ratio"
    ]

    actual_coverage = temporal[
        "actual_coverage_ratio"
    ]

    limitations = []

    can_match = True

    if (
        target_coverage
        < MIN_PARTIAL_OVERLAP_RATIO

        or actual_coverage
        < MIN_PARTIAL_OVERLAP_RATIO
    ):
        can_match = False

        limitations.append(
            "insufficient_temporal_overlap"
        )

    if power_difference_ratio is None:
        can_match = False

        limitations.append(
            "missing_power"
        )

    elif (
        power_difference_ratio
        > MAX_MATCH_POWER_DIFFERENCE_RATIO
    ):
        can_match = False

        limitations.append(
            "different_power"
        )

    score = 0.0

    if can_match:
        score = (
            temporal[
                "intersection_over_union"
            ] * 0.70

            + power_similarity * 0.30
        ) * 100

    if not can_match:
        quality = "not_matched"

    elif (
        target_coverage
        >= MIN_STRONG_OVERLAP_RATIO

        and actual_coverage
        >= MIN_STRONG_OVERLAP_RATIO
    ):
        quality = "strong"

    else:
        quality = "partial"

        limitations.append(
            "partial_temporal_overlap"
        )

    return {
        "target_block_id": target_block[
            "block_id"
        ],

        "actual_effort_id": actual_effort[
            "effort_id"
        ],

        "target_power": target_power,

        "actual_effort_average_power": (
            actual_power
        ),

        "target_duration_seconds": target_block[
            "duration_seconds"
        ],

        "actual_duration_seconds": actual_effort[
            "duration_seconds"
        ],

        **temporal,

        "power_difference_percent": (
            round(
                power_difference_ratio * 100,
                2,
            )

            if power_difference_ratio is not None

            else None
        ),

        "score": round(score, 2),

        "can_match": can_match,

        "match_quality": quality,

        "limitations": limitations,
    }


def match_target_and_actual_efforts(
    target_blocks,
    actual_efforts,
):
    """
    Выполняет уникальное сопоставление
    с сохранением хронологического порядка.

    Максимизирует суммарную оценку
    совместимости.
    """
    target_count = len(
        target_blocks
    )

    actual_count = len(
        actual_efforts
    )

    evaluations = [
        [
            evaluate_target_actual_match(
                target_block,
                actual_effort,
            )

            for actual_effort in actual_efforts
        ]

        for target_block in target_blocks
    ]

    dp = [
        [0.0] * (actual_count + 1)

        for _ in range(target_count + 1)
    ]

    decisions = [
        [None] * (actual_count + 1)

        for _ in range(target_count + 1)
    ]

    for i in range(1, target_count + 1):
        for j in range(1, actual_count + 1):

            best_score = dp[i - 1][j]

            decision = "skip_target"

            if dp[i][j - 1] > best_score:
                best_score = dp[i][j - 1]

                decision = "skip_actual"

            evaluation = evaluations[
                i - 1
            ][
                j - 1
            ]

            if evaluation["can_match"]:
                match_score = (
                    dp[i - 1][j - 1]

                    + evaluation["score"]
                )

                if match_score >= best_score:
                    best_score = match_score

                    decision = "match"

            dp[i][j] = best_score

            decisions[i][j] = decision

    matches = []

    i = target_count

    j = actual_count

    while i > 0 and j > 0:
        decision = decisions[i][j]

        if decision == "match":
            matches.append(
                evaluations[i - 1][j - 1]
            )

            i -= 1
            j -= 1

        elif decision == "skip_target":
            i -= 1

        else:
            j -= 1

    matches.reverse()

    matched_target_ids = {
        match["target_block_id"]

        for match in matches
    }

    matched_actual_ids = {
        match["actual_effort_id"]

        for match in matches
    }

    return {
        "matches": matches,

        "unmatched_target_block_ids": [
            block["block_id"]

            for block in target_blocks

            if block["block_id"]
            not in matched_target_ids
        ],

        "unmatched_actual_effort_ids": [
            effort["effort_id"]

            for effort in actual_efforts

            if effort["effort_id"]
            not in matched_actual_ids
        ],
    }


def assess_target_effort_execution(
    execution,
):
    """
    Описывает качество выполнения
    целевого блока.

    Не использует наличие совпадения
    с универсальным детектором.
    """
    coverage = execution.get(
        "comparison_coverage_ratio",
        0,
    )

    ratio = execution.get(
        "execution_ratio_percent"
    )

    within_target = execution.get(
        "within_target_percent"
    )

    if (
        coverage < MIN_POWER_COVERAGE_RATIO

        or not is_valid_number(ratio)

        or not is_valid_number(within_target)
    ):
        return {
            "status": "insufficient_data",

            "limitations": [
                "insufficient_power_coverage"
            ],
        }

    limitations = []

    if coverage < 1:
        limitations.append(
            "partial_power_coverage"
        )

    if ratio < (
        100 - MAX_EXECUTION_DIFFERENCE_PERCENT
    ):
        status = "below_target"

    elif ratio > (
        100 + MAX_EXECUTION_DIFFERENCE_PERCENT
    ):
        status = "above_target"

    elif within_target < MIN_WITHIN_TARGET_PERCENT:
        status = "variable_execution"

    else:
        status = "close_to_target"

    return {
        "status": status,

        "limitations": limitations,
    }


def analyze_target_effort_window(
    target_block,
    indexed_records,
    match=None,
):
    """
    Анализирует фактическую нагрузку
    в полном целевом окне.

    Не подменяет записанную мощность
    целевой мощностью.
    """
    target_id = target_block[
        "block_id"
    ]

    duration = target_block[
        "duration_seconds"
    ]

    effort = {
        "effort_id": target_id,

        "start": target_block["start"],

        "end": target_block["end"],

        "duration_seconds": duration,

        "average_power": target_block[
            "execution"
        ].get(
            "average_actual_power"
        ),
    }

    window_analysis = analyze_effort_window(
        effort=effort,

        indexed_records=indexed_records,

        comparison_seconds=duration,
    )

    execution = target_block[
        "execution"
    ]

    execution_quality = (
        assess_target_effort_execution(
            execution
        )
    )

    return {
        "target_block_id": target_id,

        "start": target_block["start"],

        "end": target_block["end"],

        "target_power": target_block[
            "average_target_power"
        ],

        "target_duration_seconds": duration,

        "intensity_category": target_block[
            "intensity_category"
        ],

        "execution": execution,

        "execution_quality": execution_quality,

        "physiological_window": (
            window_analysis
        ),

        "actual_effort_match": match,

        "matching_status": (
            "matched"
            if match is not None
            else "no_detected_match"
        ),

        "fitness_change": None,
    }


def summarize_target_efforts(
    efforts,
):
    """
    Обобщает выполнение всех
    целевых рабочих усилий.

    Не усредняет пульс интервалов
    различной интенсивности.
    """
    execution_counts = Counter()

    matching_counts = Counter()

    strong_matches = 0

    start_differences = []

    end_differences = []

    for effort in efforts:
        execution_counts[
            effort["execution_quality"]["status"]
        ] += 1

        matching_counts[
            effort["matching_status"]
        ] += 1

        match = effort.get(
            "actual_effort_match"
        )

        if match is None:
            continue

        if match["match_quality"] == "strong":
            strong_matches += 1

        start_differences.append(
            match["start_difference_seconds"]
        )

        end_differences.append(
            match["end_difference_seconds"]
        )

    return {
        "target_efforts_count": len(
            efforts
        ),

        "matched_efforts_count": (
            matching_counts["matched"]
        ),

        "unmatched_efforts_count": (
            matching_counts["no_detected_match"]
        ),

        "strong_matches_count": (
            strong_matches
        ),

        "execution_quality_counts": dict(
            execution_counts
        ),

        "matching_status_counts": dict(
            matching_counts
        ),

        "average_start_difference_seconds": (
            round(mean(start_differences), 2)

            if start_differences

            else None
        ),

        "average_end_difference_seconds": (
            round(mean(end_differences), 2)

            if end_differences

            else None
        ),
    }


def analyze_target_actual_workout(
    records,
    signature=None,
    ftp=None,
    ignore_power=False,
    ignore_heart_rate=False,
):
    """
    Сопоставляет записанное задание
    с фактически выполненной нагрузкой.

    Целевые усилия анализируются даже
    при отсутствии фактического профиля.
    """
    if not isinstance(
        ignore_power, bool
    ):
        raise ValueError(
            "ignore_power должен быть bool"
        )

    if not isinstance(
        ignore_heart_rate, bool
    ):
        raise ValueError(
            "ignore_heart_rate должен быть bool"
        )

    conditions = {}

    if isinstance(signature, dict):
        conditions = signature.get(
            "conditions", {}
        ) or {}

    ignore_power = (
        ignore_power

        or conditions.get(
            "ignore_power"
        ) is True
    )

    ignore_heart_rate = (
        ignore_heart_rate

        or conditions.get(
            "ignore_heart_rate"
        ) is True
    )

    target_structure = (
        analyze_workout_target_structure(
            records=records,

            ftp=ftp,

            ignore_power=ignore_power,
        )
    )

    result = {
        "status": target_structure["status"],

        "target_structure": target_structure,

        "target_efforts": [],

        "actual_structure_status": (
            signature.get("status")

            if isinstance(signature, dict)

            else "unavailable"
        ),

        "matching": None,

        "summary": summarize_target_efforts(
            []
        ),

        "ignore_power": ignore_power,

        "ignore_heart_rate": ignore_heart_rate,

        "fitness_change": None,
    }

    if target_structure["status"] != "ok":
        return result

    if ftp is None:
        return {
            **result,

            "status": "ftp_unavailable",
        }

    target_blocks = get_target_work_blocks(
        target_structure
    )

    actual_efforts = get_actual_root_efforts(
        signature
    )

    matching = match_target_and_actual_efforts(
        target_blocks=target_blocks,

        actual_efforts=actual_efforts,
    )

    result["matching"] = matching

    if not target_blocks:
        return {
            **result,

            "status": "no_work_blocks",
        }

    matches_by_target = {
        match["target_block_id"]: match

        for match in matching["matches"]
    }

    prepared = []

    for record in records:
        if not isinstance(record, dict):
            continue

        copied = dict(record)

        if ignore_heart_rate:
            copied.pop(
                "heart_rate",
                None,
            )

        prepared.append(copied)

    indexed = prepare_effort_records(
        prepared
    )

    analyzed_efforts = []

    for block in target_blocks:
        match = matches_by_target.get(
            block["block_id"]
        )

        analyzed = analyze_target_effort_window(
            target_block=block,

            indexed_records=indexed,

            match=match,
        )

        analyzed_efforts.append(
            analyzed
        )

    summary = summarize_target_efforts(
        analyzed_efforts
    )

    status = "ok"

    if any(
        effort["execution_quality"]["status"]
        == "insufficient_data"

        for effort in analyzed_efforts
    ):
        status = "partial"

    return {
        **result,

        "status": status,

        "target_efforts": analyzed_efforts,

        "summary": summary,

        "limitations": [
            (
                "Отсутствие обнаруженного совпадения "
                "не означает невыполнение задания"
            ),
            (
                "Смещение границ может зависеть "
                "от станка, спортсмена и детектора"
            ),
            (
                "Качество выполнения рассчитывается "
                "по полному целевому окну"
            ),
            (
                "Сопоставление основных усилий "
                "выполняется один к одному"
            ),
            (
                "Частично пересекающиеся и вложенные "
                "усилия требуют дополнительного анализа"
            ),
            (
                "Физиологические метрики "
                "не являются оценкой изменения формы"
            ),
        ],
    }