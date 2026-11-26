from datetime import timedelta
from statistics import mean, pstdev

from src.analytics.workout_effort_comparison import (
    get_valid_field,
    extract_record_window,
)

from src.analytics.workout_target_power import (
    get_valid_target_power,
)


MAX_TRANSIENT_SECONDS = 5

MAX_TRANSIENT_EXTRA_WORK_KJ = 1.0

MAX_TRANSIENT_MISSING_WORK_KJ = 1.0

MAX_TRANSIENT_FTP_RATIO = 1.50

CONTEXT_SECONDS = 30

MAX_CONTEXT_CV_PERCENT = 15

MAX_CONTEXT_TARGET_DIFFERENCE_RATIO = 0.10

MIN_AEROBIC_FTP_RATIO = 0.56

MAX_AEROBIC_FTP_RATIO = 0.75


def group_consecutive_timestamps(timestamps):
    """
    Объединяет соседние временные отметки
    в непрерывные события.
    """
    groups = []
    current = []

    for timestamp in sorted(set(timestamps)):
        if current:
            difference = timestamp - current[-1]

            if difference != timedelta(seconds=1):
                groups.append(current)
                current = []

        current.append(timestamp)

    if current:
        groups.append(current)

    return groups


def assess_transient_context(
    records,
    target_power,
):
    """
    Проверяет стабильность мощности
    до или после отклонения.
    """
    if len(records) != CONTEXT_SECONDS:
        return False

    if any(record is None for record in records):
        return False

    powers = [
        get_valid_field(record, "power")
        for record in records
    ]

    if any(
        power is None or power <= 0
        for power in powers
    ):
        return False

    targets = [
        get_valid_target_power(record)
        for record in records
    ]

    if any(
        target != target_power
        for target in targets
    ):
        return False

    average_power = mean(powers)

    cv = pstdev(powers) / average_power * 100

    target_difference = (
        abs(average_power - target_power)
        / target_power
    )

    return (
        cv <= MAX_CONTEXT_CV_PERCENT

        and target_difference
        <= MAX_CONTEXT_TARGET_DIFFERENCE_RATIO
    )


def assess_transient_event(
    timestamps,
    indexed_records,
    ftp,
):
    """
    Проверяет возможность сохранения
    аэробного сегмента через краткое
    отклонение мощности.

    Не использует ЧСС.
    """
    result = {
        "eligible": False,
        "duration_seconds": len(timestamps),
        "start": None,
        "end": None,
        "target_power": None,
        "peak_power": None,
        "additional_work_kj": None,
        "missing_work_kj": None,
        "reasons": [],
    }

    if not timestamps:
        result["reasons"].append(
            "empty_event"
        )

        return result

    start = timestamps[0]
    end = timestamps[-1]

    result["start"] = start.isoformat()
    result["end"] = end.isoformat()

    if len(timestamps) > MAX_TRANSIENT_SECONDS:
        result["reasons"].append(
            "event_too_long"
        )

        return result

    if (
        end - start
    ).total_seconds() + 1 != len(timestamps):
        result["reasons"].append(
            "noncontinuous_event"
        )

        return result

    records = [
        indexed_records.get(timestamp)
        for timestamp in timestamps
    ]

    if any(record is None for record in records):
        result["reasons"].append(
            "missing_records"
        )

        return result

    powers = [
        get_valid_field(record, "power")
        for record in records
    ]

    if any(
        power is None or power <= 0
        for power in powers
    ):
        result["reasons"].append(
            "zero_or_missing_power"
        )

        return result

    targets = [
        get_valid_target_power(record)
        for record in records
    ]

    target = targets[0]

    if (
        target is None
        or target <= 0
        or any(value != target for value in targets)
    ):
        result["reasons"].append(
            "inconsistent_target"
        )

        return result

    result["target_power"] = target

    if not (
        ftp * MIN_AEROBIC_FTP_RATIO
        <= target
        <= ftp * MAX_AEROBIC_FTP_RATIO
    ):
        result["reasons"].append(
            "target_outside_aerobic_zone"
        )

        return result

    peak_power = max(powers)

    result["peak_power"] = peak_power

    additional_work = sum(
        max(0, power - target)
        for power in powers
    ) / 1000

    missing_work = sum(
        max(0, target - power)
        for power in powers
    ) / 1000

    result["additional_work_kj"] = round(
        additional_work,
        3,
    )

    result["missing_work_kj"] = round(
        missing_work,
        3,
    )

    reasons = []

    if peak_power > ftp * MAX_TRANSIENT_FTP_RATIO:
        reasons.append(
            "excessive_peak_power"
        )

    if additional_work > MAX_TRANSIENT_EXTRA_WORK_KJ:
        reasons.append(
            "excessive_additional_work"
        )

    if missing_work > MAX_TRANSIENT_MISSING_WORK_KJ:
        reasons.append(
            "excessive_missing_work"
        )

    before = extract_record_window(
        indexed_records=indexed_records,
        start=start - timedelta(
            seconds=CONTEXT_SECONDS
        ),
        duration_seconds=CONTEXT_SECONDS,
    )

    after = extract_record_window(
        indexed_records=indexed_records,
        start=end + timedelta(seconds=1),
        duration_seconds=CONTEXT_SECONDS,
    )

    if not assess_transient_context(
        before,
        target,
    ):
        reasons.append(
            "unstable_context_before"
        )

    if not assess_transient_context(
        after,
        target,
    ):
        reasons.append(
            "unstable_context_after"
        )

    result["reasons"] = reasons

    result["eligible"] = not reasons

    return result


def resolve_transient_power_events(
    indexed_records,
    split_timestamps,
    ftp,
):
    """
    Проверяет события, которые могли бы
    разделить аэробную нагрузку.

    Пересекающиеся причины разделения
    рассматриваются как единое событие.
    """
    reviewed_timestamps = set(
        split_timestamps
    )

    for timestamp, record in indexed_records.items():
        power = get_valid_field(
            record,
            "power",
        )

        if (
            power is not None
            and power > ftp * 1.05
        ):
            reviewed_timestamps.add(
                timestamp
            )

    groups = group_consecutive_timestamps(
        reviewed_timestamps
    )

    accepted_timestamps = set()

    assessments = []

    for group in groups:
        assessment = assess_transient_event(
            timestamps=group,
            indexed_records=indexed_records,
            ftp=ftp,
        )

        assessments.append(
            assessment
        )

        if assessment["eligible"]:
            accepted_timestamps.update(
                group
            )

    return {
        "accepted_timestamps": (
            accepted_timestamps
        ),

        "remaining_split_timestamps": (
            reviewed_timestamps
            - accepted_timestamps
        ),

        "assessments": assessments,

        "statistics": {
            "reviewed_events_count": len(groups),

            "accepted_events_count": sum(
                assessment["eligible"]
                for assessment in assessments
            ),

            "accepted_seconds": len(
                accepted_timestamps
            ),
        },
    }