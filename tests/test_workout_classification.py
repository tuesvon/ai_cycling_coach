from datetime import datetime, timedelta, timezone

from src.analytics.workout_classification import (
    classify_workout,
)


FTP = 304


def make_records(power_blocks):
    """
    power_blocks:
        список пар (длительность, мощность).
    """
    start = datetime(
        2026, 11, 23, 10, 0,
        tzinfo=timezone.utc,
    )

    records = []
    offset = 0

    for duration, power in power_blocks:
        for _ in range(duration):
            records.append({
                "timestamp": start + timedelta(
                    seconds=offset
                ),
                "power": power,
                "heart_rate": 130,
                "cadence": 85,
            })

            offset += 1

    return records


def make_interval_workout(
    repetitions,
    interval_seconds,
    interval_power,
    recovery_seconds=240,
):
    blocks = [
        (600, 180),
    ]

    for _ in range(repetitions):
        blocks.extend([
            (
                interval_seconds,
                interval_power,
            ),
            (
                recovery_seconds,
                150,
            ),
        ])

    blocks.append(
        (600, 180)
    )

    return make_records(blocks)


def test_steady_endurance():
    records = make_records([
        (3600, 200),
    ])

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["workout_type"] == (
        "steady"
    )

    assert result["dominant_power_zone"] == (
        "endurance"
    )

    assert result["high_intensity"][
        "intervals_count"
    ] == 0

    assert result[
        "power_zone_distribution"
    ]["endurance"]["percent"] == 100.0

    print("STEADY ENDURANCE TEST PASSED")


def test_five_ninety_second_intervals():
    records = make_interval_workout(
        repetitions=5,
        interval_seconds=90,
        interval_power=375,
    )

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["workout_type"] == (
        "interval"
    )

    intensity = result["high_intensity"]

    assert intensity["intervals_count"] == 5

    assert intensity[
        "total_duration_seconds"
    ] == 450

    assert intensity[
        "average_interval_duration_seconds"
    ] == 90

    assert intensity[
        "average_interval_power"
    ] == 375

    print(
        "FIVE NINETY SECOND INTERVALS TEST PASSED"
    )


def test_four_sixty_second_intervals():
    records = make_interval_workout(
        repetitions=4,
        interval_seconds=60,
        interval_power=375,
    )

    result = classify_workout(
        records,
        FTP,
    )

    assert result["workout_type"] == (
        "interval"
    )

    intensity = result["high_intensity"]

    assert intensity["intervals_count"] == 4

    assert intensity[
        "total_duration_seconds"
    ] == 240

    assert intensity[
        "average_interval_power"
    ] == 375

    print(
        "FOUR SIXTY SECOND INTERVALS TEST PASSED"
    )


def test_short_high_intensity_intervals():
    records = make_interval_workout(
        repetitions=6,
        interval_seconds=20,
        interval_power=550,
    )

    result = classify_workout(
        records,
        FTP,
    )

    assert result["workout_type"] == (
        "interval"
    )

    intensity = result["high_intensity"]

    assert intensity["intervals_count"] == 6

    assert intensity[
        "total_duration_seconds"
    ] == 120

    assert intensity[
        "average_interval_power"
    ] == 550

    print(
        "SHORT HIGH INTENSITY INTERVALS TEST PASSED"
    )


def test_similar_average_power():
    interval_records = make_interval_workout(
        repetitions=5,
        interval_seconds=90,
        interval_power=375,
    )

    interval_result = classify_workout(
        interval_records,
        FTP,
    )

    average_power = interval_result[
        "average_power"
    ]

    steady_records = make_records([
        (
            len(interval_records),
            average_power,
        ),
    ])

    steady_result = classify_workout(
        steady_records,
        FTP,
    )

    assert abs(
        interval_result["average_power"]
        - steady_result["average_power"]
    ) < 0.1

    assert interval_result[
        "duration_seconds"
    ] == steady_result[
        "duration_seconds"
    ]

    assert interval_result[
        "workout_type"
    ] == "interval"

    assert steady_result[
        "workout_type"
    ] == "steady"

    print(
        "SIMILAR AVERAGE POWER TEST PASSED"
    )


def test_short_power_spikes():
    records = make_records([
        (600, 200),
        (3, 600),
        (600, 200),
        (5, 500),
        (600, 200),
    ])

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["high_intensity"][
        "intervals_count"
    ] == 0

    assert result["workout_type"] != (
        "interval"
    )

    print("SHORT POWER SPIKES TEST PASSED")


def test_missing_heart_rate():
    records = make_interval_workout(
        repetitions=5,
        interval_seconds=90,
        interval_power=375,
    )

    for record in records:
        record.pop("heart_rate")

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["workout_type"] == (
        "interval"
    )

    assert result["high_intensity"][
        "intervals_count"
    ] == 5

    print("MISSING HEART RATE TEST PASSED")


def test_interval_with_time_gap():
    records = make_records([
        (1500, 180),
        (60, 375),
        (1500, 180),
    ])

    for record in records[1530:]:
        record["timestamp"] += timedelta(
            seconds=10
        )

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["data_quality"][
        "continuous_segments_count"
    ] == 2

    intervals = result["high_intensity"][
        "intervals"
    ]

    assert len(intervals) == 2

    assert intervals[0][
        "duration_seconds"
    ] == 30

    assert intervals[1][
        "duration_seconds"
    ] == 30

    assert result["high_intensity"][
        "total_duration_seconds"
    ] == 60

    print("INTERVAL WITH TIME GAP TEST PASSED")


def test_irregular_timing():
    records = make_records([
        (1800, 200),
    ])

    start = records[0]["timestamp"]

    for index, record in enumerate(records):
        record["timestamp"] = (
            start + timedelta(
                seconds=index * 3
            )
        )

    result = classify_workout(
        records,
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["workout_type"] == (
        "unknown"
    )

    print("IRREGULAR TIMING TEST PASSED")


def test_invalid_ftp():
    records = make_records([
        (1800, 200),
    ])

    for ftp in (None, 0, -100, True):
        result = classify_workout(
            records,
            ftp,
        )

        assert result["status"] == (
            "insufficient_data"
        )

        assert result["workout_type"] == (
            "unknown"
        )

    print("INVALID FTP TEST PASSED")


def test_insufficient_records():
    result = classify_workout(
        make_records([
            (100, 200),
        ]),
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["workout_type"] == (
        "unknown"
    )

    print("INSUFFICIENT RECORDS TEST PASSED")


def test_empty_records():
    result = classify_workout(
        [],
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    print("EMPTY RECORDS TEST PASSED")


if __name__ == "__main__":
    test_steady_endurance()
    test_five_ninety_second_intervals()
    test_four_sixty_second_intervals()
    test_short_high_intensity_intervals()
    test_similar_average_power()
    test_short_power_spikes()
    test_missing_heart_rate()
    test_interval_with_time_gap()
    test_irregular_timing()
    test_invalid_ftp()
    test_insufficient_records()
    test_empty_records()

    print(
        "\nВсе тесты классификации "
        "тренировок пройдены!"
    )