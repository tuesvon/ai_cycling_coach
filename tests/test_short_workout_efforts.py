
from datetime import datetime, timedelta, timezone

from src.analytics.workout_effort_detection import (
    detect_workout_efforts,
)

from src.analytics.workout_effort_profile import (
    analyze_workout_effort_profile,
)


FTP = 304


def make_records(power_blocks):
    start = datetime(
        2026, 11, 24, 10, 0,
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
                "heart_rate": 145,
                "cadence": 90,
            })

            offset += 1

    return records


def test_one_minute_threshold():
    records = make_records([
        (1800, 200),
        (60, 305),
        (1800, 200),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    efforts = result[
        "efforts_by_type"
    ]["threshold"]

    assert len(efforts) == 1

    assert efforts[0][
        "duration_seconds"
    ] == 60

    assert efforts[0][
        "average_power"
    ] == 305

    print(
        "ONE MINUTE THRESHOLD TEST PASSED"
    )


def test_threshold_with_ramp():
    records = make_records([
        (1800, 200),
        (5, 270),
        (50, 305),
        (5, 270),
        (1800, 200),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result[
        "efforts_by_type"
    ]["threshold"]

    assert len(efforts) == 1

    assert efforts[0][
        "duration_seconds"
    ] == 50

    print(
        "THRESHOLD WITH RAMP TEST PASSED"
    )


def test_multiple_short_threshold_intervals():
    records = make_records([
        (600, 180),
        (60, 305),
        (120, 150),
        (60, 305),
        (120, 150),
        (60, 305),
        (600, 180),
    ])

    result = analyze_workout_effort_profile(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["summary"][
        "root_efforts_count"
    ] == 3

    assert result["summary"][
        "unique_work_seconds"
    ] == 180

    for effort in result["root_efforts"]:
        assert effort[
            "actual_power_category"
        ] == "threshold"

        assert effort[
            "duration_seconds"
        ] == 60

    print(
        "MULTIPLE SHORT THRESHOLD "
        "INTERVALS TEST PASSED"
    )


def test_threshold_minimum_duration():
    records = make_records([
        (600, 180),
        (45, 305),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["summary"]["threshold"][
        "efforts_count"
    ] == 1

    print(
        "THRESHOLD MINIMUM DURATION "
        "TEST PASSED"
    )


def test_below_threshold_minimum_duration():
    records = make_records([
        (600, 180),
        (44, 305),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["summary"]["threshold"][
        "efforts_count"
    ] == 0

    print(
        "BELOW THRESHOLD MINIMUM DURATION "
        "TEST PASSED"
    )


def test_short_sweet_spot():
    records = make_records([
        (600, 180),
        (120, 280),
        (600, 180),
    ])

    result = analyze_workout_effort_profile(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert len(
        result["root_efforts"]
    ) == 1

    effort = result["root_efforts"][0]

    assert effort[
        "actual_power_category"
    ] == "sweet_spot"

    assert effort[
        "duration_seconds"
    ] == 120

    print("SHORT SWEET SPOT TEST PASSED")


def test_endurance_with_power_spikes():
    blocks = [(600, 200)]

    for _ in range(10):
        blocks.extend([
            (10, 305),
            (60, 200),
        ])

    blocks.append((600, 200))

    result = detect_workout_efforts(
        make_records(blocks),
        FTP,
    )

    assert result["status"] == "ok"

    assert all(
        not efforts
        for efforts in result[
            "efforts_by_type"
        ].values()
    )

    print(
        "ENDURANCE WITH POWER SPIKES "
        "TEST PASSED"
    )


def test_over_under_structure():
    blocks = [(600, 180)]

    for _ in range(4):
        blocks.extend([
            (120, 290),
            (60, 335),
        ])

    blocks.append((600, 180))

    result = analyze_workout_effort_profile(
        make_records(blocks),
        FTP,
    )

    assert result["status"] == "ok"

    assert result["summary"][
        "root_efforts_count"
    ] == 1

    assert result["summary"][
        "unique_work_seconds"
    ] == 720

    root = result["root_efforts"][0]

    assert root["duration_seconds"] == 720

    assert len(
        root["child_effort_ids"]
    ) == 4

    print("OVER UNDER STRUCTURE TEST PASSED")


def test_short_active_recovery():
    records = make_records([
        (600, 180),
        (60, 305),
        (15, 250),
        (60, 305),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result[
        "efforts_by_type"
    ]["threshold"]

    assert len(efforts) == 2

    assert all(
        effort["duration_seconds"] == 60
        for effort in efforts
    )

    print(
        "SHORT ACTIVE RECOVERY TEST PASSED"
    )


def test_time_gap_inside_threshold():
    records = make_records([
        (1500, 180),
        (120, 305),
        (1500, 180),
    ])

    for record in records[1560:]:
        record["timestamp"] += timedelta(
            seconds=5
        )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    efforts = result[
        "efforts_by_type"
    ]["threshold"]

    assert len(efforts) == 2

    assert all(
        effort["duration_seconds"] == 60
        for effort in efforts
    )

    print(
        "TIME GAP INSIDE THRESHOLD TEST PASSED"
    )


def test_missing_heart_rate():
    records = make_records([
        (600, 180),
        (60, 305),
        (600, 180),
    ])

    for record in records:
        record.pop("heart_rate")

    result = analyze_workout_effort_profile(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    effort = result["root_efforts"][0]

    assert effort[
        "actual_power_category"
    ] == "threshold"

    assert effort[
        "average_heart_rate"
    ] is None

    assert effort[
        "heart_rate_coverage_ratio"
    ] == 0

    print("MISSING HEART RATE TEST PASSED")


if __name__ == "__main__":
    test_one_minute_threshold()
    test_threshold_with_ramp()
    test_multiple_short_threshold_intervals()
    test_threshold_minimum_duration()
    test_below_threshold_minimum_duration()
    test_short_sweet_spot()
    test_endurance_with_power_spikes()
    test_over_under_structure()
    test_short_active_recovery()
    test_time_gap_inside_threshold()
    test_missing_heart_rate()

    print(
        "\nВсе тесты обнаружения "
        "коротких усилий пройдены!"
    )
