from datetime import timedelta
from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


MIN_HEART_RATE_COVERAGE = 0.90

MAX_POWER_DIFFERENCE = 0.05

MIN_COMPARISON_SECONDS = 5

SHORT_EFFORT_SECONDS = 60

BASELINE_WINDOW_SECONDS = 30

PREVIOUS_LOAD_WINDOW_SECONDS = 300

HEART_RATE_EDGE_WINDOW_SECONDS = 5


def calculate_average(values):
    if not values:
        return None

    return round(mean(values), 2)


def calculate_difference(first, second):
    if (
        not is_valid_number(first)
        or not is_valid_number(second)
    ):
        return None

    return round(first - second, 2)


def prepare_effort_records(records):
    """
    Индексирует исходные записи по времени.

    Дублирующиеся временные отметки
    исключаются из анализа.
    """
    if not isinstance(records, list):
        raise ValueError(
            "Записи должны быть списком"
        )

    indexed = {}
    duplicate_timestamps = set()

    for record in records:
        if not isinstance(record, dict):
            continue

        try:
            timestamp = parse_activity_date(
                record["timestamp"]
            )

        except (KeyError, TypeError, ValueError):
            continue

        if timestamp in indexed:
            duplicate_timestamps.add(
                timestamp
            )

        indexed[timestamp] = record

    for timestamp in duplicate_timestamps:
        indexed.pop(timestamp, None)

    return indexed


def extract_record_window(
    indexed_records,
    start,
    duration_seconds,
):
    """
    Извлекает записи из точного
    временного окна.

    Отсутствующие секунды сохраняются
    как None.

    Интерполяция не применяется.
    """
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, int)
        or duration_seconds <= 0
    ):
        raise ValueError(
            "Некорректная длительность окна"
        )

    start = parse_activity_date(start)

    return [
        indexed_records.get(
            start + timedelta(seconds=offset)
        )

        for offset in range(duration_seconds)
    ]


def get_valid_field(
    record,
    field,
):
    if not isinstance(record, dict):
        return None

    value = record.get(field)

    if not is_valid_number(value):
        return None

    if field == "heart_rate":
        return value if value > 0 else None

    return value if value >= 0 else None


def calculate_window_metrics(window):
    """
    Рассчитывает показатели окна.

    Отсутствующие данные не заменяются
    нулевой мощностью или пульсом.
    """
    expected_seconds = len(window)

    if expected_seconds == 0:
        return {
            "status": "insufficient_data",
        }

    powers = []
    heart_rates = []
    cadences = []

    recorded_seconds = 0

    for record in window:
        if record is None:
            continue

        recorded_seconds += 1

        power = get_valid_field(
            record,
            "power",
        )

        heart_rate = get_valid_field(
            record,
            "heart_rate",
        )

        cadence = get_valid_field(
            record,
            "cadence",
        )

        if power is not None:
            powers.append(power)

        if heart_rate is not None:
            heart_rates.append(
                heart_rate
            )

        if cadence is not None:
            cadences.append(cadence)

    power_coverage = (
        len(powers) / expected_seconds
    )

    heart_rate_coverage = (
        len(heart_rates) / expected_seconds
    )

    cadence_coverage = (
        len(cadences) / expected_seconds
    )

    complete_power = (
        len(powers) == expected_seconds
    )

    complete_timing = (
        recorded_seconds == expected_seconds
    )

    status = (
        "ok"
        if complete_power and complete_timing
        else "partial"
    )

    return {
        "status": status,

        "duration_seconds": expected_seconds,

        "recorded_seconds": recorded_seconds,

        "time_coverage_ratio": round(
            recorded_seconds / expected_seconds,
            4,
        ),

        "power_coverage_ratio": round(
            power_coverage,
            4,
        ),

        "heart_rate_coverage_ratio": round(
            heart_rate_coverage,
            4,
        ),

        "cadence_coverage_ratio": round(
            cadence_coverage,
            4,
        ),

        "average_power": calculate_average(
            powers
        ),

        "average_heart_rate": calculate_average(
            heart_rates
        ),

        "max_heart_rate": (
            max(heart_rates)
            if heart_rates
            else None
        ),

        "average_cadence": calculate_average(
            cadences
        ),

        "work_kj": (
            round(sum(powers) / 1000, 2)
            if complete_power
            else None
        ),

        "complete_power": complete_power,

        "complete_timing": complete_timing,
    }


