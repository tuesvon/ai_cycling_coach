from statistics import median
from datetime import timedelta

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


INTERVAL_WEIGHTS = {
    "effort_power": 0.30,
    "effort_duration": 0.25,
    "effort_count": 0.15,
    "between_effort_duration": 0.15,
    "total_work": 0.10,
    "context": 0.05,
}


ENDURANCE_WEIGHTS = {
    "average_power": 0.30,
    "duration": 0.25,
    "zone_distribution": 0.25,
    "power_variability": 0.10,
    "context": 0.10,
}


MAX_EFFORT_POWER_DIFFERENCE = 0.10
MAX_EFFORT_DURATION_DIFFERENCE = 0.40

MIN_SIMILARITY_SCORE = 45
MAX_ENDURANCE_WORK_FRACTION = 0.05


def calculate_numeric_similarity(
    first,
    second,
):
    """
    Рассчитывает относительное сходство
    двух неотрицательных значений.

    Результат находится в диапазоне 0-1.
    """
    if (
        not is_valid_number(first)
        or not is_valid_number(second)
        or first < 0
        or second < 0
    ):
        return None

    if first == 0 and second == 0:
        return 1.0

    return min(first, second) / max(
        first,
        second,
    )


def calculate_relative_difference(
    first,
    second,
):
    """
    Рассчитывает симметричную
    относительную разницу значений.
    """
    similarity = calculate_numeric_similarity(
        first,
        second,
    )

    if similarity is None:
        return None

    return 1.0 - similarity


def get_similarity_level(score):
    if score >= 85:
        return "high"

    if score >= 65:
        return "moderate"

    if score >= 45:
        return "limited"

    return "low"


def calculate_weighted_score(
    components,
    weights,
):
    """
    Рассчитывает взвешенную оценку.

    Недоступные компоненты не считаются
    автоматически ни хорошими, ни плохими.

    Дополнительно возвращается доля
    доступных критериев.
    """
    weighted_sum = 0.0
    available_weight = 0.0

    for name, weight in weights.items():
        value = components.get(name)

        if not is_valid_number(value):
            continue

        if not 0 <= value <= 1:
            continue

        weighted_sum += value * weight
        available_weight += weight

    if available_weight == 0:
        return {
            "score": None,
            "criteria_coverage": 0.0,
        }

    return {
        "score": round(
            weighted_sum
            / available_weight
            * 100,
            2,
        ),
        "criteria_coverage": round(
            available_weight
            / sum(weights.values()),
            4,
        ),
    }


def get_activity_context(signature):
    return signature.get(
        "activity_context",
        {},
    ).get(
        "activity_context",
        "unknown",
    )


def compare_activity_contexts(
    reference,
    candidate,
):
    """
    Сравнивает предполагаемый контекст
    двух активностей.
    """
    first = get_activity_context(
        reference
    )

    second = get_activity_context(
        candidate
    )

    if "unknown" in (first, second):
        return None

    if first == second:
        return 1.0

    if (
        first in {"warmup", "cooldown"}
        or second in {"warmup", "cooldown"}
    ):
        return 0.20

    if "race" in (first, second):
        return 0.30

    if {
        first,
        second,
    } == {
        "structured_workout",
        "free_ride",
    }:
        return 0.70

    return 0.50

