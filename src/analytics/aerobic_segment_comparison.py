from collections import Counter

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


SUPPORTED_COMPARISON_MODES = {
    "within_workout",
    "between_workouts",
}

MAX_POWER_DIFFERENCE_RATIO = 0.05
MAX_DURATION_DIFFERENCE_RATIO = 0.20

MIN_PAIRED_COVERAGE_RATIO = 0.90

MAX_FTP_INTENSITY_DIFFERENCE_PP = 5

MAX_CADENCE_DIFFERENCE_RPM = 10

MAX_PREVIOUS_WORK_DIFFERENCE_RATIO = 0.15

MAX_ACCUMULATED_WORK_DIFFERENCE_RATIO = 0.20

MAX_TEMPERATURE_DIFFERENCE = 5


def get_numeric_value(data, key):
    """
    Безопасно получает числовое значение.
    """
    if not isinstance(data, dict):
        return None

    value = data.get(key)

    if not is_valid_number(value):
        return None

    return value


def calculate_relative_difference(first, second):
    """
    Симметричное относительное различие.

    Используется для оценки сопоставимости,
    а не направления изменения показателя.
    """
    if not (
        is_valid_number(first)
        and is_valid_number(second)
    ):
        return None

    denominator = max(
        abs(first),
        abs(second),
    )

    if denominator == 0:
        return 0.0

    return abs(first - second) / denominator


def calculate_signed_difference(reference, candidate):
    """
    Изменение от предыдущего сегмента
    к новому.
    """
    if not (
        is_valid_number(reference)
        and is_valid_number(candidate)
    ):
        return None

    return round(
        reference - candidate,
        2,
    )


def calculate_percent_change(reference, candidate):
    """
    Процентное изменение нового значения
    относительно предыдущего.
    """
    if not (
        is_valid_number(reference)
        and is_valid_number(candidate)
    ):
        return None

    if candidate <= 0:
        return None

    return round(
        (reference / candidate - 1) * 100,
        2,
    )


def get_segment_profile(segment):
    """
    Извлекает параметры, необходимые
    для сравнения аэробных сегментов.
    """
    metrics = segment.get("metrics") or {}

    efficiency = segment.get("efficiency") or {}

    drift = segment.get("drift") or {}

    previous_load = segment.get(
        "previous_load"
    ) or {}

    accumulated = segment.get(
        "accumulated_load"
    ) or {}

    power = get_numeric_value(
        metrics,
        "average_power",
    )

    ftp = get_numeric_value(
        segment,
        "ftp",
    )

    ftp_intensity = None

    if (
        power is not None
        and ftp is not None
        and ftp > 0
    ):
        ftp_intensity = power / ftp * 100

    previous_work = None

    if (
        previous_load.get("complete_power") is True
        and previous_load.get("complete_timing") is True
    ):
        previous_work = get_numeric_value(
            previous_load,
            "work_kj",
        )

    accumulated_work = None

    if accumulated.get("status") == "ok":
        accumulated_work = get_numeric_value(
            accumulated,
            "total_work_kj",
        )

    return {
        "segment_id": segment.get("segment_id"),

        "status": segment.get("status"),

        "analysis_start": segment.get(
            "analysis_start"
        ),

        "analysis_end": segment.get(
            "analysis_end"
        ),

        "duration_seconds": get_numeric_value(
            segment,
            "duration_seconds",
        ),

        "average_power": power,

        "ftp": ftp,

        "ftp_intensity_percent": ftp_intensity,

        "average_heart_rate": get_numeric_value(
            metrics,
            "average_heart_rate",
        ),

        "average_cadence": get_numeric_value(
            metrics,
            "average_cadence",
        ),

        "cadence_coverage_ratio": get_numeric_value(
            metrics,
            "cadence_coverage_ratio",
        ),

        "paired_power": get_numeric_value(
            efficiency,
            "average_paired_power",
        ),

        "paired_heart_rate": get_numeric_value(
            efficiency,
            "average_paired_heart_rate",
        ),

        "efficiency_factor": get_numeric_value(
            efficiency,
            "efficiency_factor",
        ),

        "efficiency_method": efficiency.get(
            "method"
        ),

        "efficiency_status": efficiency.get(
            "status"
        ),

        "paired_coverage_ratio": get_numeric_value(
            efficiency,
            "paired_coverage_ratio",
        ),

        "drift_percent": get_numeric_value(
            drift,
            "drift_percent",
        ),

        "drift_status": drift.get("status"),

        "drift_method": drift.get("method"),

        "previous_work_kj": previous_work,

        "accumulated_work_kj": accumulated_work,

        "observed_work_kj": get_numeric_value(
            accumulated,
            "observed_work_kj",
        ),

        "elapsed_seconds": get_numeric_value(
            accumulated,
            "elapsed_seconds_before_segment",
        ),

        "observed_high_intensity_seconds": (
            get_numeric_value(
                accumulated,
                "observed_high_intensity_seconds",
            )
        ),

        "detection_method": segment.get(
            "detection_method"
        ),
    }