def calculate_edge_heart_rate(
    window,
    edge="start",
    seconds=HEART_RATE_EDGE_WINDOW_SECONDS,
):
    """
    Рассчитывает средний пульс
    первых или последних секунд окна.

    Использование нескольких измерений
    уменьшает влияние одиночных скачков.
    """
    if edge not in {"start", "end"}:
        raise ValueError(
            "Неизвестная граница окна"
        )

    if len(window) < seconds:
        return None

    if edge == "start":
        selected = window[:seconds]

    else:
        selected = window[-seconds:]

    values = [
        get_valid_field(
            record,
            "heart_rate",
        )

        for record in selected
    ]

    if any(
        value is None
        for value in values
    ):
        return None

    return calculate_average(values)


def analyze_effort_baseline(
    indexed_records,
    effort_start,
):
    """
    Анализирует последние 30 секунд
    непосредственно перед усилием.
    """
    effort_start = parse_activity_date(
        effort_start
    )

    baseline_start = (
        effort_start
        - timedelta(
            seconds=BASELINE_WINDOW_SECONDS
        )
    )

    window = extract_record_window(
        indexed_records=indexed_records,
        start=baseline_start,
        duration_seconds=BASELINE_WINDOW_SECONDS,
    )

    metrics = calculate_window_metrics(
        window
    )

    baseline_hr = calculate_edge_heart_rate(
        window,
        edge="end",
    )

    return {
        **metrics,

        "baseline_heart_rate": baseline_hr,

        "window_start": (
            baseline_start.isoformat()
        ),

        "window_end": (
            effort_start
            - timedelta(seconds=1)
        ).isoformat(),
    }


def analyze_previous_effort_load(
    indexed_records,
    effort_start,
):
    """
    Анализирует нагрузку за 5 минут
    непосредственно перед усилием.

    Не предполагает, что весь этот
    период является восстановлением.
    """
    effort_start = parse_activity_date(
        effort_start
    )

    start = (
        effort_start
        - timedelta(
            seconds=PREVIOUS_LOAD_WINDOW_SECONDS
        )
    )

    window = extract_record_window(
        indexed_records=indexed_records,
        start=start,
        duration_seconds=(
            PREVIOUS_LOAD_WINDOW_SECONDS
        ),
    )

    return calculate_window_metrics(
        window
    )


def analyze_effort_window(
    effort,
    indexed_records,
    comparison_seconds,
):
    """
    Анализирует начало усилия
    заданной продолжительности.
    """
    duration = effort.get(
        "duration_seconds"
    )

    if (
        not is_valid_number(duration)
        or comparison_seconds > duration
    ):
        raise ValueError(
            "Окно выходит за границы усилия"
        )

    start = parse_activity_date(
        effort["start"]
    )

    end = parse_activity_date(
        effort["end"]
    )

    expected_duration = (
        end - start
    ).total_seconds() + 1

    if expected_duration != duration:
        raise ValueError(
            "Длительность усилия "
            "не соответствует его границам"
        )

    window = extract_record_window(
        indexed_records=indexed_records,
        start=start,
        duration_seconds=comparison_seconds,
    )

    metrics = calculate_window_metrics(
        window
    )

    baseline = analyze_effort_baseline(
        indexed_records=indexed_records,
        effort_start=start,
    )

    previous_load = (
        analyze_previous_effort_load(
            indexed_records=indexed_records,
            effort_start=start,
        )
    )

    start_hr = calculate_edge_heart_rate(
        window,
        edge="start",
    )

    end_hr = calculate_edge_heart_rate(
        window,
        edge="end",
    )

    return {
        "effort_id": effort.get(
            "effort_id"
        ),

        "full_duration_seconds": duration,

        "comparison_duration_seconds": (
            comparison_seconds
        ),

        "window_metrics": metrics,

        "baseline": baseline,

        "previous_load": previous_load,

        "heart_rate_response": {
            "start_heart_rate": start_hr,

            "end_heart_rate": end_hr,

            "increase_during_window_bpm": (
                calculate_difference(
                    end_hr,
                    start_hr,
                )
            ),

            "increase_from_baseline_bpm": (
                calculate_difference(
                    end_hr,
                    baseline[
                        "baseline_heart_rate"
                    ],
                )
            ),
        },
    }