def has_repeated_high_intensity_efforts(
    signature,
):
    """
    Проверяет наличие повторяющихся
    высокоинтенсивных усилий.

    Позволяет обнаруживать интервальные
    тренировки с небольшой долей
    интенсивной работы.

    Не определяет физиологическую
    направленность тренировки.
    """
    structure = signature.get(
        "effort_structure",
        {},
    )

    efforts = structure.get(
        "root_efforts",
        [],
    )

    ftp = signature.get(
        "ftp_info",
        {},
    ).get("ftp")

    high_intensity_count = 0
    very_short_intensity_count = 0

    for effort in efforts:
        duration = effort.get(
            "duration_seconds"
        )

        ftp_percent = effort.get(
            "ftp_percent"
        )

        if (
            not is_valid_number(duration)
            or duration <= 0
        ):
            continue

        if not is_valid_number(ftp_percent):
            power = effort.get(
                "average_power"
            )

            if (
                is_valid_number(power)
                and power >= 0
                and is_valid_number(ftp)
                and ftp > 0
            ):
                ftp_percent = (
                    power / ftp * 100
                )

            else:
                continue

        if (
            duration >= 15
            and ftp_percent >= 120
        ):
            high_intensity_count += 1

        if (
            duration >= 5
            and ftp_percent >= 150
        ):
            very_short_intensity_count += 1

    return (
        high_intensity_count >= 2
        or very_short_intensity_count >= 3
    )

def get_comparison_family(signature):
    """
    Определяет семейство нагрузки
    для выбора алгоритма сравнения.

    Учитывает повторяющиеся интенсивные
    усилия независимо от их доли
    в общей продолжительности активности.

    Не определяет физиологическую
    цель тренировки.
    """
    if signature.get("status") != "ok":
        return "unknown"

    load = signature.get(
        "load_profile",
        {},
    )

    structure = signature.get(
        "effort_structure",
        {},
    )

    root_count = structure.get(
        "root_efforts_count",
        0,
    )

    work_fraction = structure.get(
        "work_fraction"
    )

    dominant_zone = load.get(
        "dominant_power_zone"
    )

    context = get_activity_context(
        signature
    )

    # Гонки сохраняют собственный
    # контекст сравнения.
    if context == "race":
        return "race"

    # Повторяющиеся интенсивные усилия
    # имеют приоритет над общей долей
    # аэробной нагрузки.
    if has_repeated_high_intensity_efforts(
        signature
    ):
        return "repeated_efforts"

    # Аэробная тренировка может содержать
    # отдельные непродолжительные усилия.
    if (
        dominant_zone in {
            "recovery",
            "endurance",
        }
        and is_valid_number(work_fraction)
        and work_fraction <= (
            MAX_ENDURANCE_WORK_FRACTION
        )
    ):
        return "endurance"

    if root_count >= 2:
        return "repeated_efforts"

    if root_count == 1:
        return "single_effort"

    return "variable"


def get_root_efforts(signature):
    structure = signature.get(
        "effort_structure",
        {},
    )

    efforts = structure.get(
        "root_efforts",
        [],
    )

    return sorted(
        [
            effort
            for effort in efforts
            if (
                is_valid_number(
                    effort.get("average_power")
                )
                and effort["average_power"] > 0
                and is_valid_number(
                    effort.get("duration_seconds")
                )
                and effort["duration_seconds"] > 0
            )
        ],
        key=lambda effort: parse_activity_date(
            effort["start"]
        ),
    )


def compare_effort_pair(
    reference_effort,
    candidate_effort,
):
    """
    Сравнивает отдельные усилия.

    Пульс и каденс не участвуют
    в выборе сопоставимых усилий.
    """
    power_similarity = (
        calculate_numeric_similarity(
            reference_effort.get(
                "average_power"
            ),
            candidate_effort.get(
                "average_power"
            ),
        )
    )

    duration_similarity = (
        calculate_numeric_similarity(
            reference_effort.get(
                "duration_seconds"
            ),
            candidate_effort.get(
                "duration_seconds"
            ),
        )
    )

    if (
        power_similarity is None
        or duration_similarity is None
    ):
        return None

    power_difference = (
        1.0 - power_similarity
    )

    duration_difference = (
        1.0 - duration_similarity
    )

    can_match = (
        power_difference
        <= MAX_EFFORT_POWER_DIFFERENCE
        and duration_difference
        <= MAX_EFFORT_DURATION_DIFFERENCE
    )

    score = (
        power_similarity * 0.55
        + duration_similarity * 0.45
    )

    return {
        "reference_effort_id": (
            reference_effort["effort_id"]
        ),
        "candidate_effort_id": (
            candidate_effort["effort_id"]
        ),
        "reference_power": (
            reference_effort["average_power"]
        ),
        "candidate_power": (
            candidate_effort["average_power"]
        ),
        "reference_duration_seconds": (
            reference_effort[
                "duration_seconds"
            ]
        ),
        "candidate_duration_seconds": (
            candidate_effort[
                "duration_seconds"
            ]
        ),
        "power_similarity": power_similarity,
        "duration_similarity": duration_similarity,
        "pair_score": round(
            score * 100,
            2,
        ),
        "can_match": can_match,
    }