def assess_environment_conditions(
    reference_conditions,
    candidate_conditions,
    mode,
):
    """
    Оценивает внешние условия сравнения.
    """
    blockers = []
    limitations = []

    reference_conditions = (
        reference_conditions or {}
    )

    candidate_conditions = (
        candidate_conditions or {}
    )

    temperature_difference = None

    if mode == "within_workout":
        return {
            "blockers": blockers,

            "limitations": limitations,

            "temperature_difference": None,

            "scope": "same_workout",
        }

    first_environment = reference_conditions.get(
        "environment"
    )

    second_environment = candidate_conditions.get(
        "environment"
    )

    known_environments = {
        "indoor",
        "outdoor",
    }

    if (
        first_environment in known_environments
        and second_environment in known_environments
    ):
        if first_environment != second_environment:
            blockers.append(
                "different_environment"
            )

    else:
        limitations.append(
            "unknown_environment"
        )

    first_temperature = get_numeric_value(
        reference_conditions,
        "average_temperature",
    )

    second_temperature = get_numeric_value(
        candidate_conditions,
        "average_temperature",
    )

    if (
        first_temperature is not None
        and second_temperature is not None
    ):
        temperature_difference = round(
            first_temperature - second_temperature,
            2,
        )

        if (
            abs(temperature_difference)
            > MAX_TEMPERATURE_DIFFERENCE
        ):
            limitations.append(
                "different_temperature"
            )

    else:
        limitations.append(
            "unknown_temperature"
        )

    first_power_meter = reference_conditions.get(
        "power_meter"
    )

    second_power_meter = candidate_conditions.get(
        "power_meter"
    )

    if first_power_meter and second_power_meter:
        if first_power_meter != second_power_meter:
            limitations.append(
                "different_power_meter"
            )

    else:
        limitations.append(
            "unknown_power_meter"
        )

    return {
        "blockers": blockers,

        "limitations": limitations,

        "temperature_difference": (
            temperature_difference
        ),

        "scope": "different_workouts",
    }


