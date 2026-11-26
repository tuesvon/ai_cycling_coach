from collections import Counter, deque
from datetime import timedelta
from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    get_valid_field,
)

from src.analytics.workout_target_power import (
    get_valid_target_power,
)

from src.analytics.workout_power_event_integration import (
    analyze_integrated_power_events,
)

from src.analytics.aerobic_segment_detection import (
    calculate_aerobic_power_metrics,
)

from src.analytics.aerobic_transient_events import (
    resolve_transient_power_events,
)


MIN_AEROBIC_FTP_RATIO = 0.56
MAX_AEROBIC_FTP_RATIO = 0.75

MIN_SEGMENT_SECONDS = 600
MIN_DRIFT_CANDIDATE_SECONDS = 1200

INITIAL_ADAPTATION_SECONDS = 180

SMOOTHING_WINDOW_SECONDS = 30

MAX_POWER_CV_PERCENT = 10
MIN_ZONE_COVERAGE_RATIO = 0.80

MAX_BRIDGE_RATIO = 0.02

HARD_BREAK_FTP_RATIO = 1.05

MAX_SIGNIFICANT_DEVIATION_SECONDS = 3


def is_aerobic_power(power, ftp):
    """
    Проверяет принадлежность мощности
    к выбранному аэробному диапазону.
    """
    if not is_valid_number(power):
        return False

    return (
        ftp * MIN_AEROBIC_FTP_RATIO
        <= power
        <= ftp * MAX_AEROBIC_FTP_RATIO
    )


def build_event_timestamp_sets(
    integrated_events,
    indexed_records,
    ftp=None,
):
    """
    Формирует временные отметки разделения,
    допустимых пауз и кратких отклонений.

    Учитывает переходы на новую
    аэробную целевую мощность.
    """
    split_timestamps = set()
    bridge_timestamps = set()

    target_consistent_surge_timestamps = set()

    availability = (
        integrated_events.get(
            "target_availability"
        ) or {}
    )

    target_available = (
        ftp is not None

        and availability.get(
            "usable_for_target_analysis"
        ) is True
    )

    for event in integrated_events.get(
        "events", []
    ):
        raw_type = event.get(
            "raw_event_type"
        )

        if raw_type == "time_gap":
            continue

        duration = event.get(
            "duration_seconds"
        )

        if duration is None:
            continue

        action = event[
            "integrated_handling"
        ]["aerobic_segment_action"]

        start = parse_activity_date(
            event["start"]
        )

        timestamps = {
            start + timedelta(seconds=offset)

            for offset in range(duration)

            if start + timedelta(seconds=offset)
            in indexed_records
        }

        if action == "split":

            # Универсальный детектор может
            # классифицировать переход на новую
            # постоянную мощность как ускорение.
            #
            # При наличии аэробной цели проверяем
            # фактическое соответствие заданию.

            if (
                raw_type == "surge"
                and target_available
            ):
                for timestamp in timestamps:

                    record = indexed_records[
                        timestamp
                    ]

                    power = get_valid_field(
                        record,
                        "power",
                    )

                    target = get_valid_target_power(
                        record
                    )

                    consistent_with_target = (
                        target is not None

                        and target > 0

                        and power is not None

                        and power > 0

                        and is_aerobic_power(
                            target,
                            ftp,
                        )

                        and is_aerobic_power(
                            power,
                            ftp,
                        )

                        and abs(power - target)
                        <= target * 0.10
                    )

                    if consistent_with_target:
                        target_consistent_surge_timestamps.add(
                            timestamp
                        )

                    else:
                        split_timestamps.add(
                            timestamp
                        )

            else:
                split_timestamps.update(
                    timestamps
                )

        elif action == "bridge_candidate":
            bridge_timestamps.update(
                timestamps
            )

    # Независимо проверяем существенные
    # отклонения от целевой мощности.
    #
    # Они сохраняют право разделить сегмент.

    for event in integrated_events.get(
        "target_deviation_events", []
    ):
        event_type = event.get(
            "event_type"
        )

        duration = event.get(
            "duration_seconds", 0
        )

        should_split = (
            event_type == "missing_actual_power"

            or (
                event_type in {
                    "significantly_above_target",
                    "significantly_below_target",
                }

                and duration
                > MAX_SIGNIFICANT_DEVIATION_SECONDS
            )
        )

        if not should_split:
            continue

        start = parse_activity_date(
            event["start"]
        )

        split_timestamps.update(
            start + timedelta(seconds=offset)

            for offset in range(duration)

            if start + timedelta(seconds=offset)
            in indexed_records
        )

    transient_timestamps = set()

    transient_statistics = {
        "reviewed_events_count": 0,
        "accepted_events_count": 0,
        "accepted_seconds": 0,
    }

    if target_available:
        transient_result = (
            resolve_transient_power_events(
                indexed_records=indexed_records,

                split_timestamps=split_timestamps,

                ftp=ftp,
            )
        )

        transient_timestamps = (
            transient_result[
                "accepted_timestamps"
            ]
        )

        split_timestamps = (
            transient_result[
                "remaining_split_timestamps"
            ]
        )

        transient_statistics = (
            transient_result["statistics"]
        )

    bridge_timestamps.difference_update(
        split_timestamps
    )

    target_consistent_surge_timestamps.difference_update(
        split_timestamps
    )

    return {
        "split_timestamps": split_timestamps,

        "bridge_timestamps": bridge_timestamps,

        "transient_timestamps": transient_timestamps,

        "transient_statistics": transient_statistics,

        "target_consistent_surge_timestamps": (
            target_consistent_surge_timestamps
        ),

        "target_consistent_surge_seconds": len(
            target_consistent_surge_timestamps
        ),
    }