def match_workout_efforts(
    reference_efforts,
    candidate_efforts,
):
    """
    Находит последовательное
    соответствие рабочих усилий.

    Каждое усилие используется
    не более одного раза.

    Порядок усилий сохраняется.
    """
    first_count = len(
        reference_efforts
    )

    second_count = len(
        candidate_efforts
    )

    scores = [
        [0.0] * (second_count + 1)
        for _ in range(first_count + 1)
    ]

    decisions = [
        [None] * (second_count + 1)
        for _ in range(first_count + 1)
    ]

    pairs = {}

    for i in range(
        1,
        first_count + 1,
    ):
        for j in range(
            1,
            second_count + 1,
        ):
            best_score = scores[i - 1][j]
            decision = "skip_reference"

            if scores[i][j - 1] > best_score:
                best_score = scores[i][j - 1]
                decision = "skip_candidate"

            pair = compare_effort_pair(
                reference_efforts[i - 1],
                candidate_efforts[j - 1],
            )

            if (
                pair is not None
                and pair["can_match"]
            ):
                pairs[(i, j)] = pair

                match_score = (
                    scores[i - 1][j - 1]
                    + pair["pair_score"]
                )

                if match_score >= best_score:
                    best_score = match_score
                    decision = "match"

            scores[i][j] = best_score
            decisions[i][j] = decision

    matched = []

    i = first_count
    j = second_count

    while i > 0 and j > 0:
        decision = decisions[i][j]

        if decision == "match":
            matched.append(
                pairs[(i, j)]
            )

            i -= 1
            j -= 1

        elif decision == "skip_reference":
            i -= 1

        else:
            j -= 1

    matched.reverse()

    return matched


def get_median_between_effort_duration(
    signature,
):
    """
    Возвращает медианную длительность
    промежутков между усилиями.

    Не предполагает, что это обязательно
    физиологическое восстановление.
    """
    gaps = signature.get(
        "effort_structure",
        {},
    ).get(
        "between_effort_gaps",
        [],
    )

    durations = [
        gap["duration_seconds"]
        for gap in gaps
        if (
            gap.get("status") == "ok"
            and is_valid_number(
                gap.get("duration_seconds")
            )
            and gap["duration_seconds"] >= 0
        )
    ]

    if not durations:
        return None

    return median(durations)


def compare_zone_distributions(
    reference_distribution,
    candidate_distribution,
):
    """
    Сравнивает распределение времени
    по зонам мощности.

    Использует доли времени,
    а не абсолютные секунды.
    """
    if (
        not reference_distribution
        or not candidate_distribution
    ):
        return None

    zones = (
        set(reference_distribution)
        | set(candidate_distribution)
    )

    reference_values = {}
    candidate_values = {}

    for zone in zones:
        first = reference_distribution.get(
            zone,
            {},
        ).get("seconds", 0)

        second = candidate_distribution.get(
            zone,
            {},
        ).get("seconds", 0)

        if (
            not is_valid_number(first)
            or not is_valid_number(second)
            or first < 0
            or second < 0
        ):
            return None

        reference_values[zone] = first
        candidate_values[zone] = second

    reference_total = sum(
        reference_values.values()
    )

    candidate_total = sum(
        candidate_values.values()
    )

    if (
        reference_total <= 0
        or candidate_total <= 0
    ):
        return None

    similarity = sum(
        min(
            reference_values[zone]
            / reference_total,

            candidate_values[zone]
            / candidate_total,
        )
        for zone in zones
    )

    return min(
        1.0,
        max(0.0, similarity),
    )


