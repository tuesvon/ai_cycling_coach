from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.analytics.workout_signature import (
    build_workout_signature,
)

from src.analytics.workout_similarity import (
    calculate_numeric_similarity,
    calculate_weighted_score,
    compare_workout_signatures,
    find_similar_workout_signatures,
    get_comparison_family,
)


FTP = 304


def make_records(
    power_blocks,
    heart_rate=145,
):
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
                "heart_rate": heart_rate,
                "cadence": 90,
            })

            offset += 1

    return records


def make_activity(
    activity_id,
    name,
    date="2026-11-23T10:00:00Z",
    ftp=FTP,
    indoor=True,
    temperature=21,
    race=False,
):
    return {
        "id": activity_id,
        "name": name,
        "type": "cycling",
        "start_date": date,

        "sources": {
            "intervals": {
                "icu_ftp": ftp,

                "type": (
                    "VirtualRide"
                    if indoor
                    else "Ride"
                ),

                "trainer": indoor,
                "average_temp": temperature,
                "power_meter": "test_power_meter",
                "race": race,
            },
        },
    }


def make_interval_signature(
    activity_id="reference",
    repetitions=5,
    work_duration=90,
    work_power=375,
    recovery_duration=240,
    recovery_power=150,
    warmup_duration=600,
    cooldown_duration=600,
    heart_rate=145,
    date="2026-11-23T10:00:00Z",
    indoor=True,
    temperature=21,
    race=False,
):
    blocks = [
        (warmup_duration, 180),
    ]

    for index in range(repetitions):
        blocks.append(
            (work_duration, work_power)
        )

        if index < repetitions - 1:
            blocks.append((
                recovery_duration,
                recovery_power,
            ))

    blocks.append((
        cooldown_duration,
        180,
    ))

    name = (
        "Zwift - Race"
        if race
        else (
            f"{repetitions}x"
            f"{work_duration}s"
            f"@{work_power}W"
        )
    )

    signature = build_workout_signature(
        activity=make_activity(
            activity_id=activity_id,
            name=name,
            date=date,
            indoor=indoor,
            temperature=temperature,
            race=race,
        ),

        records=make_records(
            blocks,
            heart_rate=heart_rate,
        ),
    )

    assert signature["status"] == "ok"

    return signature


def make_endurance_signature(
    activity_id,
    duration=3600,
    power=200,
    date="2026-11-23T10:00:00Z",
    heart_rate=145,
):
    signature = build_workout_signature(
        activity=make_activity(
            activity_id=activity_id,
            name="Z2",
            date=date,
        ),

        records=make_records(
            [(duration, power)],
            heart_rate=heart_rate,
        ),
    )

    assert signature["status"] == "ok"

    return signature


def test_numeric_similarity():
    assert calculate_numeric_similarity(
        100, 100
    ) == 1.0

    assert calculate_numeric_similarity(
        100, 50
    ) == 0.5

    assert calculate_numeric_similarity(
        0, 0
    ) == 1.0

    assert calculate_numeric_similarity(
        None, 100
    ) is None

    assert calculate_numeric_similarity(
        -10, 100
    ) is None

    print("NUMERIC SIMILARITY TEST PASSED")


def test_missing_weighted_component():
    result = calculate_weighted_score(
        components={
            "power": 1.0,
            "duration": None,
        },

        weights={
            "power": 0.60,
            "duration": 0.40,
        },
    )

    assert result["score"] == 100

    assert result[
        "criteria_coverage"
    ] == 0.60

    print(
        "MISSING WEIGHTED COMPONENT "
        "TEST PASSED"
    )


