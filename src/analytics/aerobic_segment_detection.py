from collections import deque
from statistics import mean, pstdev

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    get_valid_field,
)


MIN_AEROBIC_FTP_RATIO = 0.56
MAX_AEROBIC_FTP_RATIO = 0.75

MIN_SEGMENT_SECONDS = 600

MIN_DRIFT_CANDIDATE_SECONDS = 1200

SMOOTHING_WINDOW_SECONDS = 30

INITIAL_ADAPTATION_SECONDS = 180

MAX_POWER_CV_PERCENT = 10

MIN_ZONE_COVERAGE_RATIO = 0.80

HARD_BREAK_FTP_RATIO = 1.05


def prepare_aerobic_power_segments(records):
    """
    Формирует непрерывные последовательности
    посекундных записей мощности.

    Разрывает последовательность при:
    - пропущенной мощности;
    - пропущенной секунде;
    - некорректной временной отметке;
    - дублирующихся временных отметках.

    Нулевая мощность считается валидной.
    """
    indexed = prepare_effort_records(records)

    segments = []

    current_segment = []

    previous_timestamp = None

    for timestamp in sorted(indexed):
        record = indexed[timestamp]

        power = get_valid_field(
            record,
            "power",
        )

        if power is None:
            if current_segment:
                segments.append(current_segment)

            current_segment = []
            previous_timestamp = None

            continue

        if previous_timestamp is not None:
            difference = (
                timestamp - previous_timestamp
            ).total_seconds()

            if difference != 1:
                if current_segment:
                    segments.append(
                        current_segment
                    )

                current_segment = []

        current_segment.append({
            **record,
            "timestamp": timestamp,
            "power": power,
        })

        previous_timestamp = timestamp

    if current_segment:
        segments.append(current_segment)

    return segments


def find_aerobic_candidates(
    records,
    ftp,
):
    """
    Ищет непрерывные участки,
    соответствующие аэробной мощности.

    Сглаживание используется только
    для обнаружения границ.

    Итоговые метрики рассчитываются
    по исходной мощности.
    """
    minimum_power = (
        ftp * MIN_AEROBIC_FTP_RATIO
    )

    maximum_power = (
        ftp * MAX_AEROBIC_FTP_RATIO
    )

    hard_break_power = (
        ftp * HARD_BREAK_FTP_RATIO
    )

    rolling_window = deque()

    rolling_sum = 0.0

    candidates = []

    current_candidate = []

    for record in records:
        power = record["power"]

        if power > hard_break_power:
            if current_candidate:
                candidates.append(
                    current_candidate
                )

            current_candidate = []

            rolling_window.clear()
            rolling_sum = 0.0

            continue

        rolling_window.append(power)

        rolling_sum += power

        if len(rolling_window) > (
            SMOOTHING_WINDOW_SECONDS
        ):
            rolling_sum -= (
                rolling_window.popleft()
            )

        if len(rolling_window) < (
            SMOOTHING_WINDOW_SECONDS
        ):
            continue

        smoothed_power = (
            rolling_sum
            / len(rolling_window)
        )

        in_aerobic_zone = (
            minimum_power
            <= smoothed_power
            <= maximum_power
        )

        if in_aerobic_zone:
            current_candidate.append(record)

        else:
            if current_candidate:
                candidates.append(
                    current_candidate
                )

            current_candidate = []

    if current_candidate:
        candidates.append(current_candidate)

    return candidates