def assess_effort_comparison_quality(
    reference,
    candidate,
    conditions=None,
):
    """
    Оценивает допустимость сравнения.

    Не определяет изменение физической
    формы спортсмена.
    """
    limitations = []

    first = reference["window_metrics"]
    second = candidate["window_metrics"]

    first_power = first["average_power"]
    second_power = second["average_power"]

    power_difference = None

    if (
        is_valid_number(first_power)
        and is_valid_number(second_power)
        and max(first_power, second_power) > 0
    ):
        power_difference = (
            abs(first_power - second_power)
            / max(first_power, second_power)
        )

    if (
        not first["complete_timing"]
        or not second["complete_timing"]
    ):
        limitations.append(
            "incomplete_timing"
        )

    if (
        not first["complete_power"]
        or not second["complete_power"]
    ):
        limitations.append(
            "incomplete_power_data"
        )

    if (
        power_difference is None
        or power_difference
        > MAX_POWER_DIFFERENCE
    ):
        limitations.append(
            "different_window_power"
        )

    if (
        first["heart_rate_coverage_ratio"]
        < MIN_HEART_RATE_COVERAGE

        or second["heart_rate_coverage_ratio"]
        < MIN_HEART_RATE_COVERAGE
    ):
        limitations.append(
            "insufficient_heart_rate_coverage"
        )

    if reference[
        "comparison_duration_seconds"
    ] < SHORT_EFFORT_SECONDS:
        limitations.append(
            "short_effort_heart_rate_lag"
        )

    first_baseline = reference[
        "baseline"
    ]

    second_baseline = candidate[
        "baseline"
    ]

    baseline_hr_difference = (
        calculate_difference(
            first_baseline[
                "baseline_heart_rate"
            ],
            second_baseline[
                "baseline_heart_rate"
            ],
        )
    )

    if baseline_hr_difference is None:
        limitations.append(
            "missing_baseline_heart_rate"
        )

    elif abs(
        baseline_hr_difference
    ) > 5:
        limitations.append(
            "different_baseline_heart_rate"
        )

    if (
        first_baseline["status"] != "ok"
        or second_baseline["status"] != "ok"
    ):
        limitations.append(
            "incomplete_baseline_data"
        )

    first_previous_load = reference[
        "previous_load"
    ]

    second_previous_load = candidate[
        "previous_load"
    ]

    previous_load_difference = (
        calculate_difference(
            first_previous_load["work_kj"],
            second_previous_load["work_kj"],
        )
    )

    if (
        first_previous_load["status"] != "ok"
        or second_previous_load["status"] != "ok"
    ):
        limitations.append(
            "incomplete_previous_load"
        )

    else:
        first_work = first_previous_load[
            "work_kj"
        ]

        second_work = second_previous_load[
            "work_kj"
        ]

        maximum_work = max(
            first_work,
            second_work,
        )

        if maximum_work > 0:
            relative_difference = (
                abs(first_work - second_work)
                / maximum_work
            )

            if relative_difference > 0.10:
                limitations.append(
                    "different_previous_load"
                )

    if (
        reference["full_duration_seconds"]
        != candidate["full_duration_seconds"]
    ):
        limitations.append(
            "different_full_effort_duration"
        )

    if isinstance(conditions, dict):
        limitations.extend(
            conditions.get(
                "limitations",
                [],
            )
        )

    else:
        limitations.append(
            "conditions_not_assessed"
        )

    limitations = list(
        dict.fromkeys(limitations)
    )

    blocking_limitations = {
        "incomplete_timing",
        "incomplete_power_data",
        "different_window_power",
        "insufficient_heart_rate_coverage",
    }

    heart_rate_comparable = not any(
        limitation in blocking_limitations
        for limitation in limitations
    )

    if not heart_rate_comparable:
        quality = "not_comparable"

    elif limitations:
        quality = "limited"

    else:
        quality = "preliminary"

    return {
        "quality": quality,

        "heart_rate_comparable": (
            heart_rate_comparable
        ),

        "power_difference_percent": (
            round(power_difference * 100, 2)
            if power_difference is not None
            else None
        ),

        "baseline_hr_difference_bpm": (
            baseline_hr_difference
        ),

        "previous_load_difference_kj": (
            previous_load_difference
        ),

        "limitations": limitations,

        "fitness_change": None,
    }


