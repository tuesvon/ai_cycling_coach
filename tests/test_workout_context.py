
from copy import deepcopy

from src.analytics.workout_context import (
    classify_workout_context,
)


def test_structured_intervals():
    activity = {
        "name": "5x1:30@375W",
    }

    result = classify_workout_context(
        activity
    )

    assert result["status"] == "ok"

    assert result["activity_context"] == (
        "structured_workout"
    )

    assert result["confidence"] == "medium"

    print("STRUCTURED INTERVALS TEST PASSED")


def test_structured_microintervals():
    activity = {
        "name": "2x14x0:10@540W",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "structured_workout"
    )

    print(
        "STRUCTURED MICROINTERVALS TEST PASSED"
    )


def test_structured_endurance():
    activity = {
        "name": "146m@175w",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "structured_workout"
    )

    print("STRUCTURED ENDURANCE TEST PASSED")


def test_mixed_endurance():
    activity = {
        "name": "Z2 + 1min z4",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "structured_workout"
    )

    print("MIXED ENDURANCE TEST PASSED")


def test_race_name():
    activity = {
        "name": (
            "Zwift - Race: Stage 1 - "
            "Zwift Crit Club"
        ),
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "race"
    )

    assert result["confidence"] == "medium"

    print("RACE NAME TEST PASSED")


def test_zrace():
    activity = {
        "name": "ZRace",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "race"
    )

    print("ZRACE TEST PASSED")


def test_race_metadata():
    activity = {
        "name": "Zwift - Watopia",

        "sources": {
            "intervals": {
                "race": True,
            },
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "race"
    )

    assert result["confidence"] == "high"

    assert "intervals.race" in (
        result["evidence"]
    )

    print("RACE METADATA TEST PASSED")


def test_pre_race_warmup():
    activity = {
        "name": (
            "Zwift - INEOS Grenadiers "
            "Virtual Training Camp | "
            "The Pre-Race Warm-up"
        ),
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "warmup"
    )

    print("PRE RACE WARMUP TEST PASSED")


def test_post_race_cooldown():
    activity = {
        "name": "Zwift - Post-Race Cooldown",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "cooldown"
    )

    print("POST RACE COOLDOWN TEST PASSED")


def test_group_ride():
    activity = {
        "name": (
            "Zwift - Pacer Group Ride "
            "with Bernie"
        ),
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "group_ride"
    )

    print("GROUP RIDE TEST PASSED")


def test_free_ride():
    activity = {
        "name": "Zwift - Free Ride",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "free_ride"
    )

    print("FREE RIDE TEST PASSED")


def test_unknown_activity():
    activity = {
        "name": "Zwift - Watopia",
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "unknown"
    )

    assert result["confidence"] == "low"

    print("UNKNOWN ACTIVITY TEST PASSED")


def test_paired_event_without_context():
    activity = {
        "name": "Morning Ride",

        "sources": {
            "intervals": {
                "paired_event_id": 123456,
            },
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "unknown"
    )

    assert result["has_paired_event"] is True

    assert "paired_event" in (
        result["evidence"]
    )

    print(
        "PAIRED EVENT WITHOUT CONTEXT TEST PASSED"
    )


def test_paired_structured_workout():
    activity = {
        "name": "3x7:00@305W",

        "sources": {
            "intervals": {
                "paired_event_id": 123456,
            },
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "structured_workout"
    )

    assert result["has_paired_event"] is True

    print(
        "PAIRED STRUCTURED WORKOUT TEST PASSED"
    )


def test_conflicting_metadata():
    activity = {
        "name": "Pre-Race Warm-up",

        "sources": {
            "intervals": {
                "race": True,
            },
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "unknown"
    )

    assert result["confidence"] == "low"

    assert result["conflicting_evidence"]

    print("CONFLICTING METADATA TEST PASSED")


def test_missing_name():
    activity = {}

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "unknown"
    )

    print("MISSING NAME TEST PASSED")


def test_russian_activity_names():
    cases = [
        ("Разминка перед гонкой", "warmup"),
        ("Вечерняя гонка", "race"),
        ("Заминка после гонки", "cooldown"),
        ("Групповая поездка", "group_ride"),
        ("Пороговые интервалы", "structured_workout"),
    ]

    for name, expected in cases:
        result = classify_workout_context({
            "name": name,
        })

        assert result[
            "activity_context"
        ] == expected, (
            name,
            result,
        )

    print("RUSSIAN ACTIVITY NAMES TEST PASSED")


def test_garmin_name_fallback():
    activity = {
        "sources": {
            "garmin": {
                "activityName": (
                    "Zwift - Race"
                ),
            },
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "race"
    )

    print("GARMIN NAME FALLBACK TEST PASSED")


def test_invalid_source_metadata():
    activity = {
        "name": "5x1:30@375W",

        "sources": {
            "intervals": None,
            "garmin": None,
        },
    }

    result = classify_workout_context(
        activity
    )

    assert result["activity_context"] == (
        "structured_workout"
    )

    print(
        "INVALID SOURCE METADATA TEST PASSED"
    )


def test_original_activity_preserved():
    activity = {
        "name": "5x1:30@375W",

        "sources": {
            "intervals": {
                "paired_event_id": 123456,
            },
        },
    }

    original = deepcopy(activity)

    classify_workout_context(
        activity
    )

    assert activity == original

    print(
        "ORIGINAL ACTIVITY PRESERVED TEST PASSED"
    )


if __name__ == "__main__":
    test_structured_intervals()
    test_structured_microintervals()
    test_structured_endurance()
    test_mixed_endurance()
    test_race_name()
    test_zrace()
    test_race_metadata()
    test_pre_race_warmup()
    test_post_race_cooldown()
    test_group_ride()
    test_free_ride()
    test_unknown_activity()
    test_paired_event_without_context()
    test_paired_structured_workout()
    test_conflicting_metadata()
    test_missing_name()
    test_russian_activity_names()
    test_garmin_name_fallback()
    test_invalid_source_metadata()
    test_original_activity_preserved()

    print(
        "\nВсе тесты определения "
        "контекста тренировок пройдены!"
    )
