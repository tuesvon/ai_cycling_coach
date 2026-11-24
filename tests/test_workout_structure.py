
from datetime import datetime, timedelta, timezone

from src.analytics.workout_structure import (
    analyze_workout_structure,
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
                "heart_rate": 140,
                "cadence": 85,
            })

            offset += 1

    return records


def test_single_second_power_dip():
    records = make_records([
        (600, 180),
        (27, 375),
        (1, 300),
        (58, 375),
        (600, 180),
    ])

    result = analyze_workout_structure(
        records,
        FTP,
    )

    assert result["status"] == "ok"
    assert len(result["intervals"]) == 2

    transition = result["transitions"][0]

    assert transition["transition_type"] == (
        "short_power_dip"
    )

    assert transition["duration_seconds"] == 1
    assert transition["average_power"] == 300

    assert transition["possible_power_dip"] is True

    print(
        "SINGLE SECOND POWER DIP TEST PASSED"
    )


def test_active_recovery():
    records = make_records([
        (600, 180),
        (180, 375),
        (30, 250),
        (180, 375),
        (600, 180),
    ])

    result = analyze_workout_structure(
        records,
        FTP,
    )

    assert result["status"] == "ok"
    assert len(result["intervals"]) == 2

    transition = result["transitions"][0]

    assert transition["transition_type"] == (
        "lower_power_segment"
    )

    assert transition["duration_seconds"] == 30
    assert transition["average_power"] == 250

    assert transition[
        "average_power_ftp_percent"
    ] == 82.24

    assert transition["possible_power_dip"] is False

    print("ACTIVE RECOVERY TEST PASSED")


def test_microintervals():
    blocks = [(600, 180)]

    for index in range(5):
        blocks.append((30, 375))

        if index < 4:
            blocks.append((15, 150))

    blocks.append((600, 180))

    result = analyze_workout_structure(
        make_records(blocks),
        FTP,
    )

    assert len(result["intervals"]) == 5
    assert len(result["transitions"]) == 4

    for transition in result["transitions"]:
        assert transition["duration_seconds"] == 15

        assert transition["average_power"] == 150

        assert transition["transition_type"] == (
            "lower_power_segment"
        )

    print("MICROINTERVALS TEST PASSED")


def test_intentional_three_second_dip():
    records = make_records([
        (600, 180),
        (60, 375),
        (3, 100),
        (60, 375),
        (600, 180),
    ])

    result = analyze_workout_structure(
        records,
        FTP,
    )

    assert len(result["intervals"]) == 2

    transition = result["transitions"][0]

    assert transition["duration_seconds"] == 3
    assert transition["average_power"] == 100

    # Даже очень короткое снижение
    # не приводит к объединению.
    assert transition["possible_power_dip"] is True

    assert result["structure_summary"][
        "requires_structure_refinement"
    ] is True

    print(
        "INTENTIONAL SHORT DIP TEST PASSED"
    )


def test_time_gap():
    records = make_records([
        (1500, 180),
        (60, 375),
        (1500, 180),
    ])

    for record in records[1530:]:
        record["timestamp"] += timedelta(
            seconds=10
        )

    result = analyze_workout_structure(
        records,
        FTP,
    )

    assert result["status"] == "ok"
    assert len(result["intervals"]) == 2

    transition = result["transitions"][0]

    assert transition["transition_type"] == (
        "data_gap"
    )

    assert transition["duration_seconds"] == 10
    assert transition["recorded_seconds"] == 0

    assert transition["average_power"] is None

    assert transition["possible_power_dip"] is False

    print("TIME GAP TEST PASSED")


def test_steady_workout():
    result = analyze_workout_structure(
        make_records([
            (3600, 200),
        ]),
        FTP,
    )

    assert result["status"] == "ok"
    assert result["intervals"] == []
    assert result["transitions"] == []

    assert result["structure_summary"][
        "detected_intervals_count"
    ] == 0

    print("STEADY WORKOUT TEST PASSED")


def test_missing_heart_rate():
    records = make_records([
        (600, 180),
        (60, 375),
        (30, 250),
        (60, 375),
        (600, 180),
    ])

    for record in records:
        record.pop("heart_rate")

    result = analyze_workout_structure(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    transition = result["transitions"][0]

    assert transition["average_power"] == 250

    assert transition[
        "average_heart_rate"
    ] is None

    assert transition["heart_rate_samples"] == 0

    print("MISSING HEART RATE TEST PASSED")


def test_insufficient_data():
    result = analyze_workout_structure(
        make_records([
            (100, 200),
        ]),
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["intervals"] == []
    assert result["transitions"] == []

    print("INSUFFICIENT DATA TEST PASSED")


if __name__ == "__main__":
    test_single_second_power_dip()
    test_active_recovery()
    test_microintervals()
    test_intentional_three_second_dip()
    test_time_gap()
    test_steady_workout()
    test_missing_heart_rate()
    test_insufficient_data()

    print(
        "\nВсе тесты анализа структуры "
        "тренировок пройдены!"
    )
