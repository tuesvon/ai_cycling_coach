
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.analytics.workout_effort_profile import (
    classify_effort_power,
    classify_effort_duration,
    build_workout_effort_profile,
    analyze_workout_effort_profile,
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
    effort_id,
    profile,
    start_second,
    duration,
    average_power,
    parent_id=None,
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
        "effort_id": effort_id,

        "primary_profile": profile,

        "matched_profiles": [
            profile
        ],

        "start": start.isoformat(),

        "end": end.isoformat(),

        "duration_seconds": duration,

        "average_power": average_power,

        "parent_effort_id": parent_id,

        "child_effort_ids": [],

        "overlapping_effort_ids": [],
    }


def test_power_categories():
    cases = [
        (100, "recovery"),
        (200, "endurance"),
        (250, "tempo"),
        (280, "sweet_spot"),
        (305, "threshold"),
        (350, "vo2max_power"),
        (375, "anaerobic_power"),
        (550, "very_high_intensity"),
    ]

    for power, expected in cases:
        result = classify_effort_power(
            power,
            FTP,
        )

        assert result == expected, (
            power,
            result,
            expected,
        )

    print("POWER CATEGORIES TEST PASSED")


def test_duration_categories():
    cases = [
        (8, "very_short"),
        (20, "short"),
        (90, "medium"),
        (420, "long"),
        (600, "extended"),
        (1200, "sustained"),
    ]

    for duration, expected in cases:
        result = classify_effort_duration(
            duration
        )

        assert result == expected

    print("DURATION CATEGORIES TEST PASSED")


def test_vo2max_detection_mismatch():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="vo2max_power",
                start_second=0,
                duration=87,
                average_power=375.04,
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    effort = result["efforts"][0]

    assert effort["detection_profile"] == (
        "vo2max_power"
    )

    assert effort["actual_power_category"] == (
        "anaerobic_power"
    )

    assert effort["profile_mismatch"] is True

    assert result["summary"][
        "profile_mismatch_count"
    ] == 1

    print("VO2MAX DETECTION MISMATCH TEST PASSED")


def test_threshold_detection_mismatch():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="tempo",
                start_second=0,
                duration=420,
                average_power=304.77,
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    effort = result["efforts"][0]

    assert effort["actual_power_category"] == (
        "threshold"
    )

    assert effort["duration_category"] == (
        "long"
    )

    print(
        "THRESHOLD DETECTION MISMATCH TEST PASSED"
    )


def test_sweet_spot_detection_mismatch():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="sweet_spot",
                start_second=0,
                duration=190,
                average_power=347.58,
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    effort = result["efforts"][0]

    assert effort["actual_power_category"] == (
        "vo2max_power"
    )

    assert effort["profile_mismatch"] is True

    print(
        "SWEET SPOT DETECTION MISMATCH TEST PASSED"
    )


def test_matching_profile():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="threshold",
                start_second=0,
                duration=600,
                average_power=305,
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    effort = result["efforts"][0]

    assert effort["actual_power_category"] == (
        "threshold"
    )

    assert effort["profile_mismatch"] is False

    print("MATCHING PROFILE TEST PASSED")


