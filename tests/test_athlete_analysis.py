
from pprint import pprint

from src.analytics.athlete_analysis import build_athlete_analysis


def test_build_athlete_analysis():
    status = {
        "profile": {
            "ftp": 304,
            "weight": 76.5,
        },
        "recovery": {
            "7_days": {
                "average_sleep_score": 89.3,
                "latest_sleep": {
                    "sleep_hours": 7.5,
                    "sleep_score": 90,
                },
                "latest_recovery": {
                    "hrv": 90,
                    "resting_hr": 38,
                    "atl": 50,
                    "ctl": 52,
                    "ramp_rate": 0.2,
                },
            },
            "30_days": {
                "average_sleep_score": 86.5,
                "average_hrv": 82,
                "average_resting_hr": 40,
            },
        },
        "training_history": {
            "last_ride_date": "2026-11-18",
            "days_since_last_ride": 1,
        },
    }

    result = build_athlete_analysis(status)

    pprint(result, sort_dicts=False)

    assert "readiness" in result
    assert result["readiness"]["overall"] == "good"

    assert "profile" in result
    assert "recovery" in result
    assert "training_history" in result

    assert result["profile"]["ftp"] == 304

    print("Тест формирования аналитического контекста пройден!")


if __name__ == "__main__":
    test_build_athlete_analysis()

    print("\nВсе тесты athlete_analysis пройдены!")