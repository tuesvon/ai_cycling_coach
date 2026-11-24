from datetime import timedelta

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    extract_record_window,
    calculate_window_metrics,
    calculate_edge_heart_rate,
    calculate_difference,
    get_valid_field,
)


RECOVERY_CHECKPOINTS = (30, 60, 120)

MAX_RECOVERY_SECONDS = 120

PEAK_SEARCH_SECONDS = 30

MIN_HEART_RATE_COVERAGE = 0.90

MAX_RECOVERY_POWER_DIFFERENCE_WATTS = 15

MAX_END_HEART_RATE_DIFFERENCE = 5

MAX_EFFORT_DURATION_DIFFERENCE = 0.10

MAX_EFFORT_POWER_DIFFERENCE = 0.05


def get_available_recovery_seconds(
    effort,
    indexed_records,
    next_effort=None,
    max_seconds=MAX_RECOVERY_SECONDS,
):
    """
    Определяет доступную продолжительность
    восстановления после усилия.

    Не допускает включения следующего
    обнаруженного рабочего усилия.
    """
    if (
        isinstance(max_seconds, bool)
        or not isinstance(max_seconds, int)
        or max_seconds <= 0
    ):
        raise ValueError(
            "Некорректная продолжительность "
            "восстановления"
        )

    effort_end = parse_activity_date(
        effort["end"]
    )

    if not indexed_records:
        return 0

    last_timestamp = max(
        indexed_records
    )

    available_seconds = max(
        0,
        int(
            (
                last_timestamp - effort_end
            ).total_seconds()
        ),
    )

    available_seconds = min(
        available_seconds,
        max_seconds,
    )

    if next_effort is not None:
        next_start = parse_activity_date(
            next_effort["start"]
        )

        gap_seconds = max(
            0,
            int(
                (
                    next_start - effort_end
                ).total_seconds()
            ) - 1,
        )

        available_seconds = min(
            available_seconds,
            gap_seconds,
        )

    return available_seconds


def find_recovery_heart_rate_peak(
    recovery_window,
    search_seconds=PEAK_SEARCH_SECONDS,
):
    """
    Ищет наблюдаемый пик пульса
    в начале восстановления.

    Не утверждает, что найден
    абсолютный физиологический пик.
    """
    selected = recovery_window[
        :search_seconds
    ]

    if not selected:
        return {
            "heart_rate": None,
            "seconds_after_effort": None,
            "coverage_ratio": 0.0,
            "search_duration_seconds": 0,
        }

    valid_values = []

    for index, record in enumerate(
        selected,
        start=1,
    ):
        heart_rate = get_valid_field(
            record,
            "heart_rate",
        )

        if heart_rate is not None:
            valid_values.append({
                "heart_rate": heart_rate,
                "seconds_after_effort": index,
            })

    coverage = (
        len(valid_values)
        / len(selected)
    )

    if (
        not valid_values
        or coverage < MIN_HEART_RATE_COVERAGE
    ):
        return {
            "heart_rate": None,
            "seconds_after_effort": None,
            "coverage_ratio": round(
                coverage,
                4,
            ),
            "search_duration_seconds": len(
                selected
            ),
        }

    peak = max(
        valid_values,
        key=lambda item: item[
            "heart_rate"
        ],
    )

    return {
        **peak,

        "coverage_ratio": round(
            coverage,
            4,
        ),

        "search_duration_seconds": len(
            selected
        ),
    }


