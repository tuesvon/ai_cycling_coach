
from pprint import pprint

from src.athletes.athlete_manager import get_registered_athlete_wellness
from src.analytics.recovery import aggregate_sleep


def test_readiness_data():
    athlete_id = "i280488"

    wellness = get_registered_athlete_wellness(
        athlete_id=athlete_id,
        days=30
    )

    print("\n=== RECOVERY: 7 DAYS ===")
    pprint(aggregate_sleep(wellness, 7))

    print("\n=== RECOVERY: 30 DAYS ===")
    pprint(aggregate_sleep(wellness, 30))

    print("\n=== LAST 14 DAYS: DAILY DATA ===")

    for entry in sorted(
        wellness,
        key=lambda item: item.get("id", "")
    )[-14:]:
        print({
            "date": entry.get("id"),
            "sleep_hours": (
                round(entry["sleepSecs"] / 3600, 2)
                if entry.get("sleepSecs") is not None else None
            ),
            "sleep_score": entry.get("sleepScore"),
            "hrv": entry.get("hrv"),
            "resting_hr": entry.get("restingHR"),
            "atl": entry.get("atl"),
            "ctl": entry.get("ctl"),
            "ramp_rate": entry.get("rampRate"),
        })


if __name__ == "__main__":
    test_readiness_data()