def assess_aerobic_comparison_quality(
    reference,
    candidate,
    mode,
    reference_conditions=None,
    candidate_conditions=None,
):
    """
    Определяет пригодность сегментов
    для физиологического сравнения.

    Не использует величину ЧСС или EF
    для выбора наиболее похожих сегментов.
    """
    if mode not in SUPPORTED_COMPARISON_MODES:
        raise ValueError(
            "Неизвестный режим сравнения"
        )

    blockers = []
    limitations = []

    for profile in (
        reference,
        candidate,
    ):
        if profile["status"] not in {
            "ok",
            "partial",
        }:
            blockers.append(
                "invalid_segment_status"
            )

        coverage = profile[
            "paired_coverage_ratio"
        ]

        if (
            coverage is None
            or coverage < MIN_PAIRED_COVERAGE_RATIO
            or coverage > 1
        ):
            blockers.append(
                "insufficient_paired_coverage"
            )

        elif coverage < 1:
            limitations.append(
                "partial_paired_coverage"
            )

        if profile["efficiency_factor"] is None:
            blockers.append(
                "efficiency_unavailable"
            )

        for field in (
            "average_power",
            "paired_power",
            "paired_heart_rate",
            "duration_seconds",
        ):
            value = profile.get(field)

            if value is None or value <= 0:
                blockers.append(
                    f"invalid_{field}"
                )

    power_difference = (
        calculate_relative_difference(
            reference["average_power"],
            candidate["average_power"],
        )
    )

    if (
        power_difference is None
        or power_difference > MAX_POWER_DIFFERENCE_RATIO
    ):
        blockers.append(
            "different_average_power"
        )

    paired_power_difference = (
        calculate_relative_difference(
            reference["paired_power"],
            candidate["paired_power"],
        )
    )

    if (
        paired_power_difference is None
        or paired_power_difference
        > MAX_POWER_DIFFERENCE_RATIO
    ):
        blockers.append(
            "different_paired_power"
        )

    duration_difference = (
        calculate_relative_difference(
            reference["duration_seconds"],
            candidate["duration_seconds"],
        )
    )

    if (
        duration_difference is None
        or duration_difference
        > MAX_DURATION_DIFFERENCE_RATIO
    ):
        blockers.append(
            "different_duration"
        )

    if (
        reference["efficiency_method"]
        != "average_power_to_hr"

        or candidate["efficiency_method"]
        != "average_power_to_hr"
    ):
        blockers.append(
            "incompatible_efficiency_method"
        )

    ftp_intensity_difference = (
        calculate_signed_difference(
            reference["ftp_intensity_percent"],
            candidate["ftp_intensity_percent"],
        )
    )

    if ftp_intensity_difference is None:
        limitations.append(
            "unknown_relative_intensity"
        )

    elif (
        abs(ftp_intensity_difference)
        > MAX_FTP_INTENSITY_DIFFERENCE_PP
    ):
        limitations.append(
            "different_relative_intensity"
        )

    cadence_difference = (
        calculate_signed_difference(
            reference["average_cadence"],
            candidate["average_cadence"],
        )
    )

    cadence_coverage = [
        reference["cadence_coverage_ratio"],
        candidate["cadence_coverage_ratio"],
    ]

    if (
        cadence_difference is None

        or any(
            value is None or value < 0.90
            for value in cadence_coverage
        )
    ):
        limitations.append(
            "insufficient_cadence_context"
        )

    elif (
        abs(cadence_difference)
        > MAX_CADENCE_DIFFERENCE_RPM
    ):
        limitations.append(
            "different_cadence"
        )

    previous_work_difference = (
        calculate_relative_difference(
            reference["previous_work_kj"],
            candidate["previous_work_kj"],
        )
    )

    if previous_work_difference is None:
        limitations.append(
            "incomplete_previous_load"
        )

    elif (
        previous_work_difference
        > MAX_PREVIOUS_WORK_DIFFERENCE_RATIO
    ):
        limitations.append(
            "different_previous_load"
        )

    accumulated_work_difference = (
        calculate_relative_difference(
            reference["accumulated_work_kj"],
            candidate["accumulated_work_kj"],
        )
    )

    if accumulated_work_difference is None:
        limitations.append(
            "incomplete_accumulated_load"
        )

    elif (
        mode == "between_workouts"

        and accumulated_work_difference
        > MAX_ACCUMULATED_WORK_DIFFERENCE_RATIO
    ):
        limitations.append(
            "different_accumulated_load"
        )

    conditions = assess_environment_conditions(
        reference_conditions=reference_conditions,

        candidate_conditions=candidate_conditions,

        mode=mode,
    )

    blockers.extend(
        conditions["blockers"]
    )

    limitations.extend(
        conditions["limitations"]
    )

    blockers = list(
        dict.fromkeys(blockers)
    )

    limitations = list(
        dict.fromkeys(limitations)
    )

    if blockers:
        quality = "not_comparable"

    elif limitations:
        quality = "limited"

    else:
        quality = "preliminary"

    def as_percent(value):
        if value is None:
            return None

        return round(value * 100, 2)

    return {
        "quality": quality,

        "heart_rate_comparable": not blockers,

        "blockers": blockers,

        "limitations": limitations,

        "power_difference_percent": (
            as_percent(power_difference)
        ),

        "paired_power_difference_percent": (
            as_percent(paired_power_difference)
        ),

        "duration_difference_percent": (
            as_percent(duration_difference)
        ),

        "ftp_intensity_difference_pp": (
            ftp_intensity_difference
        ),

        "cadence_difference_rpm": (
            cadence_difference
        ),

        "previous_work_difference_percent": (
            as_percent(previous_work_difference)
        ),

        "accumulated_work_difference_percent": (
            as_percent(accumulated_work_difference)
        ),

        "conditions": conditions,

        "fitness_change": None,
    }


