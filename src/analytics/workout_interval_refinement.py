
from statistics import mean

from src.analytics.workout_classification import (
    prepare_power_records,
    is_valid_number,
)

from src.analytics.workout_structure import (
    analyze_workout_structure,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


MAX_DIP_SECONDS = 3

MIN_DIP_POWER_RATIO = 0.85

MAX_INTERVAL_POWER_DIFFERENCE = 0.10


def evaluate_interval_connection(
    previous_interval,
    next_interval,
    transition,
):
    """
    Проверяет, могут ли два интенсивных
    отрезка относиться к одному рабочему
    интервалу.

    Не изменяет исходные данные.
    """
    reasons = []

    if transition.get("status") != "ok":
        reasons.append(
            "transition_data_quality"
        )

    if transition.get("transition_type") != (
        "short_power_dip"
    ):
        reasons.append(
            "not_short_power_dip"
        )

    duration = transition.get(
        "duration_seconds"
    )

    recorded = transition.get(
        "recorded_seconds"
    )

    if (
        not is_valid_number(duration)
        or not 0 < duration <= MAX_DIP_SECONDS
    ):
        reasons.append(
            "dip_duration"
        )

    if recorded != duration:
        reasons.append(
            "incomplete_transition_records"
        )

    previous_power = previous_interval.get(
        "average_power"
    )

    next_power = next_interval.get(
        "average_power"
    )

    min_dip_power = transition.get(
        "min_power"
    )

    reference_power = None
    power_difference = None
    dip_power_ratio = None

    if (
        is_valid_number(previous_power)
        and is_valid_number(next_power)
        and previous_power > 0
        and next_power > 0
    ):
        reference_power = min(
            previous_power,
            next_power,
        )

        power_difference = (
            abs(previous_power - next_power)
            / reference_power
        )

        if (
            power_difference
            > MAX_INTERVAL_POWER_DIFFERENCE
        ):
            reasons.append(
                "different_interval_power"
            )

        if is_valid_number(min_dip_power):
            dip_power_ratio = (
                min_dip_power
                / reference_power
            )

            if (
                dip_power_ratio
                < MIN_DIP_POWER_RATIO
            ):
                reasons.append(
                    "dip_power_too_low"
                )

        else:
            reasons.append(
                "missing_dip_power"
            )

    else:
        reasons.append(
            "invalid_interval_power"
        )

    return {
        "can_connect": not reasons,

        "decision": (
            "likely_same_work_interval"
            if not reasons
            else "keep_separate"
        ),

        "reasons": reasons,

        "reference_power": reference_power,

        "interval_power_difference_percent": (
            round(power_difference * 100, 2)
            if power_difference is not None
            else None
        ),

        "minimum_dip_power_percent": (
            round(dip_power_ratio * 100, 2)
            if dip_power_ratio is not None
            else None
        ),
    }


def build_refined_interval(
    intervals,
    interval_numbers,
    records,
    ftp,
):
    """
    Формирует предполагаемый рабочий интервал.

    Метрики рассчитываются по фактическим
    посекундным записям, включая участки
    кратковременного снижения мощности.
    """
    start = parse_activity_date(
        intervals[0]["start"]
    )

    end = parse_activity_date(
        intervals[-1]["end"]
    )

    interval_records = [
        record
        for record in records
        if start <= record["timestamp"] <= end
    ]

    if not interval_records:
        raise ValueError(
            "Нет записей рабочего интервала"
        )

    expected_duration = int(
        (end - start).total_seconds()
    ) + 1

    if len(interval_records) != expected_duration:
        raise ValueError(
            "Неполные записи рабочего интервала"
        )

    if any(
        abs(
            (
                interval_records[index + 1]["timestamp"]
                - interval_records[index]["timestamp"]
            ).total_seconds() - 1.0
        ) >= 0.01
        for index in range(len(interval_records) - 1)
    ):
        raise ValueError(
            "Непрерывность рабочего интервала нарушена"
        )

    powers = [
        record["power"]
        for record in interval_records
    ]

    heart_rates = [
        record["heart_rate"]
        for record in interval_records
        if (
            is_valid_number(
                record.get("heart_rate")
            )
            and record["heart_rate"] > 0
        )
    ]

    cadences = [
        record["cadence"]
        for record in interval_records
        if (
            is_valid_number(
                record.get("cadence")
            )
            and record["cadence"] >= 0
        )
    ]

    average_power = mean(powers)

    original_duration = sum(
        interval["duration_seconds"]
        for interval in intervals
    )

    refined_duration = len(
        interval_records
    )

    return {
        "start": start.isoformat(),

        "end": end.isoformat(),

        "duration_seconds": refined_duration,

        "average_power": round(
            average_power, 2
        ),

        "max_power": max(powers),

        "min_power": min(powers),

        "average_power_ftp_percent": round(
            average_power / ftp * 100,
            2,
        ),

        "average_heart_rate": (
            round(mean(heart_rates), 2)
            if heart_rates
            else None
        ),

        "max_heart_rate": (
            max(heart_rates)
            if heart_rates
            else None
        ),

        "heart_rate_samples": len(
            heart_rates
        ),

        "heart_rate_coverage_ratio": round(
            len(heart_rates) / refined_duration,
            4,
        ),

        "average_cadence": (
            round(mean(cadences), 2)
            if cadences
            else None
        ),

        "cadence_samples": len(cadences),

        "source_interval_numbers": (
            list(interval_numbers)
        ),

        "source_intervals_count": len(
            intervals
        ),

        "original_high_intensity_seconds": (
            original_duration
        ),

        "included_transition_seconds": (
            refined_duration
            - original_duration
        ),

        "was_refined": len(intervals) > 1,

        "boundary_confidence": (
            "estimated"
            if len(intervals) > 1
            else "threshold_detected"
        ),
    }


def refine_workout_intervals(
    records,
    ftp,
):
    """
    Уточняет предполагаемые рабочие интервалы.

    Сохраняет исходную структуру и отдельно
    формирует уточнённую.

    Не объединяет интервалы через пропуски
    данных или полноценные участки
    сниженной мощности.
    """
    structure = analyze_workout_structure(
        records=records,
        ftp=ftp,
    )

    if structure["status"] != "ok":
        return {
            "status": "insufficient_data",
            "original_structure": structure,
            "original_intervals": [],
            "refined_intervals": [],
            "connection_decisions": [],
        }

    original_intervals = structure[
        "intervals"
    ]

    transitions = structure[
        "transitions"
    ]

    prepared = prepare_power_records(
        records
    )

    power_records = prepared["records"]

    refined_intervals = []
    connection_decisions = []

    current_group = []
    current_numbers = []

    for index, interval in enumerate(
        original_intervals
    ):
        interval_number = index + 1

        if not current_group:
            current_group = [interval]

            current_numbers = [
                interval_number
            ]

            continue

        previous_interval = (
            original_intervals[index - 1]
        )

        transition = transitions[index - 1]

        decision = evaluate_interval_connection(
            previous_interval=previous_interval,
            next_interval=interval,
            transition=transition,
        )

        decision["previous_interval_number"] = (
            index
        )

        decision["next_interval_number"] = (
            interval_number
        )

        connection_decisions.append(
            decision
        )

        if decision["can_connect"]:
            current_group.append(interval)

            current_numbers.append(
                interval_number
            )

        else:
            refined_intervals.append(
                build_refined_interval(
                    intervals=current_group,
                    interval_numbers=current_numbers,
                    records=power_records,
                    ftp=ftp,
                )
            )

            current_group = [interval]

            current_numbers = [
                interval_number
            ]

    if current_group:
        refined_intervals.append(
            build_refined_interval(
                intervals=current_group,
                interval_numbers=current_numbers,
                records=power_records,
                ftp=ftp,
            )
        )

    connected_transitions = sum(
        decision["can_connect"]
        for decision in connection_decisions
    )

    total_duration = sum(
        interval["duration_seconds"]
        for interval in refined_intervals
    )

    original_high_intensity_seconds = sum(
        interval["duration_seconds"]
        for interval in original_intervals
    )

    if total_duration:
        average_interval_power = sum(
            interval["average_power"]
            * interval["duration_seconds"]
            for interval in refined_intervals
        ) / total_duration

    else:
        average_interval_power = None

    return {
        "status": "ok",

        "original_structure": structure,

        "original_intervals": original_intervals,

        "refined_intervals": refined_intervals,

        "connection_decisions": (
            connection_decisions
        ),

        "summary": {
            "original_intervals_count": len(
                original_intervals
            ),

            "refined_intervals_count": len(
                refined_intervals
            ),

            "connected_transitions_count": (
                connected_transitions
            ),

            "original_high_intensity_seconds": (
                original_high_intensity_seconds
            ),

            "refined_work_seconds": (
                total_duration
            ),

            "included_transition_seconds": (
                total_duration
                - original_high_intensity_seconds
            ),

            "average_interval_duration_seconds": (
                round(
                    total_duration
                    / len(refined_intervals),
                    2,
                )
                if refined_intervals
                else None
            ),

            "average_interval_power": (
                round(average_interval_power, 2)
                if average_interval_power
                is not None
                else None
            ),
        },

        "limitations": [
            (
                "Уточнённые интервалы являются "
                "оценкой фактической структуры"
            ),
            (
                "Исходные интенсивные отрезки "
                "сохраняются без изменений"
            ),
            (
                "Короткий участок снижения "
                "мощности может быть намеренным"
            ),
            (
                "Критерии уточнения применяются "
                "к соседним отрезкам"
            ),
            (
                "Границы начала и окончания "
                "рабочих интервалов пока "
                "определяются порогом мощности"
            ),
        ],
    }
