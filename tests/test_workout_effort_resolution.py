
from datetime import datetime, timedelta, timezone
from copy import deepcopy

from src.analytics.workout_effort_resolution import (
    analyze_resolved_workout_efforts,
    resolve_detected_efforts,
    calculate_unique_effort_seconds,
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


def make_effort(
    profile,
    start_second,
    duration,
    power=300,
):
    base = datetime(
        2026, 11, 23, 10, 0,
        tzinfo=timezone.utc,
    )

    start = base + timedelta(
        seconds=start_second
    )

    end = start + timedelta(
        seconds=duration - 1
    )

    return {
        "effort_type": profile,

        "start": start.isoformat(),

        "end": end.isoformat(),

        "duration_seconds": duration,

        "average_power": power,
    }


def test_identical_efforts():
    records = make_records([
        (600, 180),
        (1200, 305),
        (600, 180),
    ])

    result = analyze_resolved_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    summary = result["summary"]

    assert summary["source_efforts_count"] == 3

    assert summary["unique_efforts_count"] == 1

    assert summary[
        "duplicate_descriptions_removed"
    ] == 2

    assert summary[
        "source_duration_seconds"
    ] == 3600

    assert summary[
        "unique_work_seconds"
    ] == 1200

    effort = result["efforts"][0]

    assert effort["primary_profile"] == (
        "threshold"
    )

    assert effort["matched_profiles"] == [
        "tempo",
        "sweet_spot",
        "threshold",
    ]

    print("IDENTICAL EFFORTS TEST PASSED")


def test_separate_threshold_intervals():
    records = make_records([
        (600, 180),
        (1200, 305),
        (300, 150),
        (1200, 305),
        (600, 180),
    ])

    result = analyze_resolved_workout_efforts(
        records,
        FTP,
    )

    summary = result["summary"]

    assert summary["source_efforts_count"] == 6

    assert summary["unique_efforts_count"] == 2

    assert summary["root_efforts_count"] == 2

    assert summary[
        "unique_work_seconds"
    ] == 2400

    print(
        "SEPARATE THRESHOLD INTERVALS TEST PASSED"
    )


def test_nested_efforts():
    blocks = [(600, 180)]

    for _ in range(4):
        blocks.extend([
            (120, 290),
            (60, 335),
        ])

    blocks.append((600, 180))

    result = analyze_resolved_workout_efforts(
        make_records(blocks),
        FTP,
    )

    summary = result["summary"]

    assert result["status"] == "ok"

    assert summary["root_efforts_count"] == 1

    assert summary["nested_efforts_count"] == 4

    assert summary["unique_efforts_count"] == 5

    assert summary[
        "unique_work_seconds"
    ] == 720

    root = next(
        effort
        for effort in result["efforts"]
        if effort["parent_effort_id"] is None
    )

    assert root["duration_seconds"] == 720

    assert len(
        root["child_effort_ids"]
    ) == 4

    print("NESTED EFFORTS TEST PASSED")


def test_active_recovery():
    records = make_records([
        (600, 180),
        (180, 375),
        (30, 250),
        (180, 375),
        (600, 180),
    ])

    result = analyze_resolved_workout_efforts(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    efforts = result["efforts"]

    anaerobic_efforts = [
        effort
        for effort in efforts
        if "anaerobic_power"
        in effort["matched_profiles"]
    ]

    assert len(anaerobic_efforts) == 2

    assert all(
        effort["duration_seconds"] == 180
        for effort in anaerobic_efforts
    )

    assert result["summary"][
        "unique_work_seconds"
    ] == 390

    print("ACTIVE RECOVERY TEST PASSED")


def test_partial_overlap():
    detection = {
        "status": "ok",

        "efforts_by_type": {
            "tempo": [
                make_effort(
                    "tempo",
                    0,
                    300,
                ),
            ],

            "threshold": [
                make_effort(
                    "threshold",
                    200,
                    300,
                ),
            ],
        },
    }

    result = resolve_detected_efforts(
        detection
    )

    summary = result["summary"]

    assert summary["unique_efforts_count"] == 2

    assert summary["root_efforts_count"] == 2

    assert summary["nested_efforts_count"] == 0

    assert summary[
        "partially_overlapping_efforts_count"
    ] == 2

    assert summary[
        "unique_work_seconds"
    ] == 500

    assert summary[
        "double_counted_seconds_removed"
    ] == 100

    print("PARTIAL OVERLAP TEST PASSED")


def test_multiple_nesting_levels():
    detection = {
        "status": "ok",

        "efforts_by_type": {
            "tempo": [
                make_effort(
                    "tempo",
                    0,
                    600,
                ),
            ],

            "threshold": [
                make_effort(
                    "threshold",
                    100,
                    300,
                ),
            ],

            "anaerobic_power": [
                make_effort(
                    "anaerobic_power",
                    200,
                    60,
                    power=375,
                ),
            ],
        },
    }

    result = resolve_detected_efforts(
        detection
    )

    efforts = {
        effort["primary_profile"]: effort
        for effort in result["efforts"]
    }

    tempo = efforts["tempo"]

    threshold = efforts["threshold"]

    anaerobic = efforts[
        "anaerobic_power"
    ]

    assert threshold[
        "parent_effort_id"
    ] == tempo["effort_id"]

    assert anaerobic[
        "parent_effort_id"
    ] == threshold["effort_id"]

    assert result["summary"][
        "unique_work_seconds"
    ] == 600

    print(
        "MULTIPLE NESTING LEVELS TEST PASSED"
    )


def test_separate_efforts():
    efforts = [
        make_effort(
            "threshold",
            0,
            60,
        ),

        make_effort(
            "threshold",
            120,
            60,
        ),
    ]

    seconds = calculate_unique_effort_seconds(
        efforts
    )

    assert seconds == 120

    print("SEPARATE EFFORTS TEST PASSED")


def test_shared_boundary():
    efforts = [
        make_effort(
            "tempo",
            0,
            100,
        ),

        make_effort(
            "threshold",
            99,
            100,
        ),
    ]

    seconds = calculate_unique_effort_seconds(
        efforts
    )

    assert seconds == 199

    print("SHARED BOUNDARY TEST PASSED")


def test_microintervals():
    blocks = [(600, 180)]

    for index in range(6):
        blocks.append((30, 375))

        if index < 5:
            blocks.append((15, 150))

    blocks.append((600, 180))

    result = analyze_resolved_workout_efforts(
        make_records(blocks),
        FTP,
    )

    assert result["summary"][
        "unique_efforts_count"
    ] == 6

    assert result["summary"][
        "root_efforts_count"
    ] == 6

    assert result["summary"][
        "unique_work_seconds"
    ] == 180

    print("MICROINTERVALS TEST PASSED")


def test_endurance_workout():
    result = analyze_resolved_workout_efforts(
        make_records([
            (3600, 200),
        ]),
        FTP,
    )

    assert result["status"] == "ok"

    assert result["efforts"] == []

    assert result["root_effort_ids"] == []

    assert result["summary"][
        "unique_work_seconds"
    ] == 0

    print("ENDURANCE WORKOUT TEST PASSED")


def test_insufficient_data():
    result = analyze_resolved_workout_efforts(
        make_records([
            (100, 200),
        ]),
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["efforts"] == []

    print("INSUFFICIENT DATA TEST PASSED")


def test_original_detection_preserved():
    detection = {
        "status": "ok",

        "efforts_by_type": {
            "tempo": [
                make_effort(
                    "tempo",
                    0,
                    600,
                ),
            ],

            "threshold": [
                make_effort(
                    "threshold",
                    0,
                    600,
                ),
            ],
        },
    }

    original = deepcopy(detection)

    resolve_detected_efforts(
        detection
    )

    assert detection == original

    print(
        "ORIGINAL DETECTION PRESERVED TEST PASSED"
    )


if __name__ == "__main__":
    test_identical_efforts()
    test_separate_threshold_intervals()
    test_nested_efforts()
    test_active_recovery()
    test_partial_overlap()
    test_multiple_nesting_levels()
    test_separate_efforts()
    test_shared_boundary()
    test_microintervals()
    test_endurance_workout()
    test_insufficient_data()
    test_original_detection_preserved()

    print(
        "\nВсе тесты разрешения "
        "пересечений усилий пройдены!"
    )