def calculate_aerobic_power_metrics(
    records,
    ftp,
):
    """
    Рассчитывает характеристики
    исходной мощности участка.
    """
    if not records:
        return {
            "status": "insufficient_data",
        }

    powers = [
        record["power"]
        for record in records
    ]

    average_power = mean(powers)

    power_std = pstdev(powers)

    power_cv_percent = None

    if average_power > 0:
        power_cv_percent = (
            power_std / average_power * 100
        )

    minimum_power = (
        ftp * MIN_AEROBIC_FTP_RATIO
    )

    maximum_power = (
        ftp * MAX_AEROBIC_FTP_RATIO
    )

    in_zone_seconds = sum(
        minimum_power <= power <= maximum_power
        for power in powers
    )

    above_zone_seconds = sum(
        power > maximum_power
        for power in powers
    )

    below_zone_seconds = sum(
        power < minimum_power
        for power in powers
    )

    duration = len(powers)

    return {
        "status": "ok",

        "duration_seconds": duration,

        "average_power": round(
            average_power, 2
        ),

        "average_power_ftp_percent": round(
            average_power / ftp * 100, 2
        ),

        "min_power": min(powers),

        "max_power": max(powers),

        "power_std": round(
            power_std, 2
        ),

        "power_cv_percent": (
            round(power_cv_percent, 2)
            if power_cv_percent is not None
            else None
        ),

        "in_zone_seconds": in_zone_seconds,

        "above_zone_seconds": (
            above_zone_seconds
        ),

        "below_zone_seconds": (
            below_zone_seconds
        ),

        "zone_coverage_ratio": round(
            in_zone_seconds / duration,
            4,
        ),

        "work_kj": round(
            sum(powers) / 1000, 2
        ),
    }


def evaluate_aerobic_candidate(
    records,
    ftp,
):
    """
    Проверяет пригодность аэробного участка.

    Первые 180 секунд исключаются
    из аналитического окна.
    """
    minimum_required_duration = (
        INITIAL_ADAPTATION_SECONDS
        + MIN_SEGMENT_SECONDS
    )

    result = {
        "status": "rejected",

        "candidate_duration_seconds": len(
            records
        ),

        "excluded_adaptation_seconds": 0,

        "reasons": [],
    }

    if len(records) < minimum_required_duration:
        return {
            **result,

            "reasons": [
                "insufficient_duration",
            ],
        }

    analysis_records = records[
        INITIAL_ADAPTATION_SECONDS:
    ]

    metrics = calculate_aerobic_power_metrics(
        records=analysis_records,
        ftp=ftp,
    )

    reasons = []

    cv = metrics["power_cv_percent"]

    if (
        cv is None
        or cv > MAX_POWER_CV_PERCENT
    ):
        reasons.append(
            "unstable_power"
        )

    if metrics["zone_coverage_ratio"] < (
        MIN_ZONE_COVERAGE_RATIO
    ):
        reasons.append(
            "insufficient_zone_coverage"
        )

    relative_power = (
        metrics["average_power_ftp_percent"]
        / 100
    )

    if not (
        MIN_AEROBIC_FTP_RATIO
        <= relative_power
        <= MAX_AEROBIC_FTP_RATIO
    ):
        reasons.append(
            "average_power_outside_zone"
        )

    return {
        **result,

        "status": (
            "rejected"
            if reasons
            else "accepted"
        ),

        "candidate_start": records[0][
            "timestamp"
        ].isoformat(),

        "candidate_end": records[-1][
            "timestamp"
        ].isoformat(),

        "analysis_start": analysis_records[0][
            "timestamp"
        ].isoformat(),

        "analysis_end": analysis_records[-1][
            "timestamp"
        ].isoformat(),

        "excluded_adaptation_seconds": (
            INITIAL_ADAPTATION_SECONDS
        ),

        "metrics": metrics,

        "suitable_for_power_hr_analysis_by_power": (
            not reasons
        ),

        "drift_candidate_by_power": (
            not reasons

            and metrics["duration_seconds"]
            >= MIN_DRIFT_CANDIDATE_SECONDS
        ),

        "reasons": reasons,
    }