def compare_workout_conditions(
    reference,
    candidate,
):
    """
    Выявляет различия условий.

    Не делает выводов о физиологическом
    состоянии спортсмена.
    """
    first = reference.get(
        "conditions",
        {},
    )

    second = candidate.get(
        "conditions",
        {},
    )

    limitations = []

    first_environment = first.get(
        "environment",
        "unknown",
    )

    second_environment = second.get(
        "environment",
        "unknown",
    )

    environment_comparable = None

    if "unknown" not in (
        first_environment,
        second_environment,
    ):
        environment_comparable = (
            first_environment
            == second_environment
        )

        if not environment_comparable:
            limitations.append(
                "different_environment"
            )

    else:
        limitations.append(
            "unknown_environment"
        )

    first_temperature = first.get(
        "average_temperature"
    )

    second_temperature = second.get(
        "average_temperature"
    )

    temperature_difference = None

    if (
        is_valid_number(first_temperature)
        and is_valid_number(second_temperature)
    ):
        temperature_difference = round(
            abs(
                first_temperature
                - second_temperature
            ),
            2,
        )

        if temperature_difference > 5:
            limitations.append(
                "different_temperature"
            )

    else:
        limitations.append(
            "missing_temperature"
        )

    first_meter = first.get(
        "power_meter"
    )

    second_meter = second.get(
        "power_meter"
    )

    same_power_meter = None

    if first_meter and second_meter:
        same_power_meter = (
            first_meter == second_meter
        )

        if not same_power_meter:
            limitations.append(
                "different_power_meter"
            )

    else:
        limitations.append(
            "unknown_power_meter"
        )

    first_ftp = reference.get(
        "ftp_info",
        {},
    ).get("ftp")

    second_ftp = candidate.get(
        "ftp_info",
        {},
    ).get("ftp")

    ftp_difference = (
        calculate_relative_difference(
            first_ftp,
            second_ftp,
        )
    )

    if (
        ftp_difference is not None
        and ftp_difference > 0.05
    ):
        limitations.append(
            "different_ftp"
        )

    if (
        reference.get(
            "ftp_info", {}
        ).get("confidence") == "estimated"

        or candidate.get(
            "ftp_info", {}
        ).get("confidence") == "estimated"
    ):
        limitations.append(
            "estimated_historical_ftp"
        )

    return {
        "environment_comparable": (
            environment_comparable
        ),
        "reference_environment": (
            first_environment
        ),
        "candidate_environment": (
            second_environment
        ),
        "temperature_difference_celsius": (
            temperature_difference
        ),
        "same_power_meter": (
            same_power_meter
        ),
        "ftp_difference_percent": (
            round(ftp_difference * 100, 2)
            if ftp_difference is not None
            else None
        ),
        "limitations": limitations,
    }


