from collections import Counter
from datetime import timedelta
from statistics import mean, pstdev

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    extract_record_window,
    get_valid_field,
)

from src.analytics.workout_power_events import (
    detect_power_events,
)

from src.analytics.workout_target_power import (
    assess_target_power_availability,
    get_valid_target_power,
    calculate_target_execution_metrics,
    detect_target_deviation_events,
)


CONTEXT_SECONDS = 30

MAX_BRIDGE_SECONDS = 5

MAX_CONTEXT_POWER_CV_PERCENT = 10

MAX_CONTEXT_POWER_DIFFERENCE_RATIO = 0.05

MAX_SHORT_SURGE_SECONDS = 3


def get_event_windows(indexed_records, event):
    """
    Возвращает окна до события,
    внутри события и после него.
    """
    duration = event.get("duration_seconds")

    if duration is None or duration <= 0:
        return None

    start = parse_activity_date(
        event["start"]
    )

    end = parse_activity_date(
        event["end"]
    )

    before = extract_record_window(
        indexed_records=indexed_records,
        start=start - timedelta(
            seconds=CONTEXT_SECONDS
        ),
        duration_seconds=CONTEXT_SECONDS,
    )

    during = extract_record_window(
        indexed_records=indexed_records,
        start=start,
        duration_seconds=duration,
    )

    after = extract_record_window(
        indexed_records=indexed_records,
        start=end + timedelta(seconds=1),
        duration_seconds=CONTEXT_SECONDS,
    )

    return {
        "before": before,
        "during": during,
        "after": after,
    }


def calculate_context_power_metrics(window):
    """
    Оценивает стабильность фактической
    мощности в проверяемом окне.
    """
    powers = [
        get_valid_field(record, "power")
        for record in window
    ]

    valid = [
        power
        for power in powers
        if power is not None
    ]

    complete = (
        len(valid) == len(window)
        and bool(window)
    )

    average_power = (
        mean(valid)
        if valid
        else None
    )

    cv = None

    if (
        average_power is not None
        and average_power > 0
    ):
        cv = (
            pstdev(valid)
            / average_power
            * 100
        )

    all_positive = (
        complete
        and all(power > 0 for power in valid)
    )

    stable = (
        all_positive
        and cv is not None
        and cv <= MAX_CONTEXT_POWER_CV_PERCENT
    )

    return {
        "expected_seconds": len(window),

        "valid_power_seconds": len(valid),

        "complete_power": complete,

        "all_power_positive": all_positive,

        "average_power": average_power,

        "power_cv_percent": cv,

        "stable": stable,
    }


def assess_event_target_context(
    windows,
    target_availability,
):
    """
    Анализирует записанную цель
    до события, во время и после него.

    Не определяет намерения спортсмена.
    """
    if windows is None:
        return {
            "status": "unavailable",

            "stable_positive_target": False,

            "target_power": None,

            "target_changed": None,

            "bridge_compatible": False,
        }

    records = (
        windows["before"]
        + windows["during"]
        + windows["after"]
    )

    targets = [
        get_valid_target_power(record)
        for record in records
    ]

    positive = [
        value
        for value in targets
        if value is not None and value > 0
    ]

    unique_positive = sorted(
        set(positive)
    )

    complete_positive = (
        bool(records)
        and len(positive) == len(records)
    )

    stable_positive = (
        complete_positive
        and len(unique_positive) == 1
    )

    globally_available = (
        target_availability.get(
            "usable_for_target_analysis"
        ) is True
    )

    if stable_positive:
        status = "stable_positive_target"

    elif len(unique_positive) > 1:
        status = "target_change"

    elif positive:
        status = "incomplete_positive_target"

    else:
        status = "target_unavailable"

    # Если цель доступна на уровне
    # тренировки, не разрешаем объединение
    # через участок с неизвестной целью.
    #
    # Если цели действительно нет,
    # допускаем проверку по мощности.

    bridge_compatible = (
        stable_positive
        or (
            not globally_available
            and not positive
        )
    )

    during = [
        record
        for record in windows["during"]
        if record is not None
    ]

    execution = (
        calculate_target_execution_metrics(
            during
        )
        if during
        else None
    )

    return {
        "status": status,

        "global_target_status": (
            target_availability.get("status")
        ),

        "stable_positive_target": (
            stable_positive
        ),

        "target_power": (
            unique_positive[0]
            if stable_positive
            else None
        ),

        "positive_target_values": (
            unique_positive
        ),

        "target_changed": (
            len(unique_positive) > 1
            if positive
            else None
        ),

        "bridge_compatible": (
            bridge_compatible
        ),

        "event_execution": execution,
    }