def analyze_recovery_checkpoint(
    recovery_window,
    checkpoint_seconds,
    end_heart_rate,
    recovery_peak,
):
    """
    Анализирует восстановление
    через заданное количество секунд.

    Пульс в контрольной точке —
    среднее последних пяти секунд
    соответствующего окна.
    """
    if len(recovery_window) < checkpoint_seconds:
        return {
            "status": "insufficient_data",

            "checkpoint_seconds": (
                checkpoint_seconds
            ),

            "reason": (
                "Недостаточная продолжительность "
                "доступного восстановления"
            ),

            "heart_rate": None,

            "heart_rate_drop_from_end": None,

            "heart_rate_drop_from_peak": None,

            "metrics": None,
        }

    selected = recovery_window[
        :checkpoint_seconds
    ]

    metrics = calculate_window_metrics(
        selected
    )

    checkpoint_hr = calculate_edge_heart_rate(
        selected,
        edge="end",
    )

    limitations = []

    if not metrics["complete_timing"]:
        limitations.append(
            "incomplete_recovery_timing"
        )

    if not metrics["complete_power"]:
        limitations.append(
            "incomplete_recovery_power"
        )

    if (
        metrics["heart_rate_coverage_ratio"]
        < MIN_HEART_RATE_COVERAGE
    ):
        limitations.append(
            "insufficient_recovery_heart_rate"
        )

    if checkpoint_hr is None:
        limitations.append(
            "missing_checkpoint_heart_rate"
        )

    if end_heart_rate is None:
        limitations.append(
            "missing_end_heart_rate"
        )

    peak_hr = recovery_peak.get(
        "heart_rate"
    )

    peak_offset = recovery_peak.get(
        "seconds_after_effort"
    )

    drop_from_peak = None

    # Пик должен находиться до
    # контрольного окна пульса.
    if (
        peak_hr is not None
        and peak_offset is not None
        and peak_offset <= checkpoint_seconds - 5
        and not limitations
    ):
        drop_from_peak = calculate_difference(
            peak_hr,
            checkpoint_hr,
        )

    drop_from_end = None

    if not limitations:
        drop_from_end = calculate_difference(
            end_heart_rate,
            checkpoint_hr,
        )

    return {
        "status": (
            "ok"
            if not limitations
            else "partial"
        ),

        "checkpoint_seconds": (
            checkpoint_seconds
        ),

        "heart_rate": checkpoint_hr,

        "heart_rate_drop_from_end": (
            drop_from_end
        ),

        "heart_rate_drop_from_peak": (
            drop_from_peak
        ),

        "metrics": metrics,

        "limitations": limitations,
    }


def analyze_effort_recovery(
    effort,
    records,
    next_effort=None,
    ignore_heart_rate=False,
):
    """
    Анализирует восстановление после
    фактического окончания усилия.

    Не использует окончание сокращённого
    окна физиологического сравнения.
    """
    if ignore_heart_rate:
        records = [
            {
                key: value
                for key, value in record.items()
                if key != "heart_rate"
            }

            if isinstance(record, dict)
            else record

            for record in records
        ]

    indexed = prepare_effort_records(
        records
    )

    effort_start = parse_activity_date(
        effort["start"]
    )

    effort_end = parse_activity_date(
        effort["end"]
    )

    effort_duration = effort.get(
        "duration_seconds"
    )

    expected_duration = (
        effort_end - effort_start
    ).total_seconds() + 1

    if (
        isinstance(effort_duration, bool)
        or not isinstance(effort_duration, int)
        or effort_duration <= 0
        or expected_duration != effort_duration
    ):
        raise ValueError(
            "Некорректные границы усилия"
        )

    effort_window = extract_record_window(
        indexed_records=indexed,
        start=effort_start,
        duration_seconds=effort_duration,
    )

    effort_metrics = calculate_window_metrics(
        effort_window
    )

    end_heart_rate = calculate_edge_heart_rate(
        effort_window,
        edge="end",
    )

    available_seconds = (
        get_available_recovery_seconds(
            effort=effort,
            indexed_records=indexed,
            next_effort=next_effort,
        )
    )

    recovery_window = []

    if available_seconds > 0:
        recovery_window = extract_record_window(
            indexed_records=indexed,

            start=(
                effort_end
                + timedelta(seconds=1)
            ),

            duration_seconds=(
                available_seconds
            ),
        )

    recovery_peak = (
        find_recovery_heart_rate_peak(
            recovery_window
        )
    )

    checkpoints = {}

    for seconds in RECOVERY_CHECKPOINTS:
        checkpoints[str(seconds)] = (
            analyze_recovery_checkpoint(
                recovery_window=recovery_window,

                checkpoint_seconds=seconds,

                end_heart_rate=end_heart_rate,

                recovery_peak=recovery_peak,
            )
        )

    successful_checkpoints = sum(
        checkpoint["status"] == "ok"

        for checkpoint in checkpoints.values()
    )

    if successful_checkpoints == len(
        RECOVERY_CHECKPOINTS
    ):
        status = "ok"

    elif successful_checkpoints > 0:
        status = "partial"

    elif available_seconds > 0:
        status = "partial"

    else:
        status = "insufficient_data"

    return {
        "status": status,

        "effort_id": effort.get(
            "effort_id"
        ),

        "effort_duration_seconds": (
            effort_duration
        ),

        "effort_end": effort_end.isoformat(),

        "effort_metrics": effort_metrics,

        "end_heart_rate": end_heart_rate,

        "available_recovery_seconds": (
            available_seconds
        ),

        "next_effort_id": (
            next_effort.get("effort_id")
            if next_effort is not None
            else None
        ),

        "recovery_peak": recovery_peak,

        "checkpoints": checkpoints,

        "successful_checkpoints": (
            successful_checkpoints
        ),

        "ignore_heart_rate": (
            ignore_heart_rate
        ),

        "limitations": [
            (
                "Начало восстановления определяется "
                "по обнаруженной границе усилия"
            ),
            (
                "Следующее необнаруженное ускорение "
                "может влиять на результат"
            ),
            (
                "Показатели HRR рассчитываются "
                "для условий велосипедной нагрузки"
            ),
            (
                "Пик пульса определяется в пределах "
                "первых 30 секунд восстановления"
            ),
            (
                "Снижение пульса не является "
                "самостоятельным доказательством "
                "изменения физической формы"
            ),
        ],
    }