def detect_aerobic_segments(
    records,
    ftp,
):
    """
    Обнаруживает стабильные аэробные
    участки велосипедной тренировки.

    Не использует ЧСС для выбора участков.

    Не требует, чтобы вся тренировка
    была классифицирована как endurance.
    """
    if (
        not is_valid_number(ftp)
        or ftp <= 0
    ):
        return {
            "status": "insufficient_data",

            "reason": "Некорректный FTP",

            "segments": [],

            "rejected_candidates": [],
        }

    continuous_segments = (
        prepare_aerobic_power_segments(
            records
        )
    )

    accepted_segments = []

    rejected_candidates = []

    candidates_count = 0

    for continuous_segment in continuous_segments:
        candidates = find_aerobic_candidates(
            records=continuous_segment,
            ftp=ftp,
        )

        for candidate in candidates:
            candidates_count += 1

            evaluated = evaluate_aerobic_candidate(
                records=candidate,
                ftp=ftp,
            )

            if evaluated["status"] == "accepted":
                accepted_segments.append({
                    "segment_id": (
                        f"aerobic_"
                        f"{len(accepted_segments) + 1}"
                    ),

                    **evaluated,
                })

            else:
                rejected_candidates.append(
                    evaluated
                )

    total_duration = sum(
        segment["metrics"]["duration_seconds"]
        for segment in accepted_segments
    )

    drift_candidates_count = sum(
        segment["drift_candidate_by_power"]
        for segment in accepted_segments
    )

    return {
        "status": (
            "ok"
            if accepted_segments
            else "no_aerobic_segments"
        ),

        "ftp": ftp,

        "power_range_watts": {
            "minimum": round(
                ftp * MIN_AEROBIC_FTP_RATIO,
                2,
            ),

            "maximum": round(
                ftp * MAX_AEROBIC_FTP_RATIO,
                2,
            ),
        },

        "segments": accepted_segments,

        "rejected_candidates": (
            rejected_candidates
        ),

        "statistics": {
            "continuous_power_segments": len(
                continuous_segments
            ),

            "detected_candidates": (
                candidates_count
            ),

            "accepted_segments": len(
                accepted_segments
            ),

            "rejected_candidates": len(
                rejected_candidates
            ),

            "total_aerobic_seconds": (
                total_duration
            ),

            "total_aerobic_minutes": round(
                total_duration / 60,
                2,
            ),

            "drift_candidates_count": (
                drift_candidates_count
            ),
        },

        "settings": {
            "minimum_ftp_ratio": (
                MIN_AEROBIC_FTP_RATIO
            ),

            "maximum_ftp_ratio": (
                MAX_AEROBIC_FTP_RATIO
            ),

            "minimum_segment_seconds": (
                MIN_SEGMENT_SECONDS
            ),

            "minimum_drift_seconds": (
                MIN_DRIFT_CANDIDATE_SECONDS
            ),

            "smoothing_window_seconds": (
                SMOOTHING_WINDOW_SECONDS
            ),

            "initial_adaptation_seconds": (
                INITIAL_ADAPTATION_SECONDS
            ),

            "maximum_power_cv_percent": (
                MAX_POWER_CV_PERCENT
            ),

            "minimum_zone_coverage_ratio": (
                MIN_ZONE_COVERAGE_RATIO
            ),

            "hard_break_ftp_ratio": (
                HARD_BREAK_FTP_RATIO
            ),
        },

        "limitations": [
            (
                "Аэробные участки определяются "
                "по мощности относительно FTP"
            ),
            (
                "Зона мощности не подтверждает "
                "физиологическое состояние спортсмена"
            ),
            (
                "ЧСС не используется "
                "для обнаружения участков"
            ),
            (
                "Исключение первых трёх минут "
                "не гарантирует стабилизацию ЧСС"
            ),
            (
                "Сглаживание мощности может "
                "смещать обнаруженные границы"
            ),
            (
                "Нестабильный кандидат отклоняется "
                "целиком без поиска более коротких "
                "стабильных участков внутри него"
            ),
            (
                "Пригодность для анализа дрейфа "
                "пока оценивается только по мощности"
            ),
        ],
    }