def get_aerobic_detection_context(
    record,
    ftp,
    target_available,
):
    """
    Определяет способ отбора
    аэробного участка.

    Положительная цель используется
    только при доступной целевой
    структуре тренировки.
    """
    target = get_valid_target_power(
        record
    )

    if (
        target_available
        and target is not None
        and target > 0
    ):
        return {
            "method": "target_based",

            "target_power": target,

            "target_in_aerobic_zone": (
                is_aerobic_power(
                    target,
                    ftp,
                )
            ),
        }

    return {
        "method": "power_based",

        "target_power": None,

        "target_in_aerobic_zone": None,
    }


def find_aerobic_candidates_v2(
    indexed_records,
    ftp,
    event_timestamp_sets,
    target_available,
):
    """
    Выделяет аэробные кандидаты
    с учётом проверенных отклонений.
    """
    split_timestamps = event_timestamp_sets[
        "split_timestamps"
    ]

    bridge_timestamps = event_timestamp_sets[
        "bridge_timestamps"
    ]

    transient_timestamps = event_timestamp_sets.get(
        "transient_timestamps", set()
    )

    candidates = []
    current = []

    rolling_power = deque(
        maxlen=SMOOTHING_WINDOW_SECONDS
    )

    previous_timestamp = None
    previous_context = None

    def close_candidate():
        nonlocal current

        if current:
            candidates.append({
                "records": current,

                "method": current[0][
                    "detection_method"
                ],

                "target_power": current[0][
                    "segment_target_power"
                ],
            })

        current = []

    for timestamp in sorted(indexed_records):
        record = indexed_records[timestamp]

        power = get_valid_field(
            record,
            "power",
        )

        context = get_aerobic_detection_context(
            record=record,
            ftp=ftp,
            target_available=target_available,
        )

        time_gap = (
            previous_timestamp is not None

            and timestamp - previous_timestamp
            != timedelta(seconds=1)
        )

        context_changed = (
            previous_context is not None

            and (
                context["method"]
                != previous_context["method"]

                or context["target_power"]
                != previous_context["target_power"]
            )
        )

        if time_gap or context_changed:
            close_candidate()
            rolling_power.clear()

        previous_timestamp = timestamp
        previous_context = context

        transient = (
            timestamp in transient_timestamps
        )

        hard_break = (
            power is None

            or timestamp in split_timestamps

            or (
                power is not None

                and power > ftp * HARD_BREAK_FTP_RATIO

                and not transient
            )
        )

        if hard_break:
            close_candidate()
            rolling_power.clear()

            continue

        bridge = (
            timestamp in bridge_timestamps
            and power == 0
        )

        if power == 0 and not bridge:
            close_candidate()
            rolling_power.clear()

            continue

        method = context["method"]

        if method == "target_based":
            eligible = context[
                "target_in_aerobic_zone"
            ]

        else:
            rolling_power.append(power)

            eligible = (
                len(rolling_power)
                == SMOOTHING_WINDOW_SECONDS

                and is_aerobic_power(
                    mean(rolling_power),
                    ftp,
                )
            )

        if bridge:
            eligible = bool(current) and (
                method == "power_based"

                or context[
                    "target_in_aerobic_zone"
                ]
            )

        if not eligible:
            close_candidate()

            continue

        current.append({
            **record,

            "timestamp": timestamp,

            "power": power,

            "detection_method": method,

            "segment_target_power": context[
                "target_power"
            ],

            "accepted_bridge_second": bridge,

            "accepted_transient_second": transient,
        })

    close_candidate()

    return candidates