def calculate_relative_recovery_difference(
    first,
    second,
):
    """
    Рассчитывает симметричную
    относительную разницу.
    """
    if (
        not is_valid_number(first)
        or not is_valid_number(second)
        or first < 0
        or second < 0
    ):
        return None

    maximum = max(
        first,
        second,
    )

    if maximum == 0:
        return 0.0

    return abs(
        first - second
    ) / maximum


def compare_recovery_checkpoint(
    reference,
    candidate,
    conditions=None,
):
    """
    Сравнивает восстановление двух
    усилий в одинаковой контрольной точке.
    """
    if (
        reference["checkpoint_seconds"]
        != candidate["checkpoint_seconds"]
    ):
        raise ValueError(
            "Контрольные точки не совпадают"
        )

    result = {
        "checkpoint_seconds": reference[
            "checkpoint_seconds"
        ],

        "heart_rate_drop_difference_bpm": None,

        "recovery_power_difference_watts": None,

        "comparison_quality": "not_comparable",

        "limitations": [],

        "fitness_change": None,
    }

    if (
        reference["status"] != "ok"
        or candidate["status"] != "ok"
    ):
        return {
            **result,

            "status": "insufficient_data",

            "limitations": [
                "insufficient_checkpoint_data",
            ],
        }

    first_metrics = reference["metrics"]

    second_metrics = candidate["metrics"]

    power_difference = calculate_difference(
        first_metrics["average_power"],
        second_metrics["average_power"],
    )

    limitations = []

    if (
        power_difference is None
        or abs(power_difference)
        > MAX_RECOVERY_POWER_DIFFERENCE_WATTS
    ):
        limitations.append(
            "different_recovery_power"
        )

    if conditions is not None:
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

    comparable = (
        "different_recovery_power"
        not in limitations
    )

    heart_rate_difference = None

    if comparable:
        heart_rate_difference = (
            calculate_difference(
                reference[
                    "heart_rate_drop_from_end"
                ],

                candidate[
                    "heart_rate_drop_from_end"
                ],
            )
        )

    if not comparable:
        quality = "not_comparable"

    elif limitations:
        quality = "limited"

    else:
        quality = "preliminary"

    return {
        **result,

        "status": (
            "ok"
            if comparable
            else "partial"
        ),

        "heart_rate_drop_difference_bpm": (
            heart_rate_difference
        ),

        "recovery_power_difference_watts": (
            power_difference
        ),

        "comparison_quality": quality,

        "limitations": list(
            dict.fromkeys(limitations)
        ),
    }