def test_nested_efforts():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="vo2max_power",
                start_second=0,
                duration=90,
                average_power=375,
            ),

            make_effort(
                effort_id="effort_2",
                profile="anaerobic_power",
                start_second=10,
                duration=30,
                average_power=390,
                parent_id="effort_1",
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    assert result["summary"][
        "efforts_count"
    ] == 2

    assert result["summary"][
        "root_efforts_count"
    ] == 1

    assert result["summary"][
        "nested_efforts_count"
    ] == 1

    category = result[
        "category_summary"
    ]["anaerobic_power"]

    assert category["efforts_count"] == 2

    assert category[
        "unique_covered_seconds"
    ] == 90

    assert result["summary"][
        "unique_work_seconds"
    ] == 90

    print("NESTED EFFORTS TEST PASSED")


def test_different_category_overlap():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="threshold",
                start_second=0,
                duration=600,
                average_power=305,
            ),

            make_effort(
                effort_id="effort_2",
                profile="vo2max_power",
                start_second=100,
                duration=60,
                average_power=350,
                parent_id="effort_1",
            ),
        ],
    }

    result = build_workout_effort_profile(
        resolution,
        FTP,
    )

    assert result["summary"][
        "unique_work_seconds"
    ] == 600

    categories = result[
        "category_summary"
    ]

    assert categories["threshold"][
        "unique_covered_seconds"
    ] == 600

    assert categories["vo2max_power"][
        "unique_covered_seconds"
    ] == 60

    print(
        "DIFFERENT CATEGORY OVERLAP TEST PASSED"
    )


def test_full_threshold_workout():
    records = make_records([
        (600, 180),
        (1200, 305),
        (300, 150),
        (1200, 305),
        (600, 180),
    ])

    result = analyze_workout_effort_profile(
        records,
        FTP,
    )

    assert result["status"] == "ok"

    assert result["summary"][
        "root_efforts_count"
    ] == 2

    assert result["summary"][
        "unique_work_seconds"
    ] == 2400

    assert all(
        effort["actual_power_category"]
        == "threshold"
        for effort in result["root_efforts"]
    )

    print("FULL THRESHOLD WORKOUT TEST PASSED")


def test_full_anaerobic_workout():
    blocks = [(600, 180)]

    for index in range(5):
        blocks.append((90, 375))

        if index < 4:
            blocks.append((240, 150))

    blocks.append((600, 180))

    result = analyze_workout_effort_profile(
        make_records(blocks),
        FTP,
    )

    assert result["status"] == "ok"

    assert result["summary"][
        "root_efforts_count"
    ] == 5

    assert all(
        effort["actual_power_category"]
        == "anaerobic_power"
        for effort in result["root_efforts"]
    )

    assert result["summary"][
        "unique_work_seconds"
    ] == 450

    print("FULL ANAEROBIC WORKOUT TEST PASSED")


def test_endurance_workout():
    result = analyze_workout_effort_profile(
        make_records([
            (3600, 200),
        ]),
        FTP,
    )

    assert result["status"] == "ok"

    assert result["efforts"] == []

    assert result["root_efforts"] == []

    assert result["summary"][
        "unique_work_seconds"
    ] == 0

    print("ENDURANCE WORKOUT TEST PASSED")


def test_invalid_data():
    assert classify_effort_power(
        None,
        FTP,
    ) == "unknown"

    assert classify_effort_power(
        300,
        0,
    ) == "unknown"

    assert classify_effort_duration(
        None
    ) == "unknown"

    result = analyze_workout_effort_profile(
        [],
        FTP,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    print("INVALID DATA TEST PASSED")


def test_original_resolution_preserved():
    resolution = {
        "status": "ok",

        "efforts": [
            make_effort(
                effort_id="effort_1",
                profile="tempo",
                start_second=0,
                duration=420,
                average_power=305,
            ),
        ],
    }

    original = deepcopy(resolution)

    build_workout_effort_profile(
        resolution,
        FTP,
    )

    assert resolution == original

    print(
        "ORIGINAL RESOLUTION PRESERVED TEST PASSED"
    )


if __name__ == "__main__":
    test_power_categories()
    test_duration_categories()
    test_vo2max_detection_mismatch()
    test_threshold_detection_mismatch()
    test_sweet_spot_detection_mismatch()
    test_matching_profile()
    test_nested_efforts()
    test_different_category_overlap()
    test_full_threshold_workout()
    test_full_anaerobic_workout()
    test_endurance_workout()
    test_invalid_data()
    test_original_resolution_preserved()

    print(
        "\nВсе тесты профиля фактической "
        "интенсивности усилий пройдены!"
    )
