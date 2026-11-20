
from pprint import pprint

from src.analytics.training_trends import analyze_training_trends


def test_increasing_training_trend():
    history = {
        "periods": {
            "7_days": {
                "cycling_sessions_per_week": 6.0,
                "cycling_duration_hours": 8.0,
                "cycling_activities_count": 6,
            },
            "30_days": {
                "cycling_sessions_per_week": 5.0,
                "cycling_duration_hours": 22.0,
                "cycling_activities_count": 22,
            },
            "90_days": {
                "cycling_sessions_per_week": 4.0,
                "cycling_duration_hours": 75.0,
                "cycling_activities_count": 52,
            },
        }
    }

    result = analyze_training_trends(history)

    pprint(result)

    assert result["overall_trend"] == "increasing"
    assert result["comparison"]["short_vs_medium_sessions"] == 1.0
    assert result["comparison"]["medium_vs_long_sessions"] == 1.0

    print("Тест возрастающей регулярности пройден!")


def test_decreasing_training_trend():
    history = {
        "periods": {
            "7_days": {
                "cycling_sessions_per_week": 3.0,
                "cycling_duration_hours": 4.0,
                "cycling_activities_count": 3,
            },
            "30_days": {
                "cycling_sessions_per_week": 4.0,
                "cycling_duration_hours": 18.0,
                "cycling_activities_count": 18,
            },
            "90_days": {
                "cycling_sessions_per_week": 5.0,
                "cycling_duration_hours": 70.0,
                "cycling_activities_count": 65,
            },
        }
    }

    result = analyze_training_trends(history)

    assert result["overall_trend"] == "decreasing"

    print("Тест снижающейся регулярности пройден!")


def test_mixed_training_trend():
    history = {
        "periods": {
            "7_days": {
                "cycling_sessions_per_week": 5.0,
                "cycling_duration_hours": 7.0,
                "cycling_activities_count": 5,
            },
            "30_days": {
                "cycling_sessions_per_week": 4.0,
                "cycling_duration_hours": 18.0,
                "cycling_activities_count": 17,
            },
            "90_days": {
                "cycling_sessions_per_week": 5.0,
                "cycling_duration_hours": 65.0,
                "cycling_activities_count": 64,
            },
        }
    }

    result = analyze_training_trends(history)

    assert result["overall_trend"] == "stable_or_mixed"

    print("Тест смешанной динамики пройден!")


def test_insufficient_training_data():
    history = {
        "periods": {
            "7_days": None,
            "30_days": None,
            "90_days": None,
        }
    }

    result = analyze_training_trends(history)

    assert result["overall_trend"] == "insufficient_data"

    print("Тест недостатка данных пройден!")


if __name__ == "__main__":
    print("\n=== INCREASING TREND ===")
    test_increasing_training_trend()

    print("\n=== DECREASING TREND ===")
    test_decreasing_training_trend()

    print("\n=== MIXED TREND ===")
    test_mixed_training_trend()

    print("\n=== INSUFFICIENT DATA ===")
    test_insufficient_training_data()

    print("\nВсе тесты training_trends успешно пройдены!")
