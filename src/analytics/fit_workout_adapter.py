from datetime import datetime, timezone
from math import isfinite

from src.analytics.fit_metrics import read_fit_file


MIN_ANALYSIS_RECORDS = 1200
MIN_ONE_SECOND_RATIO = 0.99
MIN_VALID_RECORDS_RATIO = 0.99
MIN_TIME_COVERAGE_RATIO = 0.99


def is_valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def prepare_fit_records(
    records,
    max_gap_seconds=2,
):
    """
    Подготавливает FIT-записи для анализа.

    Отдельно оценивает пригодность данных для:
    - сравнения пульса при одинаковой мощности;
    - анализа, требующего непрерывной записи.

    Разделяет записи на непрерывные сегменты.
    Не восстанавливает отсутствующие значения.
    """
    if not isinstance(records, list):
        raise ValueError(
            "FIT-записи должны быть списком"
        )

    if (
        not is_valid_number(max_gap_seconds)
        or max_gap_seconds <= 0
    ):
        raise ValueError(
            "Некорректный порог пропуска"
        )

    valid_records = []
    invalid_records = 0
    missing_power = 0
    missing_hr = 0

    for record in records:
        if not isinstance(record, dict):
            invalid_records += 1
            continue

        timestamp = record.get("timestamp")
        power = record.get("power")
        heart_rate = record.get("heart_rate")

        if not isinstance(timestamp, datetime):
            invalid_records += 1
            continue

        power_valid = (
            is_valid_number(power)
            and power >= 0
        )

        hr_valid = (
            is_valid_number(heart_rate)
            and heart_rate > 0
        )

        if not power_valid:
            missing_power += 1

        if not hr_valid:
            missing_hr += 1

        if not power_valid or not hr_valid:
            continue

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )
        else:
            timestamp = timestamp.astimezone(
                timezone.utc
            )

        valid_records.append({
            **record,
            "timestamp": timestamp,
        })

    valid_records.sort(
        key=lambda record: record["timestamp"]
    )

    gaps = []
    intervals = []
    segments = []
    duplicate_timestamps = 0

    current_segment = []

    for record in valid_records:
        if not current_segment:
            current_segment.append(record)
            continue

        previous = current_segment[-1]

        current_time = previous["timestamp"]
        next_time = record["timestamp"]

        seconds = (
            next_time - current_time
        ).total_seconds()

        if seconds == 0:
            duplicate_timestamps += 1
            continue

        intervals.append(seconds)

        if seconds > max_gap_seconds:
            gaps.append({
                "start": current_time.isoformat(),
                "end": next_time.isoformat(),
                "duration_seconds": seconds,
            })

        if abs(seconds - 1.0) >= 0.01:
            segments.append(current_segment)
            current_segment = []

        current_segment.append(record)

    if current_segment:
        segments.append(current_segment)

    prepared_records = [
        record
        for segment in segments
        for record in segment
    ]

    total_intervals = len(intervals)

    one_second_intervals = sum(
        1
        for seconds in intervals
        if abs(seconds - 1.0) < 0.01
    )

    one_second_ratio = (
        one_second_intervals / total_intervals
        if total_intervals > 0
        else 0
    )

    valid_records_ratio = (
        len(prepared_records) / len(records)
        if records
        else 0
    )

    if prepared_records:
        elapsed_seconds = (
            prepared_records[-1]["timestamp"]
            - prepared_records[0]["timestamp"]
        ).total_seconds() + 1
    else:
        elapsed_seconds = 0

    time_coverage_ratio = (
        min(
            len(prepared_records) / elapsed_seconds,
            1.0,
        )
        if elapsed_seconds > 0
        else 0
    )

    longest_segment = max(
        (len(segment) for segment in segments),
        default=0,
    )

    longest_gap = max(
        (
            gap["duration_seconds"]
            for gap in gaps
        ),
        default=0,
    )

    has_regular_timing = (
        total_intervals > 0
        and one_second_intervals == total_intervals
        and len(gaps) == 0
        and duplicate_timestamps == 0
        and invalid_records == 0
        and missing_power == 0
        and missing_hr == 0
    )

    suitable_for_power_hr_analysis = (
        len(prepared_records) >= MIN_ANALYSIS_RECORDS
        and duplicate_timestamps == 0
        and one_second_ratio >= MIN_ONE_SECOND_RATIO
        and valid_records_ratio >= MIN_VALID_RECORDS_RATIO
        and time_coverage_ratio >= MIN_TIME_COVERAGE_RATIO
    )

    suitable_for_continuous_analysis = (
        has_regular_timing
        and len(prepared_records) >= MIN_ANALYSIS_RECORDS
    )

    suitable_for_segment_analysis = (
        duplicate_timestamps == 0
        and longest_segment >= MIN_ANALYSIS_RECORDS
    )

    quality = {
        "total_records": len(records),
        "valid_records": len(prepared_records),
        "invalid_records": invalid_records,

        "missing_power_records": missing_power,
        "missing_hr_records": missing_hr,

        "valid_records_ratio": round(
            valid_records_ratio, 4
        ),

        "time_gaps_count": len(gaps),
        "time_gaps": gaps,
        "longest_gap_seconds": longest_gap,

        "duplicate_timestamps": duplicate_timestamps,

        "one_second_intervals_ratio": round(
            one_second_ratio, 4
        ),

        "time_coverage_ratio": round(
            time_coverage_ratio, 4
        ),

        "has_regular_timing": has_regular_timing,

        "continuous_segments_count": len(segments),

        "longest_segment_records": longest_segment,

        "suitable_for_power_hr_analysis": (
            suitable_for_power_hr_analysis
        ),

        "suitable_for_continuous_analysis": (
            suitable_for_continuous_analysis
        ),

        "suitable_for_segment_analysis": (
            suitable_for_segment_analysis
        ),

        "suitable_for_sample_based_analysis": (
            suitable_for_continuous_analysis
        ),
    }

    return {
        "records": prepared_records,
        "segments": segments,
        "quality": quality,
    }


def load_fit_workout_records(file_path):
    """
    Читает FIT-файл и подготавливает
    его записи для анализа.
    """
    raw_records = read_fit_file(file_path)

    return prepare_fit_records(raw_records)