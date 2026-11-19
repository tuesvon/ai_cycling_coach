from pprint import pprint

from src.athletes.data_loader import get_registered_athlete_training
from src.athletes.activity_matching import match_activities


def test_activity_matching():
    result = get_registered_athlete_training(
        athlete_id="i280488",
        days=30
    )

    intervals = result["sources"]["intervals"]
    garmin = result["sources"]["garmin"]

    matching = match_activities(
        intervals,
        garmin,
        time_tolerance=60
    )

    print("\n=== MATCHING STATISTICS ===")
    pprint(matching["statistics"])

    print("\n=== MATCHED ACTIVITIES ===")
    for pair in matching["matches"]:
        print(
            pair["intervals"].get("name"),
            "|",
            pair["time_difference_seconds"],
            "sec",
            "|",
            pair["duration_difference_seconds"],
            "sec",
        )

    print("\n=== UNMATCHED INTERVALS ===")
    pprint(matching["unmatched_intervals"])

    print("\n=== UNMATCHED GARMIN ===")
    pprint(matching["unmatched_garmin"])

    # Проверяем структуру одной полноценной активности
    pair = next(
        pair for pair in matching["matches"]
        if pair["intervals"].get("name")
    )

    print("\n=== INTERVALS ACTIVITY FIELDS ===")
    pprint(pair["intervals"])

    print("\n=== GARMIN ACTIVITY FIELDS ===")
    pprint(pair["garmin"])


if __name__ == "__main__":
    test_activity_matching()