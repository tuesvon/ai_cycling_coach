
from src.analytics.workout_comparison import (
    is_similar_workout,
    find_similar_workouts,
    compare_workout_heart_rate,
    analyze_latest_workout,
)


LATEST = {
    "id": "latest",
    "start_date": "2027-03-15T10:00:00+00:00",
    "type": "cycling",
    "duration_seconds": 3600,
    "average_power": 200,
    "average_hr": 137,
}


ACTIVITIES = [
    {
        "id": "old_1",
        "start_date": "2027-03-01T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 145,
    },
    {
        "id": "old_2",
        "start_date": "2027-02-25T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3900,
        "average_power": 205,
        "average_hr": 143,
    },
    {
        "id": "too_hard",
        "start_date": "2027-03-05T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 280,
        "average_hr": 165,
    },
    {
        "id": "too_old",
        "start_date": "2027-01-01T10:00:00+00:00",
        "type": "cycling",
        "duration_seconds": 3600,
        "average_power": 200,
        "average_hr": 150,
    },
]


def test_workout_comparison():
    assert is_similar_workout(
        LATEST,
        ACTIVITIES[0],
    )

    assert not is_similar_workout(
        LATEST,
        ACTIVITIES[2],
    )

    print("WORKOUT SIMILARITY TEST PASSED")

    similar = find_similar_workouts(
        LATEST,
        ACTIVITIES,
        days=30,
    )

    assert len(similar) == 2

    assert {
        workout["id"]
        for workout in similar
    } == {"old_1", "old_2"}

    print("SIMILAR WORKOUT SEARCH TEST PASSED")

    comparison = compare_workout_heart_rate(
        LATEST,
        similar,
    )

    assert comparison["status"] == "ok"
    assert comparison["latest_average_hr"] == 137
    assert comparison["previous_average_hr"] == 144
    assert comparison["difference_bpm"] == -7
    assert comparison["quality"] == "limited"

    print("HEART RATE COMPARISON TEST PASSED")

    result = analyze_latest_workout(
        LATEST,
        ACTIVITIES,
    )

    assert result["similar_workouts_found"] == 2
    assert result["heart_rate_comparison"][
        "difference_bpm"
    ] == -7

    print("LATEST WORKOUT ANALYSIS TEST PASSED")

    missing_hr = dict(LATEST)
    missing_hr["average_hr"] = None

    result = compare_workout_heart_rate(
        missing_hr,
        similar,
    )

    assert result["status"] == "insufficient_data"

    print("MISSING HEART RATE TEST PASSED")

    print("Все тесты сравнения тренировок пройдены!")


if __name__ == "__main__":
    test_workout_comparison()
