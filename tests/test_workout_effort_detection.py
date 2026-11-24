
from datetime import datetime, timedelta, timezone

from src.analytics.workout_effort_detection import (
    detect_workout_efforts,
    smooth_segment_power,
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
                "heart_rate": 145,
                "cadence": 90,
            })

            offset += 1

    return records


def make_interval_workout(
    repetitions,
    work_duration,
    work_power,
    recovery_duration,
    recovery_power,
):
    blocks = [(600, 180)]

    for index in range(repetitions):
        blocks.append(
            (work_duration, work_power)
        )

        if index < repetitions - 1:
            blocks.append(
                (
                    recovery_duration,
                    recovery_power,
                )
            )

    blocks.append((600, 180))

    return make_records(blocks)


def test_endurance_workout():
    records = make_records([
        (3600, 200),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert all(
        not efforts
        for efforts in result[
            "efforts_by_type"
        ].values()
    )

    print("ENDURANCE WORKOUT TEST PASSED")


def test_tempo_intervals():
    records = make_interval_workout(
        repetitions=3,
        work_duration=900,
        work_power=250,
        recovery_duration=180,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    tempo = result["summary"]["tempo"]

    assert tempo["efforts_count"] == 3

    assert tempo[
        "total_duration_seconds"
    ] == 2700

    assert result["summary"]["sweet_spot"][
        "efforts_count"
    ] == 0

    print("TEMPO INTERVALS TEST PASSED")


def test_sweet_spot_intervals():
    records = make_interval_workout(
        repetitions=3,
        work_duration=1200,
        work_power=280,
        recovery_duration=300,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    sweet_spot = result["summary"][
        "sweet_spot"
    ]

    assert sweet_spot["efforts_count"] == 3

    assert sweet_spot[
        "total_duration_seconds"
    ] == 3600

    assert sweet_spot[
        "average_power"
    ] == 280

    assert result["summary"]["threshold"][
        "efforts_count"
    ] == 0

    print("SWEET SPOT INTERVALS TEST PASSED")


def test_threshold_intervals():
    records = make_interval_workout(
        repetitions=2,
        work_duration=1200,
        work_power=305,
        recovery_duration=300,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    threshold = result["summary"][
        "threshold"
    ]

    assert threshold["efforts_count"] == 2

    assert threshold[
        "total_duration_seconds"
    ] == 2400

    assert threshold[
        "average_power"
    ] == 305

    print("THRESHOLD INTERVALS TEST PASSED")


def test_vo2max_power_intervals():
    records = make_interval_workout(
        repetitions=5,
        work_duration=180,
        work_power=350,
        recovery_duration=180,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    vo2max = result["summary"][
        "vo2max_power"
    ]

    assert vo2max["efforts_count"] == 5

    assert vo2max[
        "total_duration_seconds"
    ] == 900

    print("VO2MAX POWER INTERVALS TEST PASSED")


def test_anaerobic_power_intervals():
    records = make_interval_workout(
        repetitions=5,
        work_duration=90,
        work_power=375,
        recovery_duration=240,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    anaerobic = result["summary"][
        "anaerobic_power"
    ]

    assert anaerobic["efforts_count"] == 5

    assert anaerobic[
        "total_duration_seconds"
    ] == 450

    print(
        "ANAEROBIC POWER INTERVALS TEST PASSED"
    )


def test_very_high_intensity():
    records = make_interval_workout(
        repetitions=6,
        work_duration=20,
        work_power=550,
        recovery_duration=300,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["summary"][
        "very_high_intensity"
    ]

    assert efforts["efforts_count"] == 6

    assert efforts[
        "total_duration_seconds"
    ] == 120

    print("VERY HIGH INTENSITY TEST PASSED")


def test_short_sprint():
    records = make_records([
        (600, 180),
        (8, 900),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["efforts_by_type"][
        "very_high_intensity"
    ]

    assert len(efforts) == 1

    assert efforts[0][
        "duration_seconds"
    ] == 8

    assert efforts[0][
        "average_power"
    ] == 900

    print("SHORT SPRINT TEST PASSED")


def test_active_recovery():
    records = make_records([
        (600, 180),
        (180, 375),
        (30, 250),
        (180, 375),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["efforts_by_type"][
        "vo2max_power"
    ]

    assert len(efforts) == 2

    assert efforts[0][
        "duration_seconds"
    ] == 180

    assert efforts[1][
        "duration_seconds"
    ] == 180

    print("ACTIVE RECOVERY TEST PASSED")


def test_microintervals():
    records = make_interval_workout(
        repetitions=6,
        work_duration=30,
        work_power=375,
        recovery_duration=15,
        recovery_power=150,
    )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["efforts_by_type"][
        "anaerobic_power"
    ]

    assert len(efforts) == 6

    assert all(
        effort["duration_seconds"] == 30
        for effort in efforts
    )

    print("MICROINTERVALS TEST PASSED")


def test_short_power_dip():
    records = make_records([
        (600, 180),
        (40, 375),
        (1, 330),
        (49, 375),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["efforts_by_type"][
        "anaerobic_power"
    ]

    assert len(efforts) == 1

    effort = efforts[0]

    assert effort[
        "duration_seconds"
    ] == 90

    assert effort[
        "seconds_above_threshold"
    ] == 89

    assert effort["average_power"] == 374.5

    assert effort["min_power"] == 330

    print("SHORT POWER DIP TEST PASSED")


def test_single_power_spike():
    records = make_records([
        (600, 180),
        (1, 900),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["summary"][
        "very_high_intensity"
    ]["efforts_count"] == 0

    print("SINGLE POWER SPIKE TEST PASSED")


def test_time_gap():
    records = make_records([
        (1500, 180),
        (120, 375),
        (1500, 180),
    ])

    for record in records[1560:]:
        record["timestamp"] += timedelta(
            seconds=10
        )

    result = detect_workout_efforts(
        records,
        FTP,
    )

    efforts = result["efforts_by_type"][
        "anaerobic_power"
    ]

    assert len(efforts) == 2

    assert efforts[0][
        "duration_seconds"
    ] == 60

    assert efforts[1][
        "duration_seconds"
    ] == 60

    print("TIME GAP TEST PASSED")


def test_overlapping_profiles():
    records = make_records([
        (600, 180),
        (600, 305),
        (600, 180),
    ])

    result = detect_workout_efforts(
        records,
        FTP,
    )

    for effort_type in (
        "tempo",
        "sweet_spot",
        "threshold",
    ):
        efforts = result[
            "efforts_by_type"
        ][effort_type]

        assert len(efforts) == 1

        assert efforts[0][
            "duration_seconds"
        ] == 600

    print("OVERLAPPING PROFILES TEST PASSED")


def test_missing_heart_rate():
    records = make_records([
        (600, 180),
        (600, 280),
        (600, 180),
    ])

    for record in records:
        record.pop("heart_rate")

    result = detect_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    effort = result["efforts_by_type"][
        "sweet_spot"
    ][0]

    assert effort["average_heart_rate"] is None

    assert effort[
        "heart_rate_coverage_ratio"
    ] == 0

    print("MISSING HEART RATE TEST PASSED")


def test_invalid_ftp():
    records = make_records([
        (1800, 200),
    ])

    result = detect_workout_efforts(
        records,
        None,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    print("INVALID FTP TEST PASSED")


def test_original_records_preserved():
    records = make_records([
        (600, 180),
        (40, 375),
        (1, 330),
        (49, 375),
        (600, 180),
    ])

    original = [
        dict(record)
        for record in records
    ]

    detect_workout_efforts(
        records,
        FTP,
    )

    assert records == original

    print("ORIGINAL RECORDS PRESERVED TEST PASSED")


def test_median_smoothing():
    records = make_records([
        (4, 375),
        (1, 330),
        (4, 375),
    ])

    smoothed = smooth_segment_power(
        records
    )

    assert smoothed == [375] * 9

    assert records[4]["power"] == 330

    print("MEDIAN SMOOTHING TEST PASSED")


if __name__ == "__main__":
    test_endurance_workout()
    test_tempo_intervals()
    test_sweet_spot_intervals()
    test_threshold_intervals()
    test_vo2max_power_intervals()
    test_anaerobic_power_intervals()
    test_very_high_intensity()
    test_short_sprint()
    test_active_recovery()
    test_microintervals()
    test_short_power_dip()
    test_single_power_spike()
    test_time_gap()
    test_overlapping_profiles()
    test_missing_heart_rate()
    test_invalid_ftp()
    test_original_records_preserved()
    test_median_smoothing()

    print(
        "\nВсе тесты обнаружения "
        "рабочих усилий пройдены!"
    )