def compare_matched_effort(
    reference_effort,
    candidate_effort,
    reference_records,
    candidate_records,
    conditions=None,
):
    """
    Сравнивает одну пару усилий
    по участкам одинаковой длительности.

    Все разницы рассчитываются как
    последняя тренировка минус предыдущая.
    """
    reference_duration = reference_effort.get(
        "duration_seconds"
    )

    candidate_duration = candidate_effort.get(
        "duration_seconds"
    )

    for duration in (
        reference_duration,
        candidate_duration,
    ):
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration <= 0
        ):
            return {
                "status": "insufficient_data",
                "reason": (
                    "Некорректная длительность усилия"
                ),
            }

    comparison_seconds = min(
        reference_duration,
        candidate_duration,
    )

    if comparison_seconds < MIN_COMPARISON_SECONDS:
        return {
            "status": "insufficient_data",
            "reason": (
                "Слишком короткий участок"
            ),
        }

    reference_index = prepare_effort_records(
        reference_records
    )

    candidate_index = prepare_effort_records(
        candidate_records
    )

    reference = analyze_effort_window(
        effort=reference_effort,
        indexed_records=reference_index,
        comparison_seconds=comparison_seconds,
    )

    candidate = analyze_effort_window(
        effort=candidate_effort,
        indexed_records=candidate_index,
        comparison_seconds=comparison_seconds,
    )

    quality = assess_effort_comparison_quality(
        reference=reference,
        candidate=candidate,
        conditions=conditions,
    )

    first = reference["window_metrics"]
    second = candidate["window_metrics"]

    hr_difference = None

    if quality["heart_rate_comparable"]:
        hr_difference = calculate_difference(
            first["average_heart_rate"],
            second["average_heart_rate"],
        )

    return {
        "status": (
            "ok"
            if quality["heart_rate_comparable"]
            else "partial"
        ),

        "comparison_duration_seconds": (
            comparison_seconds
        ),

        "reference": reference,

        "candidate": candidate,

        "differences": {
            "average_power_watts": (
                calculate_difference(
                    first["average_power"],
                    second["average_power"],
                )
            ),

            "average_heart_rate_bpm": (
                hr_difference
            ),

            "average_cadence_rpm": (
                calculate_difference(
                    first["average_cadence"],
                    second["average_cadence"],
                )
            ),

            "work_kj": calculate_difference(
                first["work_kj"],
                second["work_kj"],
            ),
        },

        "comparison_quality": quality,

        "fitness_change": None,
    }