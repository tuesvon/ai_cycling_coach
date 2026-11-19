
from pprint import pprint

from src.athletes.data_loader import (
    get_registered_athlete_training,
    match_activities,
)


def test_data_loader():
    print("Получаем активности...")

    result = get_registered_athlete_training(
        athlete_id="i280488",
        days=30,
    )

    intervals = result["sources"]["intervals"]
    garmin = result["sources"]["garmin"]

    deduplication = match_activities(intervals, garmin)

    print("\n=== DEDUPLICATION RESULT ===")
    pprint(deduplication["statistics"])

    print("\n=== MATCHED ACTIVITIES ===")

    for match in deduplication["matches"]:
        intervals_activity = match["intervals"]

        print(
            intervals_activity.get("name"),
            "|",
            intervals_activity.get("start_date_local"),
            "|",
            f"разница: {match['time_difference_seconds']} сек."
        )

    print("\n=== UNMATCHED INTERVALS ===")
    pprint(deduplication["unmatched_intervals"])

    print("\n=== UNMATCHED GARMIN ===")
    pprint(deduplication["unmatched_garmin"])


if __name__ == "__main__":
    test_data_loader()