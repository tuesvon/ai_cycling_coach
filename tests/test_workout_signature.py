from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.analytics.workout_signature import (
    resolve_workout_ftp,
    extract_workout_conditions,
    build_workout_signature,
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


def make_activity(
    name="5x1:30@375W",
    ftp=304,
):
    return {
        "id": "intervals:test_workout",

        "name": name,

        "type": "cycling",

        "start_date": (
            "2026-11-23T10:00:00Z"
        ),

        "sources": {
            "intervals": {
                "icu_ftp": ftp,

                "type": "VirtualRide",

                "trainer": True,

                "average_temp": 21,

                "icu_rpe": 7,

                "paired_event_id": 12345,
            },

            "garmin": {
                "activityType": {
                    "typeKey": "indoor_cycling",
                },
            },
        },
    }


def make_interval_records():
    blocks = [(600, 180)]

    for index in range(5):
        blocks.append((90, 375))

        if index < 4:
            blocks.append((240, 150))

    blocks.append((600, 180))

    return make_records(blocks)


def test_activity_ftp_priority():
    activity = make_activity(
        ftp=290
    )

    result = resolve_workout_ftp(
        activity,
        fallback_ftp=304,
    )

    assert result["ftp"] == 290

    assert result["source"] == (
        "intervals.icu_ftp"
    )

    print("ACTIVITY FTP PRIORITY TEST PASSED")


def test_fallback_ftp():
    activity = make_activity(
        ftp=None
    )

    result = resolve_workout_ftp(
        activity,
        fallback_ftp=304,
    )

    assert result["ftp"] == 304

    assert result["source"] == "fallback"

    assert result["confidence"] == (
        "estimated"
    )

    print("FALLBACK FTP TEST PASSED")


def test_invalid_ftp():
    activity = make_activity(
        ftp=0
    )

    result = build_workout_signature(
        activity=activity,
        records=make_interval_records(),
    )

    assert result["status"] == (
        "insufficient_data"
    )

    print("INVALID FTP TEST PASSED")


def test_indoor_conditions():
    result = extract_workout_conditions(
        make_activity()
    )

    assert result["environment"] == "indoor"

    assert result[
        "average_temperature"
    ] == 21

    assert result["rpe"] == 7

    print("INDOOR CONDITIONS TEST PASSED")


def test_outdoor_conditions():
    activity = {
        "sources": {
            "intervals": {
                "type": "Ride",
                "trainer": False,
            },
        },
    }

    result = extract_workout_conditions(
        activity
    )

    assert result["environment"] == "outdoor"

    print("OUTDOOR CONDITIONS TEST PASSED")


def test_missing_conditions():
    result = extract_workout_conditions(
        {}
    )

    assert result["environment"] == "unknown"

    assert result[
        "average_temperature"
    ] is None

    assert result["rpe"] is None

    print("MISSING CONDITIONS TEST PASSED")


def test_interval_signature():
    result = build_workout_signature(
        activity=make_activity(),
        records=make_interval_records(),
    )

    assert result["status"] == "ok"

    assert result["activity_context"][
        "activity_context"
    ] == "structured_workout"

    structure = result["effort_structure"]

    assert structure[
        "root_efforts_count"
    ] == 5

    assert structure[
        "unique_work_seconds"
    ] == 450

    summary = structure[
        "root_effort_summary"
    ]["anaerobic_power"]

    assert summary["efforts_count"] == 5

    assert summary[
        "average_duration_seconds"
    ] == 90

    assert summary[
        "average_effort_power"
    ] == 375

    gaps = structure[
        "between_effort_gaps"
    ]

    assert len(gaps) == 4

    assert all(
        gap["duration_seconds"] == 240
        for gap in gaps
    )

    print("INTERVAL SIGNATURE TEST PASSED")


def test_race_context_preserved():
    activity = make_activity(
        name="Zwift - Race"
    )

    activity["sources"]["intervals"][
        "race"
    ] = True

    result = build_workout_signature(
        activity=activity,
        records=make_interval_records(),
    )

    assert result["status"] == "ok"

    assert result["activity_context"][
        "activity_context"
    ] == "race"

    assert result["effort_structure"][
        "root_efforts_count"
    ] == 5

    print("RACE CONTEXT PRESERVED TEST PASSED")


def test_endurance_signature():
    activity = make_activity(
        name="60m@200W"
    )

    result = build_workout_signature(
        activity=activity,

        records=make_records([
            (3600, 200),
        ]),
    )

    assert result["status"] == "ok"

    assert result["load_profile"][
        "dominant_power_zone"
    ] == "endurance"

    structure = result["effort_structure"]

    assert structure[
        "root_efforts_count"
    ] == 0

    assert structure[
        "unique_work_seconds"
    ] == 0

    assert structure[
        "structure_type"
    ] == "no_detected_efforts"

    print("ENDURANCE SIGNATURE TEST PASSED")


def test_mixed_endurance_signature():
    activity = make_activity(
        name="Z2 + 1min Z4"
    )

    records = make_records([
        (1800, 200),
        (60, 305),
        (1800, 200),
    ])

    result = build_workout_signature(
        activity=activity,
        records=records,
    )

    assert result["status"] == "ok"

    assert result["load_profile"][
        "dominant_power_zone"
    ] == "endurance"

    structure = result["effort_structure"]

    assert structure[
        "root_efforts_count"
    ] == 1

    assert structure[
        "unique_work_seconds"
    ] == 60

    assert structure["root_efforts"][0][
        "power_category"
    ] == "threshold"

    assert structure[
        "work_fraction"
    ] < 0.02

    print("MIXED ENDURANCE SIGNATURE TEST PASSED")


def test_nested_structure():
    blocks = [(600, 180)]

    for _ in range(4):
        blocks.extend([
            (120, 290),
            (60, 335),
        ])

    blocks.append((600, 180))

    result = build_workout_signature(
        activity=make_activity(
            name="Over-Under"
        ),

        records=make_records(blocks),
    )

    assert result["status"] == "ok"

    structure = result["effort_structure"]

    assert structure[
        "root_efforts_count"
    ] == 1

    assert structure[
        "nested_efforts_count"
    ] == 4

    assert structure[
        "unique_work_seconds"
    ] == 720

    print("NESTED STRUCTURE TEST PASSED")


def test_historical_ftp_changes_category():
    records = make_records([
        (600, 180),
        (600, 300),
        (600, 180),
    ])

    result = build_workout_signature(
        activity=make_activity(
            ftp=270
        ),

        records=records,

        fallback_ftp=304,
    )

    assert result["status"] == "ok"

    assert result["ftp_info"]["ftp"] == 270

    effort = result["effort_structure"][
        "root_efforts"
    ][0]

    assert effort["power_category"] == (
        "vo2max_power"
    )

    print(
        "HISTORICAL FTP CHANGES "
        "CATEGORY TEST PASSED"
    )


def test_ignore_power():
    activity = make_activity()

    activity["sources"]["intervals"][
        "icu_ignore_power"
    ] = True

    result = build_workout_signature(
        activity=activity,
        records=make_interval_records(),
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["conditions"][
        "ignore_power"
    ] is True

    print("IGNORE POWER TEST PASSED")


def test_ignore_heart_rate():
    activity = make_activity()

    activity["sources"]["intervals"][
        "icu_ignore_hr"
    ] = True

    result = build_workout_signature(
        activity=activity,
        records=make_interval_records(),
    )

    assert result["status"] == "ok"

    efforts = result["effort_structure"][
        "root_efforts"
    ]

    assert all(
        effort["average_heart_rate"] is None
        for effort in efforts
    )

    assert all(
        effort["heart_rate_coverage_ratio"] == 0
        for effort in efforts
    )

    print("IGNORE HEART RATE TEST PASSED")


def test_insufficient_records():
    result = build_workout_signature(
        activity=make_activity(),

        records=make_records([
            (100, 200),
        ]),
    )

    assert result["status"] == (
        "insufficient_data"
    )

    print("INSUFFICIENT RECORDS TEST PASSED")


def test_original_data_preserved():
    activity = make_activity()

    records = make_interval_records()

    original_activity = deepcopy(
        activity
    )

    original_records = deepcopy(
        records
    )

    build_workout_signature(
        activity=activity,
        records=records,
    )

    assert activity == original_activity

    assert records == original_records

    print("ORIGINAL DATA PRESERVED TEST PASSED")


if __name__ == "__main__":
    test_activity_ftp_priority()
    test_fallback_ftp()
    test_invalid_ftp()
    test_indoor_conditions()
    test_outdoor_conditions()
    test_missing_conditions()
    test_interval_signature()
    test_race_context_preserved()
    test_endurance_signature()
    test_mixed_endurance_signature()
    test_nested_structure()
    test_historical_ftp_changes_category()
    test_ignore_power()
    test_ignore_heart_rate()
    test_insufficient_records()
    test_original_data_preserved()

    print(
        "\nВсе тесты единого профиля "
        "тренировки пройдены!"
    )