def evaluate_aerobic_candidate_v2(
    candidate,
    ftp,
):
    """
    Проверяет фактическую стабильность
    аэробного кандидата.
    """
    records = candidate["records"]
    duration = len(records)

    result = {
        "status": "rejected",

        "detection_method": candidate["method"],

        "target_power": candidate["target_power"],

        "candidate_start": records[0][
            "timestamp"
        ].isoformat(),

        "candidate_end": records[-1][
            "timestamp"
        ].isoformat(),

        "candidate_duration_seconds": duration,

        "excluded_adaptation_seconds": 0,

        "analysis_start": None,
        "analysis_end": None,

        "metrics": None,

        "bridge_seconds": 0,
        "bridge_ratio": None,

        "transient_seconds": 0,
        "transient_ratio": None,

        "transient_timestamps": [],

        "combined_interruption_ratio": None,

        "suitable_for_power_hr_analysis_by_power": False,

        "drift_candidate_by_power": False,

        "reasons": [],
    }

    minimum_duration = (
        INITIAL_ADAPTATION_SECONDS
        + MIN_SEGMENT_SECONDS
    )

    if duration < minimum_duration:
        result["reasons"].append(
            "insufficient_duration"
        )

        return result

    analysis_records = records[
        INITIAL_ADAPTATION_SECONDS:
    ]

    metrics = calculate_aerobic_power_metrics(
        analysis_records,
        ftp,
    )

    analysis_duration = len(
        analysis_records
    )

    bridge_seconds = sum(
        record.get(
            "accepted_bridge_second",
            False,
        )

        for record in analysis_records
    )

    transient_records = [
        record

        for record in analysis_records

        if record.get(
            "accepted_transient_second",
            False,
        )
    ]

    transient_seconds = len(
        transient_records
    )

    bridge_ratio = (
        bridge_seconds / analysis_duration
    )

    transient_ratio = (
        transient_seconds / analysis_duration
    )

    combined_ratio = sum(
        bool(
            record.get(
                "accepted_bridge_second",
                False,
            )

            or record.get(
                "accepted_transient_second",
                False,
            )
        )

        for record in analysis_records
    ) / analysis_duration

    reasons = []

    power_cv = metrics.get(
        "power_cv_percent"
    )

    if (
        power_cv is None

        or power_cv > MAX_POWER_CV_PERCENT
    ):
        reasons.append(
            "unstable_power"
        )

    if metrics.get(
        "zone_coverage_ratio", 0
    ) < MIN_ZONE_COVERAGE_RATIO:
        reasons.append(
            "insufficient_zone_coverage"
        )

    average_power = mean(
        record["power"]
        for record in analysis_records
    )

    if not is_aerobic_power(
        average_power,
        ftp,
    ):
        reasons.append(
            "average_power_outside_zone"
        )

    if bridge_ratio > MAX_BRIDGE_RATIO:
        reasons.append(
            "excessive_bridge_duration"
        )

    if transient_ratio > MAX_BRIDGE_RATIO:
        reasons.append(
            "excessive_transient_duration"
        )

    if combined_ratio > MAX_BRIDGE_RATIO:
        reasons.append(
            "excessive_combined_interruptions"
        )

    accepted = not reasons

    return {
        **result,

        "status": (
            "accepted"
            if accepted
            else "rejected"
        ),

        "excluded_adaptation_seconds": (
            INITIAL_ADAPTATION_SECONDS
        ),

        "analysis_start": analysis_records[0][
            "timestamp"
        ].isoformat(),

        "analysis_end": analysis_records[-1][
            "timestamp"
        ].isoformat(),

        "metrics": metrics,

        "bridge_seconds": bridge_seconds,

        "bridge_ratio": round(
            bridge_ratio,
            4,
        ),

        "transient_seconds": transient_seconds,

        "transient_ratio": round(
            transient_ratio,
            4,
        ),

        "transient_timestamps": [
            record["timestamp"].isoformat()
            for record in transient_records
        ],

        "combined_interruption_ratio": round(
            combined_ratio,
            4,
        ),

        "suitable_for_power_hr_analysis_by_power": (
            accepted
        ),

        "drift_candidate_by_power": (
            accepted

            and analysis_duration
            >= MIN_DRIFT_CANDIDATE_SECONDS
        ),

        "reasons": reasons,
    }