def compare_aerobic_segments(
    reference_segment,
    candidate_segment,
    mode="between_workouts",
    reference_conditions=None,
    candidate_conditions=None,
):
    """
    Сравнивает два аэробных сегмента.

    reference_segment:
        новый или более поздний сегмент.

    candidate_segment:
        предыдущий или более ранний сегмент.

    Все изменения рассчитываются как
    reference минус candidate.
    """
    reference = get_segment_profile(
        reference_segment
    )

    candidate = get_segment_profile(
        candidate_segment
    )

    quality = assess_aerobic_comparison_quality(
        reference=reference,

        candidate=candidate,

        mode=mode,

        reference_conditions=reference_conditions,

        candidate_conditions=candidate_conditions,
    )

    if mode == "within_workout":
        reference_start = parse_activity_date(
            reference["analysis_start"]
        )

        candidate_end = parse_activity_date(
            candidate["analysis_end"]
        )

        if (
            reference_start is None
            or candidate_end is None
            or reference_start <= candidate_end
        ):
            quality["blockers"].append(
                "overlapping_or_unordered_segments"
            )

            quality["quality"] = "not_comparable"

            quality["heart_rate_comparable"] = False

    comparable = quality[
        "heart_rate_comparable"
    ]

    differences = {
        "average_power_watts": (
            calculate_signed_difference(
                reference["average_power"],
                candidate["average_power"],
            )
        ),

        "duration_seconds": (
            calculate_signed_difference(
                reference["duration_seconds"],
                candidate["duration_seconds"],
            )
        ),

        "heart_rate_bpm": None,

        "efficiency_factor": None,

        "efficiency_change_percent": None,

        "drift_difference_pp": None,

        "accumulated_work_kj": (
            calculate_signed_difference(
                reference["accumulated_work_kj"],
                candidate["accumulated_work_kj"],
            )
        ),

        "elapsed_seconds": (
            calculate_signed_difference(
                reference["elapsed_seconds"],
                candidate["elapsed_seconds"],
            )
        ),
    }

    drift_comparable = False

    if comparable:
        differences["heart_rate_bpm"] = (
            calculate_signed_difference(
                reference["paired_heart_rate"],
                candidate["paired_heart_rate"],
            )
        )

        differences["efficiency_factor"] = round(
            reference["efficiency_factor"]
            - candidate["efficiency_factor"],
            6,
        )

        differences["efficiency_change_percent"] = (
            calculate_percent_change(
                reference["efficiency_factor"],
                candidate["efficiency_factor"],
            )
        )

        drift_comparable = (
            reference["drift_percent"] is not None

            and candidate["drift_percent"] is not None

            and reference["drift_method"]
            == candidate["drift_method"]
            == "average_power_to_hr"

            and reference["drift_status"] == "ok"

            and candidate["drift_status"] == "ok"
        )

        if drift_comparable:
            differences["drift_difference_pp"] = (
                calculate_signed_difference(
                    reference["drift_percent"],
                    candidate["drift_percent"],
                )
            )

    if not comparable:
        status = "not_comparable"

    elif quality["quality"] == "limited":
        status = "partial"

    else:
        status = "ok"

    return {
        "status": status,

        "comparison_mode": mode,

        "comparison_method": (
            "full_aerobic_segment"
        ),

        "reference": reference,

        "candidate": candidate,

        "differences": differences,

        "comparison_quality": quality,

        "drift_comparable": drift_comparable,

        "fitness_change": None,

        "limitations": [
            (
                "Сравниваются полные сегменты, "
                "а не выровненные временные окна"
            ),
            (
                "Различия ЧСС и EF не доказывают "
                "изменение физической формы"
            ),
            (
                "Динамика между сегментами "
                "не является непрерывным "
                "аэробным дрейфом"
            ),
        ],
    }


def compare_aerobic_progression(
    aerobic_analysis,
):
    """
    Сравнивает первый пригодный сегмент
    с последующими сегментами тренировки.

    Первый сегмент выбирается по времени,
    а не по величине ЧСС или EF.
    """
    result = {
        "status": "insufficient_data",

        "comparison_mode": "within_workout",

        "baseline_segment_id": None,

        "comparisons": [],

        "summary": {
            "available_segments_count": 0,

            "comparisons_count": 0,

            "comparable_segments_count": 0,

            "comparison_quality_counts": {},
        },

        "fitness_change": None,
    }

    segments = [
        segment

        for segment in aerobic_analysis.get(
            "segments", []
        )

        if (
            segment.get("status") in {
                "ok",
                "partial",
            }

            and parse_activity_date(
                segment.get("analysis_start")
            ) is not None
        )
    ]

    segments.sort(
        key=lambda segment: parse_activity_date(
            segment["analysis_start"]
        )
    )

    result["summary"][
        "available_segments_count"
    ] = len(segments)

    if len(segments) < 2:
        return result

    baseline = segments[0]

    comparisons = [
        compare_aerobic_segments(
            reference_segment=segment,

            candidate_segment=baseline,

            mode="within_workout",
        )

        for segment in segments[1:]
    ]

    comparable_count = sum(
        comparison["comparison_quality"][
            "heart_rate_comparable"
        ]

        for comparison in comparisons
    )

    quality_counts = Counter(
        comparison["comparison_quality"][
            "quality"
        ]

        for comparison in comparisons
    )

    if comparable_count == 0:
        status = "not_comparable"

    elif any(
        comparison["status"] != "ok"

        for comparison in comparisons
    ):
        status = "partial"

    else:
        status = "ok"

    return {
        **result,

        "status": status,

        "baseline_segment_id": baseline[
            "segment_id"
        ],

        "comparisons": comparisons,

        "summary": {
            "available_segments_count": len(
                segments
            ),

            "comparisons_count": len(
                comparisons
            ),

            "comparable_segments_count": (
                comparable_count
            ),

            "comparison_quality_counts": dict(
                quality_counts
            ),
        },
    }