def compare_interval_signatures(
    reference,
    candidate,
):
    """
    Сравнивает структуру обнаруженных
    рабочих усилий.
    """
    reference_efforts = get_root_efforts(
        reference
    )

    candidate_efforts = get_root_efforts(
        candidate
    )

    matched = match_workout_efforts(
        reference_efforts,
        candidate_efforts,
    )

    reference_count = len(
        reference_efforts
    )

    candidate_count = len(
        candidate_efforts
    )

    matched_count = len(matched)

    power_similarity = 0.0
    duration_similarity = 0.0

    if matched:
        power_similarity = sum(
            pair["power_similarity"]
            for pair in matched
        ) / matched_count

        duration_similarity = sum(
            pair["duration_similarity"]
            for pair in matched
        ) / matched_count

    reference_structure = reference[
        "effort_structure"
    ]

    candidate_structure = candidate[
        "effort_structure"
    ]

    reference_coverage = (
        matched_count / reference_count
        if reference_count
        else 0.0
    )

    candidate_coverage = (
        matched_count / candidate_count
        if candidate_count
        else 0.0
    )

    components = {
        "effort_power": power_similarity,

        "effort_duration": (
            duration_similarity
        ),

        "effort_count": (
            calculate_numeric_similarity(
                reference_count,
                candidate_count,
            )
        ),

        "between_effort_duration": (
            calculate_numeric_similarity(
                get_median_between_effort_duration(
                    reference
                ),
                get_median_between_effort_duration(
                    candidate
                ),
            )
        ),

        "total_work": (
            calculate_numeric_similarity(
                reference_structure[
                    "unique_work_seconds"
                ],
                candidate_structure[
                    "unique_work_seconds"
                ],
            )
        ),

        "context": compare_activity_contexts(
            reference,
            candidate,
        ),
    }

    weighted = calculate_weighted_score(
        components,
        INTERVAL_WEIGHTS,
    )

    raw_score = weighted["score"]

    # Не позволяем одному совпавшему
    # усилию сделать две существенно
    # разные тренировки похожими.
    match_coverage = min(
        reference_coverage,
        candidate_coverage,
    )

    if raw_score is None:
        score = 0.0

    else:
        score = round(
            raw_score
            * (0.5 + 0.5 * match_coverage),
            2,
        )

    limitations = []

    if not matched:
        score = min(score, 44.0)

        limitations.append(
            "no_matching_efforts"
        )

    if match_coverage < 0.80:
        limitations.append(
            "limited_effort_match_coverage"
        )

    if (
        reference_structure.get(
            "nested_efforts_count", 0
        ) > 0

        or candidate_structure.get(
            "nested_efforts_count", 0
        ) > 0
    ):
        limitations.append(
            "nested_structure_not_fully_compared"
        )

    if (
        reference_structure.get(
            "partially_overlapping_efforts_count",
            0,
        ) > 0

        or candidate_structure.get(
            "partially_overlapping_efforts_count",
            0,
        ) > 0
    ):
        limitations.append(
            "partially_overlapping_efforts"
        )

    return {
        "comparison_type": (
            "effort_structure"
        ),
        "score": score,
        "raw_score": raw_score,
        "criteria_coverage": weighted[
            "criteria_coverage"
        ],
        "components": components,
        "matched_efforts_count": matched_count,
        "matched_efforts": matched,
        "reference_efforts_count": reference_count,
        "candidate_efforts_count": candidate_count,
        "reference_match_coverage": round(
            reference_coverage,
            4,
        ),
        "candidate_match_coverage": round(
            candidate_coverage,
            4,
        ),
        "limitations": limitations,
    }


def compare_endurance_signatures(
    reference,
    candidate,
):
    """
    Сравнивает общий профиль
    аэробной нагрузки.
    """
    first = reference["load_profile"]
    second = candidate["load_profile"]

    components = {
        "average_power": (
            calculate_numeric_similarity(
                first.get("average_power"),
                second.get("average_power"),
            )
        ),

        "duration": (
            calculate_numeric_similarity(
                first.get("duration_seconds"),
                second.get("duration_seconds"),
            )
        ),

        "zone_distribution": (
            compare_zone_distributions(
                first.get(
                    "power_zone_distribution",
                    {},
                ),
                second.get(
                    "power_zone_distribution",
                    {},
                ),
            )
        ),

        "power_variability": (
            calculate_numeric_similarity(
                first.get("power_cv_percent"),
                second.get("power_cv_percent"),
            )
        ),

        "context": compare_activity_contexts(
            reference,
            candidate,
        ),
    }

    weighted = calculate_weighted_score(
        components,
        ENDURANCE_WEIGHTS,
    )

    return {
        "comparison_type": "endurance",
        "score": (
            weighted["score"]
            if weighted["score"] is not None
            else 0.0
        ),
        "criteria_coverage": weighted[
            "criteria_coverage"
        ],
        "components": components,
        "matched_efforts_count": 0,
        "matched_efforts": [],
        "limitations": [
            "aerobic_segments_not_yet_matched"
        ],
    }