def detect_aerobic_segments_v2(
    records,
    ftp,
    riding_mode="unknown",
    ignore_power=False,
    ignore_heart_rate=False,
):
    """
    Обнаруживает аэробные сегменты
    с учётом целевой мощности,
    пауз и кратковременных отклонений.
    """
    if not isinstance(ignore_power, bool):
        raise ValueError(
            "ignore_power должен быть bool"
        )

    if not isinstance(ignore_heart_rate, bool):
        raise ValueError(
            "ignore_heart_rate должен быть bool"
        )

    result = {
        "status": "insufficient_data",

        "ftp": ftp,

        "segments": [],

        "rejected_candidates": [],

        "statistics": {
            "indexed_records_count": 0,

            "detected_candidates": 0,

            "accepted_segments": 0,

            "rejected_candidates": 0,

            "total_aerobic_seconds": 0,

            "total_aerobic_minutes": 0,

            "drift_candidates_count": 0,

            "accepted_bridge_seconds": 0,

            "accepted_transient_seconds": 0,

            "detection_method_counts": {},
        },

        "target_availability": None,

        "event_statistics": None,

        "transient_statistics": None,

        "fitness_change": None,
    }

    if ignore_power:
        return {
            **result,
            "status": "power_ignored",
        }

    if (
        not is_valid_number(ftp)
        or ftp <= 0
    ):
        return {
            **result,

            "reason": "invalid_or_missing_ftp",
        }

    indexed_records = prepare_effort_records(
        records
    )

    if not indexed_records:
        return result

    integrated = analyze_integrated_power_events(
        records=records,

        ftp=ftp,

        riding_mode=riding_mode,

        ignore_heart_rate=ignore_heart_rate,
    )

    if integrated["status"] != "ok":
        return {
            **result,

            "reason": "event_analysis_unavailable",
        }

    availability = integrated[
        "target_availability"
    ]

    target_available = (
        availability is not None

        and availability.get(
            "usable_for_target_analysis"
        ) is True
    )

    event_timestamp_sets = build_event_timestamp_sets(
        integrated_events=integrated,

        indexed_records=indexed_records,

        ftp=ftp,
    )

    candidates = find_aerobic_candidates_v2(
        indexed_records=indexed_records,

        ftp=ftp,

        event_timestamp_sets=event_timestamp_sets,

        target_available=target_available,
    )

    segments = []
    rejected = []

    for candidate in candidates:
        evaluated = evaluate_aerobic_candidate_v2(
            candidate=candidate,

            ftp=ftp,
        )

        if evaluated["status"] == "accepted":
            segments.append({
                "segment_id": (
                    f"aerobic_{len(segments) + 1}"
                ),

                **evaluated,
            })

        else:
            rejected.append(
                evaluated
            )

    total_seconds = sum(
        segment["metrics"]["duration_seconds"]

        for segment in segments
    )

    method_counts = Counter(
        segment["detection_method"]

        for segment in segments
    )

    return {
        **result,

        "status": (
            "ok"

            if segments

            else "no_aerobic_segments"
        ),

        "segments": segments,

        "rejected_candidates": rejected,

        "target_availability": availability,

        "event_statistics": integrated[
            "statistics"
        ],

        "transient_statistics": (
            event_timestamp_sets[
                "transient_statistics"
            ]
        ),

        "statistics": {
            "indexed_records_count": len(
                indexed_records
            ),

            "detected_candidates": len(
                candidates
            ),

            "accepted_segments": len(
                segments
            ),

            "rejected_candidates": len(
                rejected
            ),

            "total_aerobic_seconds": total_seconds,

            "total_aerobic_minutes": round(
                total_seconds / 60,
                2,
            ),

            "drift_candidates_count": sum(
                segment["drift_candidate_by_power"]

                for segment in segments
            ),

            "accepted_bridge_seconds": sum(
                segment["bridge_seconds"]

                for segment in segments
            ),

            "accepted_transient_seconds": sum(
                segment["transient_seconds"]

                for segment in segments
            ),

            "detection_method_counts": dict(
                method_counts
            ),
        },

        "settings": {
            "minimum_aerobic_ftp_ratio": (
                MIN_AEROBIC_FTP_RATIO
            ),

            "maximum_aerobic_ftp_ratio": (
                MAX_AEROBIC_FTP_RATIO
            ),

            "minimum_segment_seconds": (
                MIN_SEGMENT_SECONDS
            ),

            "minimum_drift_candidate_seconds": (
                MIN_DRIFT_CANDIDATE_SECONDS
            ),

            "initial_adaptation_seconds": (
                INITIAL_ADAPTATION_SECONDS
            ),

            "maximum_bridge_ratio": (
                MAX_BRIDGE_RATIO
            ),

            "maximum_combined_interruption_ratio": (
                MAX_BRIDGE_RATIO
            ),

            "maximum_power_cv_percent": (
                MAX_POWER_CV_PERCENT
            ),

            "minimum_zone_coverage_ratio": (
                MIN_ZONE_COVERAGE_RATIO
            ),
        },

        "limitations": [
            (
                "Целевая мощность не заменяет "
                "фактические измерения"
            ),
            (
                "ЧСС не используется "
                "для отбора сегментов"
            ),
            (
                "Допустимые паузы и отклонения "
                "сохраняются в исходном виде"
            ),
            (
                "Кратковременное отклонение "
                "не считается автоматически "
                "ошибкой измерения"
            ),
            (
                "Разрывы FIT не объединяются"
            ),
            (
                "Кандидат на анализ дрейфа "
                "требует физиологической проверки"
            ),
            (
                "Допустимые отклонения проверяются "
                "при постоянной аэробной цели"
            ),
            (
                "Ramp пока не анализируется "
                "как единый аэробный блок"
            ),
            (
                "Нестабильный кандидат "
                "отклоняется целиком"
            ),
        ],
    }