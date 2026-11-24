
from datetime import datetime, timedelta, timezone

from src.analytics.fit_workout_adapter import (
    prepare_fit_records,
)


def make_records(
    count,
    power=200,
    heart_rate=140,
    interval_seconds=1,
):
    start = datetime(
        2027, 3, 15, 10, 0,
        tzinfo=timezone.utc,
    )

    return [
        {
            "timestamp": start + timedelta(
                seconds=index * interval_seconds
            ),
            "power": power,
            "heart_rate": heart_rate,
            "cadence": 85,
        }
        for index in range(count)
    ]


def test_regular_records():
    result = prepare_fit_records(
        make_records(1800)
    )

    quality = result["quality"]

    assert quality["has_regular_timing"] is True

    assert quality[
        "suitable_for_sample_based_analysis"
    ] is True

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is True

    assert quality[
        "suitable_for_continuous_analysis"
    ] is True

    assert quality[
        "suitable_for_segment_analysis"
    ] is True

    assert quality["time_coverage_ratio"] == 1.0

    assert len(result["records"]) == 1800
    assert len(result["segments"]) == 1

    print("REGULAR FIT RECORDS TEST PASSED")


def test_irregular_timing():
    result = prepare_fit_records(
        make_records(
            1800,
            interval_seconds=3,
        )
    )

    quality = result["quality"]

    assert quality["has_regular_timing"] is False

    assert quality[
        "suitable_for_sample_based_analysis"
    ] is False

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is False

    assert quality[
        "suitable_for_segment_analysis"
    ] is False

    assert quality["time_gaps_count"] == 1799

    print("IRREGULAR TIMING TEST PASSED")


def test_missing_metrics():
    records = make_records(1800)

    records[100]["power"] = None
    records[200]["heart_rate"] = None

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["missing_power_records"] == 1
    assert quality["missing_hr_records"] == 1

    assert len(result["records"]) == 1798

    assert quality["has_regular_timing"] is False

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is True

    assert quality[
        "suitable_for_continuous_analysis"
    ] is False

    assert len(result["segments"]) == 3

    print("MISSING METRICS TEST PASSED")


def test_short_workout():
    result = prepare_fit_records(
        make_records(100)
    )

    quality = result["quality"]

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is False

    assert quality[
        "suitable_for_sample_based_analysis"
    ] is False

    assert quality[
        "suitable_for_segment_analysis"
    ] is False

    print("SHORT WORKOUT TEST PASSED")


def test_empty_records():
    result = prepare_fit_records([])

    quality = result["quality"]

    assert quality["valid_records"] == 0
    assert quality["has_regular_timing"] is False

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is False

    assert result["segments"] == []

    print("EMPTY RECORDS TEST PASSED")


def test_duplicate_timestamp():
    records = make_records(1800)

    records[100]["timestamp"] = (
        records[99]["timestamp"]
    )

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["duplicate_timestamps"] == 1
    assert quality["has_regular_timing"] is False

    assert quality[
        "suitable_for_sample_based_analysis"
    ] is False

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is False

    assert quality[
        "suitable_for_segment_analysis"
    ] is False

    print("DUPLICATE TIMESTAMP TEST PASSED")


def test_single_time_gap():
    records = make_records(3510)

    for record in records[1500:]:
        record["timestamp"] += timedelta(
            seconds=27
        )

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["time_gaps_count"] == 1

    assert quality[
        "longest_gap_seconds"
    ] == 28.0

    assert quality[
        "one_second_intervals_ratio"
    ] == 0.9997

    assert quality[
        "continuous_segments_count"
    ] == 2

    assert quality[
        "longest_segment_records"
    ] == 2010

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is True

    assert quality[
        "suitable_for_continuous_analysis"
    ] is False

    assert quality[
        "suitable_for_segment_analysis"
    ] is True

    assert len(result["records"]) == 3510

    assert len(result["segments"][0]) == 1500
    assert len(result["segments"][1]) == 2010

    print("SINGLE TIME GAP TEST PASSED")


def test_large_time_gap():
    records = make_records(3600)

    for record in records[1800:]:
        record["timestamp"] += timedelta(
            seconds=1800
        )

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["time_gaps_count"] == 1

    assert quality["longest_gap_seconds"] == 1801

    assert quality["time_coverage_ratio"] < 0.99

    assert quality[
        "suitable_for_power_hr_analysis"
    ] is False

    assert quality[
        "suitable_for_continuous_analysis"
    ] is False

    assert quality[
        "suitable_for_segment_analysis"
    ] is True

    print("LARGE TIME GAP TEST PASSED")


def test_multiple_missing_metrics():
    records = make_records(1800)

    records[100]["power"] = None
    records[100]["heart_rate"] = None

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["missing_power_records"] == 1
    assert quality["missing_hr_records"] == 1
    assert quality["valid_records"] == 1799

    print("MULTIPLE MISSING METRICS TEST PASSED")


def test_additional_fit_fields():
    records = make_records(1800)

    records[0]["temperature"] = 22
    records[0]["speed"] = 8.5

    result = prepare_fit_records(records)

    first = result["records"][0]

    assert first["temperature"] == 22
    assert first["speed"] == 8.5
    assert first["cadence"] == 85

    print("ADDITIONAL FIT FIELDS TEST PASSED")


def test_mixed_timestamp_formats():
    records = make_records(1800)

    records[0]["timestamp"] = (
        records[0]["timestamp"].replace(tzinfo=None)
    )

    result = prepare_fit_records(records)

    quality = result["quality"]

    assert quality["has_regular_timing"] is True

    assert quality[
        "suitable_for_continuous_analysis"
    ] is True

    print("MIXED TIMESTAMP FORMATS TEST PASSED")


def test_fit_workout_adapter():
    test_regular_records()
    test_irregular_timing()
    test_missing_metrics()
    test_short_workout()
    test_empty_records()
    test_duplicate_timestamp()
    test_single_time_gap()
    test_large_time_gap()
    test_multiple_missing_metrics()
    test_additional_fit_fields()
    test_mixed_timestamp_formats()

    print(
        "\nВсе тесты FIT-адаптера пройдены!"
    )


if __name__ == "__main__":
    test_fit_workout_adapter()