def assess_coasting_bridge(
    event,
    windows,
    target_context,
):
    """
    Проверяет возможность сохранения
    непрерывности нагрузки через
    кратковременную нулевую мощность.

    ЧСС не используется для принятия
    решения об объединении.
    """
    result = {
        "eligible": False,

        "reasons": [],

        "before_power": None,

        "after_power": None,

        "power_difference_percent": None,

        "coasting_seconds": (
            event.get("duration_seconds")
        ),
    }

    if event.get("raw_event_type") != "zero_power":
        result["reasons"].append(
            "not_zero_power_event"
        )

        return result

    duration = event.get(
        "duration_seconds"
    )

    if (
        duration is None
        or duration <= 0
        or duration > MAX_BRIDGE_SECONDS
    ):
        result["reasons"].append(
            "coasting_too_long"
        )

        return result

    if windows is None:
        result["reasons"].append(
            "missing_event_context"
        )

        return result

    all_records = (
        windows["before"]
        + windows["during"]
        + windows["after"]
    )

    if any(
        record is None
        for record in all_records
    ):
        result["reasons"].append(
            "incomplete_time_context"
        )

    during_powers = [
        get_valid_field(record, "power")
        for record in windows["during"]
    ]

    if not all(
        power == 0
        for power in during_powers
    ):
        result["reasons"].append(
            "nonzero_or_missing_event_power"
        )

    cadences = [
        get_valid_field(record, "cadence")
        for record in windows["during"]
    ]

    if any(
        cadence is None
        for cadence in cadences
    ):
        result["reasons"].append(
            "missing_event_cadence"
        )

    elif any(
        cadence != 0
        for cadence in cadences
    ):
        result["reasons"].append(
            "nonzero_event_cadence"
        )

    before = calculate_context_power_metrics(
        windows["before"]
    )

    after = calculate_context_power_metrics(
        windows["after"]
    )

    result["before_power"] = before
    result["after_power"] = after

    if not before["stable"]:
        result["reasons"].append(
            "unstable_power_before_event"
        )

    if not after["stable"]:
        result["reasons"].append(
            "unstable_power_after_event"
        )

    before_power = before["average_power"]
    after_power = after["average_power"]

    if (
        before_power is not None
        and before_power > 0
        and after_power is not None
        and after_power > 0
    ):
        difference = (
            abs(after_power - before_power)
            / before_power
        )

        result["power_difference_percent"] = (
            round(difference * 100, 2)
        )

        if (
            difference
            > MAX_CONTEXT_POWER_DIFFERENCE_RATIO
        ):
            result["reasons"].append(
                "different_power_after_event"
            )

    else:
        result["reasons"].append(
            "insufficient_context_power"
        )

    if not target_context["bridge_compatible"]:
        result["reasons"].append(
            "incompatible_target_context"
        )

    result["eligible"] = (
        not result["reasons"]
    )

    return result


def get_integrated_event_action(
    event,
    bridge_assessment,
):
    """
    Определяет предварительное действие
    для аэробного детектора.

    Границы событий и решения
    не зависят от ЧСС.
    """
    raw_type = event.get(
        "raw_event_type"
    )

    duration = event.get(
        "duration_seconds"
    )

    if raw_type in {
        "time_gap",
        "power_data_gap",
    }:
        return "split"

    if raw_type == "zero_power":
        if bridge_assessment["eligible"]:
            return "bridge_candidate"

        return "split"

    if raw_type == "surge":
        if (
            duration is not None
            and duration <= MAX_SHORT_SURGE_SECONDS
        ):
            return "review_short_surge"

        return "split"

    return "review"


