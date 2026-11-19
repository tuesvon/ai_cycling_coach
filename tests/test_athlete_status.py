from pprint import pprint

from src.analytics.athlete_status import build_athlete_status

from src.athletes.athlete_manager import (
    get_registered_athlete_wellness,
    get_registered_athlete_activities
)


def test_athlete_status():
    print("Получаем активности Garmin...")
    garmin_activities = get_registered_athlete_activities(
        athlete_id="i280488",
        days=30
    )

    print("Получаем данные восстановления Intervals.icu...")
    wellness_data = get_registered_athlete_wellness(
        athlete_id="i280488",
        days=30
    )

    normalized_activities = []

    for activity in garmin_activities:
        timestamp = activity.get("beginTimestamp")

        if timestamp is None:
            continue

        normalized_activities.append({
            "start_date": timestamp / 1000,
            "duration": activity.get("duration", 0),
            "tss": None,
            "garmin_load": activity.get("activityTrainingLoad"),
            "activity_type": activity.get("activityType", {}).get("typeKey")
        })

    status = build_athlete_status(
        athlete_id="i280488",
        activities=normalized_activities,
        wellness_data=wellness_data
    )

    print("\n=== ATHLETE STATUS ===")
    pprint(status, sort_dicts=False)


if __name__ == "__main__":
    test_athlete_status()