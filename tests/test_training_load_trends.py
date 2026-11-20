from datetime import datetime, timedelta, timezone
from pprint import pprint

from src.analytics.training_load_trends import (
    analyze_training_load_trends,
)


def create_activity(days_ago, activity_type, tss, garmin_load):
    start_date = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat()

    return {
        "start_date": start_date,
        "activity_type": activity_type,
        "duration": 3600,
        "tss": tss,
        "garmin_load": garmin_load,
    }


def test_increasing_training_load():
    activities = [
        create_activity(2, "cycling", 120, 120),
        create_activity(10, "cycling", 100, 100),
        create_activity(20, "cycling", 130, 130),
        create_activity(3, "walking", 500, 500),
    ]

    result = analyze_training_load_trends(activities)

    pprint(result, sort_dicts=False)

    assert result["comparison"]["tss"]["trend"] == "increasing"
    assert result["comparison"]["garmin_load"]["trend"] == "increasing"

    assert (
        result["comparison"]["tss"]["data_quality"]
        ["recent_7_days"]["status"] == "complete"
    )

    print("Тест возрастающей нагрузки пройден!")


def test_insufficient_training_load():
    activities = [
        create_activity(2, "cycling", None, 100),
    ]

    result = analyze_training_load_trends(activities)

    assert result["comparison"]["tss"]["trend"] == "insufficient_data"
    assert result["comparison"]["garmin_load"]["trend"] == "insufficient_data"

    assert (
        result["comparison"]["tss"]["data_quality"]
        ["recent_7_days"]["status"] == "missing"
    )

    print("Тест недостатка данных пройден!")


def test_partial_data_coverage():
    activities = [
        create_activity(2, "cycling", 100, 100),
        create_activity(3, "cycling", None, 100),
        create_activity(10, "cycling", 100, 100),
    ]

    result = analyze_training_load_trends(activities)

    assert result["comparison"]["tss"]["trend"] == "insufficient_data"
    assert result["comparison"]["garmin_load"]["trend"] == "increasing"

    tss_coverage = (
        result["comparison"]["tss"]["data_quality"]["recent_7_days"]
    )

    assert tss_coverage["coverage_percent"] == 50.0
    assert tss_coverage["status"] == "partial"

    print("Тест неполных данных пройден!")


if __name__ == "__main__":
    print("\n=== INCREASING TRAINING LOAD ===")
    test_increasing_training_load()

    print("\n=== INSUFFICIENT TRAINING LOAD ===")
    test_insufficient_training_load()

    print("\n=== PARTIAL DATA COVERAGE ===")
    test_partial_data_coverage()

    print("\nВсе тесты training_load_trends пройдены!")