def integrate_power_event(
    event,
    indexed_records,
    target_availability,
):
    """
    Дополняет исходное событие
    информацией о целевой мощности
    и возможности сохранения сегмента.
    """
    # Не создаём посекундные окна
    # для потенциально больших разрывов FIT.

    if event["raw_event_type"] == "time_gap":
        windows = None

    else:
        windows = get_event_windows(
            indexed_records,
            event,
        )

    target_context = (
        assess_event_target_context(
            windows=windows,

            target_availability=(
                target_availability
            ),
        )
    )

    bridge = assess_coasting_bridge(
        event=event,

        windows=windows,

        target_context=target_context,
    )

    action = get_integrated_event_action(
        event=event,

        bridge_assessment=bridge,
    )

    return {
        **event,

        "target_context": target_context,

        "bridge_assessment": bridge,

        "integrated_handling": {
            "aerobic_segment_action": action,

            "preserve_raw_records": True,

            "interpolate_missing_data": False,

            "heart_rate_used_for_decision": False,
        },
    }


def analyze_integrated_power_events(
    records,
    ftp=None,
    riding_mode="unknown",
    ignore_power=False,
    ignore_heart_rate=False,
):
    """
    Объединяет фактические отклонения
    и контекст записанной цели.

    Отклонения от цели сохраняются
    отдельным аналитическим слоем.

    Исходные записи не изменяются.
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

        "events": [],

        "target_deviation_events": [],

        "target_availability": None,

        "statistics": {
            "power_events_count": 0,

            "target_deviation_events_count": 0,

            "bridge_candidates_count": 0,

            "action_counts": {},
        },

        "fitness_change": None,
    }

    if ignore_power:
        return {
            **result,

            "status": "power_ignored",
        }

    power_result = detect_power_events(
        records=records,

        ftp=ftp,

        riding_mode=riding_mode,

        ignore_heart_rate=ignore_heart_rate,
    )

    if power_result["status"] != "ok":
        return result

    availability = (
        assess_target_power_availability(
            records
        )
    )

    prepared = []

    for record in records:
        if not isinstance(record, dict):
            continue

        copied = dict(record)

        if ignore_heart_rate:
            copied.pop("heart_rate", None)

        prepared.append(copied)

    indexed_records = prepare_effort_records(
        prepared
    )

    events = [
        integrate_power_event(
            event=event,

            indexed_records=indexed_records,

            target_availability=availability,
        )

        for event in power_result["events"]
    ]

    target_deviations = []

    if availability[
        "usable_for_target_analysis"
    ]:
        target_deviations = (
            detect_target_deviation_events(
                prepared
            )
        )

    action_counts = Counter(
        event["integrated_handling"][
            "aerobic_segment_action"
        ]

        for event in events
    )

    return {
        **result,

        "status": "ok",

        "ftp": ftp,

        "riding_mode": power_result[
            "riding_mode"
        ],

        "ignore_heart_rate": (
            ignore_heart_rate
        ),

        "events": events,

        "target_deviation_events": (
            target_deviations
        ),

        "target_availability": availability,

        "statistics": {
            "power_events_count": len(events),

            "target_deviation_events_count": (
                len(target_deviations)
            ),

            "bridge_candidates_count": (
                action_counts["bridge_candidate"]
            ),

            "action_counts": dict(
                action_counts
            ),
        },

        "limitations": [
            (
                "События мощности и отклонения "
                "от цели могут пересекаться"
            ),
            (
                "Количество событий двух типов "
                "нельзя суммировать как количество "
                "уникальных отклонений"
            ),
            (
                "Bridge candidate ещё не означает "
                "фактическое объединение сегментов"
            ),
            (
                "Не проверяется суммарная доля "
                "прерываний внутри аэробного сегмента"
            ),
            (
                "Короткие скачки мощности "
                "требуют дополнительной проверки"
            ),
            (
                "Целевая мощность не доказывает "
                "использование ERG"
            ),
            (
                "ЧСС не определяет допустимость "
                "объединения участков"
            ),
        ],
    }