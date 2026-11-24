
from datetime import datetime, timedelta, timezone

from src.analytics.workout_interval_refinement import (
    refine_workout_intervals,
)


FTP = 304


def make_records(power_blocks):
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
                "heart_rate": 150,
                "cadence": 95,
            })

            offset += 1

    return records


def test_single_second_power_dip():
    records = make_records([
        (600, 180),
        (27, 375),
        (1, 330),
        (58, 375),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert len(result["original_intervals"]) == 2
    assert len(result["refined_intervals"]) == 1

    interval = result["refined_intervals"][0]

    assert interval["duration_seconds"] == 86

    assert interval["average_power"] == 374.48

    assert interval[
        "included_transition_seconds"
    ] == 1

    assert interval[
        "source_interval_numbers"
    ] == [1, 2]

    assert interval["was_refined"] is True

    print("SINGLE SECOND POWER DIP TEST PASSED")


def test_three_second_power_dip():
    records = make_records([
        (600, 180),
        (21, 375),
        (1, 332),
        (1, 344),
        (1, 332),
        (31, 375),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["original_intervals"]) == 2

    assert len(result["refined_intervals"]) == 1

    interval = result["refined_intervals"][0]

    assert interval["duration_seconds"] == 55

    assert interval[
        "included_transition_seconds"
    ] == 3

    print("THREE SECOND POWER DIP TEST PASSED")


def test_active_recovery():
    records = make_records([
        (600, 180),
        (180, 375),
        (30, 250),
        (180, 375),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["original_intervals"]) == 2

    assert len(result["refined_intervals"]) == 2

    assert result["summary"][
        "connected_transitions_count"
    ] == 0

    for interval in result["refined_intervals"]:
        assert interval["duration_seconds"] == 180

    print("ACTIVE RECOVERY TEST PASSED")


def test_microintervals():
    blocks = [(600, 180)]

    for index in range(5):
        blocks.append((30, 375))

        if index < 4:
            blocks.append((15, 150))

    blocks.append((600, 180))

    result = refine_workout_intervals(
        make_records(blocks),
        FTP,
    )

    assert len(result["original_intervals"]) == 5

    assert len(result["refined_intervals"]) == 5

    assert result["summary"][
        "connected_transitions_count"
    ] == 0

    print("MICROINTERVALS TEST PASSED")


def test_deep_short_dip():
    records = make_records([
        (600, 180),
        (60, 375),
        (3, 100),
        (60, 375),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["refined_intervals"]) == 2

    decision = result[
        "connection_decisions"
    ][0]

    assert decision["can_connect"] is False

    assert "dip_power_too_low" in (
        decision["reasons"]
    )

    print("DEEP SHORT DIP TEST PASSED")


def test_different_interval_power():
    records = make_records([
        (600, 180),
        (60, 375),
        (1, 330),
        (60, 550),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["refined_intervals"]) == 2

    decision = result[
        "connection_decisions"
    ][0]

    assert decision["can_connect"] is False

    assert "different_interval_power" in (
        decision["reasons"]
    )

    print("DIFFERENT INTERVAL POWER TEST PASSED")


def test_time_gap():
    records = make_records([
        (1500, 180),
        (60, 375),
        (1500, 180),
    ])

    for record in records[1530:]:
        record["timestamp"] += timedelta(
            seconds=2
        )

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["original_intervals"]) == 2

    assert len(result["refined_intervals"]) == 2

    assert result["summary"][
        "connected_transitions_count"
    ] == 0

    print("TIME GAP TEST PASSED")


def test_multiple_connections():
    records = make_records([
        (600, 180),
        (30, 375),
        (1, 330),
        (30, 375),
        (1, 327),
        (30, 375),
        (600, 180),
    ])

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert len(result["original_intervals"]) == 3

    assert len(result["refined_intervals"]) == 1

    interval = result["refined_intervals"][0]

    assert interval["duration_seconds"] == 92

    assert interval[
        "source_interval_numbers"
    ] == [1, 2, 3]

    assert result["summary"][
        "connected_transitions_count"
    ] == 2

    assert result["summary"][
        "original_high_intensity_seconds"
    ] == 90

    assert result["summary"][
        "refined_work_seconds"
    ] == 92

    print("MULTIPLE CONNECTIONS TEST PASSED")


def test_interval_metrics():
    records = make_records([
        (600, 180),
        (60, 375),
        (600, 180),
    ])

    for record in records[600:630]:
        record["heart_rate"] = 140

    for record in records[630:660]:
        record["heart_rate"] = 160

    result = refine_workout_intervals(
        records,
        FTP,
    )

    interval = result["refined_intervals"][0]

    assert interval["average_power"] == 375

    assert interval["average_heart_rate"] == 150

    assert interval["max_heart_rate"] == 160

    assert interval["average_cadence"] == 95

    assert interval["heart_rate_samples"] == 60

    assert interval[
        "heart_rate_coverage_ratio"
    ] == 1.0

    print("INTERVAL METRICS TEST PASSED")


def test_missing_heart_rate():
    records = make_records([
        (600, 180),
        (60, 375),
        (600, 180),
    ])

    for record in records:
        record.pop("heart_rate")

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    interval = result["refined_intervals"][0]

    assert interval["average_heart_rate"] is None

    assert interval["heart_rate_samples"] == 0

    assert interval[
        "heart_rate_coverage_ratio"
    ] == 0

    print("MISSING HEART RATE TEST PASSED")


def test_steady_workout():
    result = refine_workout_intervals(
        make_records([
            (3600, 200),
        ]),
        FTP,
    )

    assert result["status"] == "ok"

    assert result["original_intervals"] == []
    assert result["refined_intervals"] == []

    assert result["summary"][
        "refined_intervals_count"
    ] == 0

    print("STEADY WORKOUT TEST PASSED")


def test_insufficient_data():
    result = refine_workout_intervals(
        make_records([
            (100, 200),
        ]),
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["refined_intervals"] == []

    print("INSUFFICIENT DATA TEST PASSED")


def test_original_records_preserved():
    records = make_records([
        (600, 180),
        (30, 375),
        (1, 330),
        (30, 375),
        (600, 180),
    ])

    original = [
        dict(record)
        for record in records
    ]

    result = refine_workout_intervals(
        records,
        FTP,
    )

    assert records == original

    assert len(result["original_intervals"]) == 2

    assert len(result["refined_intervals"]) == 1

    assert result["original_intervals"][0][
        "duration_seconds"
    ] == 30

    assert result["original_intervals"][1][
        "duration_seconds"
    ] == 30

    print("ORIGINAL RECORDS PRESERVED TEST PASSED")


if __name__ == "__main__":
    test_single_second_power_dip()
    test_three_second_power_dip()
    test_active_recovery()
    test_microintervals()
    test_deep_short_dip()
    test_different_interval_power()
    test_time_gap()
    test_multiple_connections()
    test_interval_metrics()
    test_missing_heart_rate()
    test_steady_workout()
    test_insufficient_data()
    test_original_records_preserved()

    print(
        "\nВсе тесты уточнения рабочих "
        "интервалов пройдены!"
    )
