from statistics import mean

from src.analytics.workout_classification import (
    classify_workout,
    prepare_power_records,
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


MAX_SHORT_DIP_SECONDS = 3


def analyze_interval_transition(
    previous_interval,
    next_interval,
    records,
    ftp,
):
    """
    Анализирует участок между двумя
    обнаруженными интенсивными отрезками.

    Не объединяет интервалы и не изменяет
    исходные записи.
    """
    previous_end = parse_activity_date(
        previous_interval["end"]
    )

    next_start = parse_activity_date(
        next_interval["start"]
    )

    expected_seconds = (
        next_start - previous_end
    ).total_seconds() - 1

    if expected_seconds < 0:
        return {
            "status": "invalid",
            "transition_type": "unknown",
            "reason": "Интервалы пересекаются",
        }

    transition_records = [
        record
        for record in records
        if previous_end
        < record["timestamp"]
        < next_start
    ]

    recorded_seconds = len(
        transition_records
    )

    result = {
        "status": "ok",

        "previous_interval_end": (
            previous_end.isoformat()
        ),

        "next_interval_start": (
            next_start.isoformat()
        ),

        "duration_seconds": (
            expected_seconds
        ),

        "recorded_seconds": (
            recorded_seconds
        ),

        "average_power": None,
        "min_power": None,
        "max_power": None,

        "average_power_ftp_percent": None,

        "average_heart_rate": None,
        "heart_rate_samples": 0,

        "power_drop_percent": None,
        "possible_power_dip": False,

        "transition_type": "unknown",
    }

    if expected_seconds == 0:
        result["transition_type"] = (
            "adjacent_intervals"
        )

        return result

    if transition_records:
        powers = [
            record["power"]
            for record in transition_records
        ]

        average_power = mean(powers)

        heart_rates = [
            record["heart_rate"]
            for record in transition_records
            if (
                is_valid_number(
                    record.get("heart_rate")
                )
                and record["heart_rate"] > 0
            )
        ]

        reference_power = min(
            previous_interval["average_power"],
            next_interval["average_power"],
        )

        result.update({
            "average_power": round(
                average_power, 2
            ),

            "min_power": min(powers),
            "max_power": max(powers),

            "average_power_ftp_percent": round(
                average_power / ftp * 100,
                2,
            ),

            "average_heart_rate": (
                round(mean(heart_rates), 2)
                if heart_rates
                else None
            ),

            "heart_rate_samples": len(
                heart_rates
            ),

            "power_drop_percent": (
                round(
                    (
                        reference_power
                        - average_power
                    )
                    / reference_power
                    * 100,
                    2,
                )
                if reference_power > 0
                else None
            ),
        })

    timing_records = [
        previous_end,
        *[
            record["timestamp"]
            for record in transition_records
        ],
        next_start,
    ]

    has_missing_data = (
        abs(
            recorded_seconds
            - expected_seconds
        ) >= 0.01
        or any(
            abs(
                (
                    timing_records[index + 1]
                    - timing_records[index]
                ).total_seconds() - 1.0
            ) >= 0.01
            for index in range(
                len(timing_records) - 1
            )
        )
    )

    if has_missing_data:
        result["status"] = "partial"

        result["transition_type"] = (
            "data_gap"
        )

        return result

    if (
        expected_seconds
        <= MAX_SHORT_DIP_SECONDS
    ):
        result["transition_type"] = (
            "short_power_dip"
        )

        result["possible_power_dip"] = True

    else:
        result["transition_type"] = (
            "lower_power_segment"
        )

    return result


def analyze_workout_structure(
    records,
    ftp,
):
    """
    Анализирует структуру тренировки.

    Сохраняет все обнаруженные интенсивные
    отрезки и описывает участки между ними.

    Не предполагает автоматически, что
    снижение мощности является отдыхом.
    """
    classification = classify_workout(
        records=records,
        ftp=ftp,
    )

    if classification["status"] != "ok":
        return {
            "status": "insufficient_data",
            "classification": classification,
            "intervals": [],
            "transitions": [],
        }

    prepared = prepare_power_records(
        records
    )

    power_records = prepared["records"]

    intervals = classification[
        "high_intensity"
    ]["intervals"]

    transitions = []

    for index in range(
        len(intervals) - 1
    ):
        transition = analyze_interval_transition(
            previous_interval=intervals[index],
            next_interval=intervals[index + 1],
            records=power_records,
            ftp=ftp,
        )

        transition["previous_interval_number"] = (
            index + 1
        )

        transition["next_interval_number"] = (
            index + 2
        )

        transitions.append(transition)

    short_dips = [
        transition
        for transition in transitions
        if transition["transition_type"]
        == "short_power_dip"
    ]

    lower_power_segments = [
        transition
        for transition in transitions
        if transition["transition_type"]
        == "lower_power_segment"
    ]

    data_gaps = [
        transition
        for transition in transitions
        if transition["transition_type"]
        == "data_gap"
    ]

    return {
        "status": "ok",

        "classification": classification,

        "intervals": intervals,

        "transitions": transitions,

        "structure_summary": {
            "detected_intervals_count": len(
                intervals
            ),

            "transitions_count": len(
                transitions
            ),

            "short_power_dips_count": len(
                short_dips
            ),

            "lower_power_segments_count": len(
                lower_power_segments
            ),

            "data_gaps_count": len(
                data_gaps
            ),

            "requires_structure_refinement": (
                bool(short_dips)
                or bool(data_gaps)
            ),
        },

        "limitations": [
            (
                "Интенсивные отрезки "
                "не объединяются автоматически"
            ),
            (
                "Короткое снижение мощности "
                "может быть намеренным"
            ),
            (
                "Участок сниженной мощности "
                "не обязательно является "
                "физиологическим восстановлением"
            ),
            (
                "Пока анализируются только "
                "интенсивные отрезки, обнаруженные "
                "существующим классификатором"
            ),
        ],
    }