def compare_workout_signatures(
    reference,
    candidate,
):
    """
    Оценивает сходство двух профилей.

    Не делает вывод о росте или снижении
    физической формы.
    """
    if (
        reference.get("status") != "ok"
        or candidate.get("status") != "ok"
    ):
        return {
            "status": "insufficient_data",
            "score": None,
            "similarity_level": "unknown",
            "comparison_scope": "none",
        }

    reference_family = get_comparison_family(
        reference
    )

    candidate_family = get_comparison_family(
        candidate
    )

    conditions = compare_workout_conditions(
        reference,
        candidate,
    )

    reference_context = get_activity_context(
        reference
    )

    candidate_context = get_activity_context(
        candidate
    )

    if (
        reference_family == "endurance"
        and candidate_family == "endurance"
    ):
        comparison = (
            compare_endurance_signatures(
                reference,
                candidate,
            )
        )

    elif (
        get_root_efforts(reference)
        and get_root_efforts(candidate)
    ):
        comparison = (
            compare_interval_signatures(
                reference,
                candidate,
            )
        )

    else:
        return {
            "status": "not_comparable",
            "score": 0.0,
            "similarity_level": "low",
            "comparison_scope": "none",
            "reference_family": (
                reference_family
            ),
            "candidate_family": (
                candidate_family
            ),
            "conditions": conditions,
            "limitations": [
                "different_load_structure"
            ],
        }

    score = comparison["score"]

    limitations = list(
        comparison["limitations"]
    )

    same_context = (
        reference_context
        == candidate_context
        and reference_context != "unknown"
    )

    if not same_context:
        limitations.append(
            "different_or_unknown_context"
        )

    if reference_family != candidate_family:
        limitations.append(
            "different_comparison_family"
        )

    if score < MIN_SIMILARITY_SCORE:
        scope = "none"

    elif (
        comparison["comparison_type"]
        == "endurance"
    ):
        scope = (
            "aerobic_segment_candidates"
        )

    else:
        scope = "matched_efforts_only"

    # Пока ни один результат не считается
    # разрешением на автоматический вывод
    # о физиологическом прогрессе.
    full_workout_candidate = (
        score >= 85
        and same_context
        and reference_family == candidate_family
        and reference_context
        not in {
            "race",
            "warmup",
            "cooldown",
        }
        and comparison["criteria_coverage"]
        >= 0.80
        and not conditions["limitations"]
        and not (
            comparison["comparison_type"]
            == "effort_structure"
            and (
                comparison[
                    "reference_match_coverage"
                ] < 0.80
                or comparison[
                    "candidate_match_coverage"
                ] < 0.80
                or limitations
            )
        )
    )

    return {
        **comparison,
        "status": "ok",

        "reference_activity_id": reference.get(
            "activity_id"
        ),

        "candidate_activity_id": candidate.get(
            "activity_id"
        ),

        "candidate_activity_name": candidate.get(
            "activity_name"
        ),

        "candidate_start_date": candidate.get(
            "start_date"
        ),

        "reference_family": reference_family,

        "candidate_family": candidate_family,

        "reference_context": reference_context,

        "candidate_context": candidate_context,

        "similarity_level": (
            get_similarity_level(score)
        ),

        "comparison_scope": scope,

        "full_workout_comparison_candidate": (
            full_workout_candidate
        ),

        "conditions": conditions,

        "limitations": list(
            dict.fromkeys(
                limitations
                + conditions["limitations"]
            )
        ),
    }