def test_identical_interval_workouts():
    reference = make_interval_signature(
        activity_id="reference"
    )

    candidate = make_interval_signature(
        activity_id="candidate"
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == "ok"

    assert result["score"] == 100

    assert result[
        "similarity_level"
    ] == "high"

    assert result[
        "matched_efforts_count"
    ] == 5

    assert result[
        "reference_match_coverage"
    ] == 1.0

    assert result[
        "candidate_match_coverage"
    ] == 1.0

    print(
        "IDENTICAL INTERVAL WORKOUTS "
        "TEST PASSED"
    )


def test_different_warmup_duration():
    reference = make_interval_signature(
        warmup_duration=1800,
        cooldown_duration=1800,
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        warmup_duration=300,
        cooldown_duration=300,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["score"] == 100

    assert result[
        "matched_efforts_count"
    ] == 5

    print(
        "DIFFERENT WARMUP DURATION "
        "TEST PASSED"
    )


def test_different_repetitions():
    reference = make_interval_signature(
        repetitions=5
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        repetitions=4,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == "ok"

    assert result[
        "matched_efforts_count"
    ] == 4

    assert result[
        "reference_match_coverage"
    ] == 0.80

    assert result[
        "candidate_match_coverage"
    ] == 1.0

    assert 65 <= result["score"] < 100

    print(
        "DIFFERENT REPETITIONS TEST PASSED"
    )


def test_realistic_375w_comparison():
    reference = make_interval_signature(
        repetitions=5,
        work_duration=90,
        work_power=375,
        recovery_duration=240,
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        repetitions=4,
        work_duration=60,
        work_power=375,
        recovery_duration=60,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == "ok"

    assert result[
        "matched_efforts_count"
    ] == 4

    assert result[
        "comparison_scope"
    ] == "matched_efforts_only"

    assert not result[
        "full_workout_comparison_candidate"
    ]

    print(
        "REALISTIC 375W COMPARISON "
        "TEST PASSED"
    )

    print("Similarity score:", result["score"])


def test_different_interval_power():
    reference = make_interval_signature(
        work_power=375
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        work_power=550,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result[
        "matched_efforts_count"
    ] == 0

    assert result["score"] < 45

    assert result[
        "comparison_scope"
    ] == "none"

    print(
        "DIFFERENT INTERVAL POWER TEST PASSED"
    )


def test_different_interval_duration():
    reference = make_interval_signature(
        work_duration=90
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        work_duration=20,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result[
        "matched_efforts_count"
    ] == 0

    assert result["score"] < 45

    print(
        "DIFFERENT INTERVAL DURATION "
        "TEST PASSED"
    )


def test_heart_rate_does_not_affect_similarity():
    reference = make_interval_signature(
        heart_rate=145
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        heart_rate=170,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["score"] == 100

    assert result[
        "matched_efforts_count"
    ] == 5

    print(
        "HEART RATE INDEPENDENCE TEST PASSED"
    )


def test_race_vs_structured_workout():
    reference = make_interval_signature()

    candidate = make_interval_signature(
        activity_id="race",
        race=True,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == "ok"

    assert result[
        "matched_efforts_count"
    ] == 5

    assert result[
        "candidate_context"
    ] == "race"

    assert not result[
        "full_workout_comparison_candidate"
    ]

    assert result[
        "comparison_scope"
    ] == "matched_efforts_only"

    print(
        "RACE VS STRUCTURED WORKOUT "
        "TEST PASSED"
    )


def test_different_environment():
    reference = make_interval_signature(
        indoor=True
    )

    candidate = make_interval_signature(
        activity_id="outdoor",
        indoor=False,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["score"] == 100

    assert result["conditions"][
        "environment_comparable"
    ] is False

    assert (
        "different_environment"
        in result["limitations"]
    )

    assert not result[
        "full_workout_comparison_candidate"
    ]

    print("DIFFERENT ENVIRONMENT TEST PASSED")


def test_different_temperature():
    reference = make_interval_signature(
        temperature=20
    )

    candidate = make_interval_signature(
        activity_id="hot",
        temperature=29,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["conditions"][
        "temperature_difference_celsius"
    ] == 9

    assert (
        "different_temperature"
        in result["limitations"]
    )

    assert not result[
        "full_workout_comparison_candidate"
    ]

    print("DIFFERENT TEMPERATURE TEST PASSED")


def test_identical_endurance_workouts():
    reference = make_endurance_signature(
        "reference"
    )

    candidate = make_endurance_signature(
        "candidate"
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["score"] == 100

    assert result[
        "comparison_type"
    ] == "endurance"

    assert result[
        "comparison_scope"
    ] == "aerobic_segment_candidates"

    print(
        "IDENTICAL ENDURANCE WORKOUTS "
        "TEST PASSED"
    )


def test_mixed_endurance_family():
    signature = build_workout_signature(
        activity=make_activity(
            activity_id="mixed",
            name="Z2 + 1min Z4",
        ),

        records=make_records([
            (1800, 200),
            (60, 305),
            (1800, 200),
        ]),
    )

    assert get_comparison_family(
        signature
    ) == "endurance"

    print("MIXED ENDURANCE FAMILY TEST PASSED")


def test_endurance_vs_intervals():
    reference = make_endurance_signature(
        "reference"
    )

    candidate = make_interval_signature(
        activity_id="candidate"
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == (
        "not_comparable"
    )

    assert result[
        "comparison_scope"
    ] == "none"

    print("ENDURANCE VS INTERVALS TEST PASSED")


def test_effort_matching_without_duplicates():
    reference = make_interval_signature(
        repetitions=5
    )

    candidate = make_interval_signature(
        activity_id="candidate",
        repetitions=3,
    )

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    pairs = result["matched_efforts"]

    assert len(pairs) == 3

    reference_ids = [
        pair["reference_effort_id"]
        for pair in pairs
    ]

    candidate_ids = [
        pair["candidate_effort_id"]
        for pair in pairs
    ]

    assert len(reference_ids) == len(
        set(reference_ids)
    )

    assert len(candidate_ids) == len(
        set(candidate_ids)
    )

    print(
        "EFFORT MATCHING WITHOUT DUPLICATES "
        "TEST PASSED"
    )


def test_find_similar_workouts():
    reference = make_interval_signature(
        activity_id="reference"
    )

    identical = make_interval_signature(
        activity_id="identical",
        date="2026-11-20T10:00:00Z",
    )

    shorter = make_interval_signature(
        activity_id="shorter",
        repetitions=4,
        work_duration=60,
        recovery_duration=60,
        date="2026-11-18T10:00:00Z",
    )

    sprint = make_interval_signature(
        activity_id="sprint",
        repetitions=6,
        work_duration=20,
        work_power=550,
        date="2026-11-16T10:00:00Z",
    )

    endurance = make_endurance_signature(
        activity_id="endurance",
        date="2026-11-12T10:00:00Z",
    )

    result = find_similar_workout_signatures(
        reference=reference,
        candidates=[
            sprint,
            endurance,
            shorter,
            identical,
        ],
    )

    assert result["status"] == "ok"

    assert result[
        "evaluated_workouts_count"
    ] == 4

    assert result[
        "similar_workouts_count"
    ] == 2

    ids = [
        workout["candidate_activity_id"]
        for workout in result[
            "similar_workouts"
        ]
    ]

    assert ids == [
        "identical",
        "shorter",
    ]

    print("FIND SIMILAR WORKOUTS TEST PASSED")

    for workout in result[
        "similar_workouts"
    ]:
        print(
            workout["candidate_activity_id"],
            workout["score"],
            workout["similarity_level"],
        )


def test_history_period_filter():
    reference = make_interval_signature(
        activity_id="reference"
    )

    valid = make_interval_signature(
        activity_id="valid",
        date="2026-11-18T10:00:00Z",
    )

    old = make_interval_signature(
        activity_id="old",
        date="2026-10-01T10:00:00Z",
    )

    future = make_interval_signature(
        activity_id="future",
        date="2026-11-25T10:00:00Z",
    )

    result = find_similar_workout_signatures(
        reference=reference,
        candidates=[
            reference,
            valid,
            old,
            future,
            valid,
        ],
        days=30,
    )

    assert result[
        "similar_workouts_count"
    ] == 1

    assert result[
        "evaluated_workouts_count"
    ] == 1

    assert result[
        "skipped_workouts_count"
    ] == 2

    assert result["similar_workouts"][0][
        "candidate_activity_id"
    ] == "valid"

    print("HISTORY PERIOD FILTER TEST PASSED")


def test_no_similar_workouts():
    reference = make_interval_signature()

    candidate = make_interval_signature(
        activity_id="sprint",
        work_duration=20,
        work_power=550,
        date="2026-11-16T10:00:00Z",
    )

    result = find_similar_workout_signatures(
        reference,
        [candidate],
    )

    assert result["status"] == (
        "no_similar_workouts"
    )

    assert result[
        "similar_workouts"
    ] == []

    print("NO SIMILAR WORKOUTS TEST PASSED")


def test_insufficient_data():
    reference = make_interval_signature()

    candidate = {
        "status": "insufficient_data",
    }

    result = compare_workout_signatures(
        reference,
        candidate,
    )

    assert result["status"] == (
        "insufficient_data"
    )

    assert result["score"] is None

    print("INSUFFICIENT DATA TEST PASSED")


def test_original_signatures_preserved():
    reference = make_interval_signature()

    candidate = make_interval_signature(
        activity_id="candidate"
    )

    original_reference = deepcopy(
        reference
    )

    original_candidate = deepcopy(
        candidate
    )

    compare_workout_signatures(
        reference,
        candidate,
    )

    assert reference == original_reference

    assert candidate == original_candidate

    print(
        "ORIGINAL SIGNATURES PRESERVED "
        "TEST PASSED"
    )


if __name__ == "__main__":
    test_numeric_similarity()
    test_missing_weighted_component()
    test_identical_interval_workouts()
    test_different_warmup_duration()
    test_different_repetitions()
    test_realistic_375w_comparison()
    test_different_interval_power()
    test_different_interval_duration()
    test_heart_rate_does_not_affect_similarity()
    test_race_vs_structured_workout()
    test_different_environment()
    test_different_temperature()
    test_identical_endurance_workouts()
    test_mixed_endurance_family()
    test_endurance_vs_intervals()
    test_effort_matching_without_duplicates()
    test_find_similar_workouts()
    test_history_period_filter()
    test_no_similar_workouts()
    test_insufficient_data()
    test_original_signatures_preserved()

    print(
        "\nВсе тесты поиска похожих "
        "тренировок пройдены!"
    )