def compare_effort_recovery(
    reference_effort,
    candidate_effort,
    reference_records,
    candidate_records,
    reference_next_effort=None,
    candidate_next_effort=None,
    conditions=None,
    reference_ignore_heart_rate=False,
    candidate_ignore_heart_rate=False,
):
    """
    Сравнивает восстановление после
    двух сопоставленных усилий.

    Все разницы рассчитываются как
    последняя тренировка минус предыдущая.
    """
    reference = analyze_effort_recovery(
        effort=reference_effort,

        records=reference_records,

        next_effort=reference_next_effort,

        ignore_heart_rate=(
            reference_ignore_heart_rate
        ),
    )

    candidate = analyze_effort_recovery(
        effort=candidate_effort,

        records=candidate_records,

        next_effort=candidate_next_effort,

        ignore_heart_rate=(
            candidate_ignore_heart_rate
        ),
    )

    limitations = []

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

    duration_difference = (
        calculate_relative_recovery_difference(
            reference[
                "effort_duration_seconds"
            ],

            candidate[
                "effort_duration_seconds"
            ],
        )
    )

    if (
        duration_difference is None
        or duration_difference
        > MAX_EFFORT_DURATION_DIFFERENCE
    ):
        limitations.append(
            "different_preceding_effort_duration"
        )

    first_metrics = reference[
        "effort_metrics"
    ]

    second_metrics = candidate[
        "effort_metrics"
    ]

    effort_power_difference = (
        calculate_relative_recovery_difference(
            first_metrics["average_power"],
            second_metrics["average_power"],
        )
    )

    if (
        first_metrics["status"] != "ok"
        or second_metrics["status"] != "ok"
    ):
        limitations.append(
            "incomplete_preceding_effort_data"
        )

    if (
        effort_power_difference is None
        or effort_power_difference
        > MAX_EFFORT_POWER_DIFFERENCE
    ):
        limitations.append(
            "different_preceding_effort_power"
        )

    end_hr_difference = calculate_difference(
        reference["end_heart_rate"],
        candidate["end_heart_rate"],
    )

    if end_hr_difference is None:
        limitations.append(
            "missing_end_heart_rate"
        )

    elif abs(
        end_hr_difference
    ) > MAX_END_HEART_RATE_DIFFERENCE:
        limitations.append(
            "different_end_heart_rate"
        )

    if (
        reference_ignore_heart_rate
        or candidate_ignore_heart_rate
    ):
        limitations.append(
            "heart_rate_excluded_by_settings"
        )

    if (
        reference["effort_duration_seconds"] < 60
        or candidate["effort_duration_seconds"] < 60
    ):
        limitations.append(
            "short_effort_heart_rate_lag"
        )

    limitations = list(
        dict.fromkeys(limitations)
    )

    checkpoints = {}

    blocking_limitations = {
        "different_preceding_effort_duration",
        "different_preceding_effort_power",
        "incomplete_preceding_effort_data",
        "missing_end_heart_rate",
        "heart_rate_excluded_by_settings",
    }

    blocked = any(
        limitation in blocking_limitations

        for limitation in limitations
    )

    for seconds in RECOVERY_CHECKPOINTS:
        key = str(seconds)

        comparison = compare_recovery_checkpoint(
            reference=reference[
                "checkpoints"
            ][key],

            candidate=candidate[
                "checkpoints"
            ][key],

            conditions={
                "limitations": limitations,
            },
        )

        comparison["limitations"] = list(
            dict.fromkeys(
                comparison["limitations"]
                + limitations
            )
        )

        if blocked:
            comparison[
                "heart_rate_drop_difference_bpm"
            ] = None

            comparison[
                "comparison_quality"
            ] = "not_comparable"

            if comparison["status"] == "ok":
                comparison["status"] = "partial"

        checkpoints[key] = comparison

    comparable_checkpoints = sum(
        checkpoint["status"] == "ok"

        for checkpoint in checkpoints.values()
    )

    if comparable_checkpoints == len(
        RECOVERY_CHECKPOINTS
    ):
        status = "ok"

    elif comparable_checkpoints > 0:
        status = "partial"

    elif (
        reference["successful_checkpoints"] > 0
        and candidate["successful_checkpoints"] > 0
    ):
        status = "not_comparable"

    else:
        status = "insufficient_data"

    return {
        "status": status,

        "reference": reference,

        "candidate": candidate,

        "checkpoints": checkpoints,

        "comparable_checkpoints": (
            comparable_checkpoints
        ),

        "end_heart_rate_difference_bpm": (
            end_hr_difference
        ),

        "effort_duration_difference_percent": (
            round(
                duration_difference * 100,
                2,
            )
            if duration_difference is not None
            else None
        ),

        "effort_power_difference_percent": (
            round(
                effort_power_difference * 100,
                2,
            )
            if effort_power_difference is not None
            else None
        ),

        "limitations": limitations,

        "fitness_change": None,
    }