def find_similar_workout_signatures(
    reference,
    candidates,
    days=30,
    min_score=MIN_SIMILARITY_SCORE,
):
    """
    Ищет похожие выполненные тренировки
    за указанный период до референсной
    тренировки.

    Будущие активности исключаются.
    """
    if (
        isinstance(days, bool)
        or not isinstance(days, int)
        or days <= 0
    ):
        raise ValueError(
            "Период должен быть "
            "положительным целым числом"
        )

    if (
        not is_valid_number(min_score)
        or not 0 <= min_score <= 100
    ):
        raise ValueError(
            "Некорректный минимальный балл"
        )

    if not isinstance(candidates, list):
        raise ValueError(
            "Кандидаты должны быть списком"
        )

    if reference.get("status") != "ok":
        return {
            "status": "insufficient_data",
            "similar_workouts": [],
            "evaluations": [],
            "skipped_workouts": [],
        }

    try:
        reference_date = parse_activity_date(
            reference["start_date"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return {
            "status": "insufficient_data",
            "reason": (
                "Некорректная дата "
                "референсной тренировки"
            ),
            "similar_workouts": [],
            "evaluations": [],
            "skipped_workouts": [],
        }

    cutoff_date = (
        reference_date
        - timedelta(days=days)
    )

    reference_id = reference.get(
        "activity_id"
    )

    evaluations = []
    similar_workouts = []
    skipped_workouts = []

    processed_ids = set()

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        candidate_id = candidate.get(
            "activity_id"
        )

        if candidate_id is None:
            skipped_workouts.append({
                "activity_id": None,
                "reason": "missing_activity_id",
            })

            continue

        if candidate_id == reference_id:
            continue

        if candidate_id in processed_ids:
            continue

        processed_ids.add(
            candidate_id
        )

        try:
            candidate_date = (
                parse_activity_date(
                    candidate["start_date"]
                )
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            skipped_workouts.append({
                "activity_id": candidate_id,
                "reason": "invalid_date",
            })

            continue

        if not (
            cutoff_date
            <= candidate_date
            < reference_date
        ):
            skipped_workouts.append({
                "activity_id": candidate_id,
                "reason": "outside_period",
            })

            continue

        if candidate.get("status") != "ok":
            skipped_workouts.append({
                "activity_id": candidate_id,
                "reason": "insufficient_data",
            })

            continue

        comparison = compare_workout_signatures(
            reference,
            candidate,
        )

        evaluation = {
            **comparison,
            "candidate_activity_id": (
                candidate_id
            ),
            "candidate_activity_name": (
                candidate.get("activity_name")
            ),
            "candidate_start_date": (
                candidate.get("start_date")
            ),
        }

        evaluations.append(
            evaluation
        )

        if (
            evaluation["status"] == "ok"
            and evaluation["score"] >= min_score
            and evaluation[
                "comparison_scope"
            ] != "none"
        ):
            similar_workouts.append(
                evaluation
            )

    def sort_key(item):
        score = item.get("score")

        return (
            score
            if is_valid_number(score)
            else -1.0,

            parse_activity_date(
                item["candidate_start_date"]
            ),
        )

    evaluations.sort(
        key=sort_key,
        reverse=True,
    )

    similar_workouts.sort(
        key=sort_key,
        reverse=True,
    )

    return {
        "status": (
            "ok"
            if similar_workouts
            else "no_similar_workouts"
        ),

        "reference_activity_id": reference_id,

        "comparison_period_days": days,

        "minimum_similarity_score": min_score,

        "evaluated_workouts_count": len(
            evaluations
        ),

        "similar_workouts_count": len(
            similar_workouts
        ),

        "skipped_workouts_count": len(
            skipped_workouts
        ),

        "similar_workouts": similar_workouts,

        "evaluations": evaluations,

        "skipped_workouts": skipped_workouts,
    }