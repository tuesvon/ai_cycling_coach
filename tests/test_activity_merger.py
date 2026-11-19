
from pprint import pprint

from src.athletes.data_loader import get_registered_athlete_training
from src.athletes.activity_matching import match_activities
from src.athletes.activity_merger import build_unified_activities


def test_activity_merger():
    result = get_registered_athlete_training(
        athlete_id="i280488",
        days=30
    )

    matching = match_activities(
        result["sources"]["intervals"],
        result["sources"]["garmin"],
        time_tolerance=60
    )

    activities = build_unified_activities(matching)

    print("\n=== UNIFIED STATISTICS ===")
    print("Intervals:", len(result["sources"]["intervals"]))
    print("Garmin:", len(result["sources"]["garmin"]))
    print("Unified:", len(activities))

    print("\n=== FIRST UNIFIED ACTIVITY ===")
    pprint(activities[0])

    print("\n=== NORMALIZED FIELDS ===")
    for key in (
        "name",
        "start_date",
        "duration",
        "activity_type",
        "tss",
        "garmin_load",
        "average_power",
        "normalized_power",
        "average_hr",
        "distance",
    ):
        print(f"{key}: {activities[0].get(key)}")


if __name__ == "__main__":
    test_activity_merger()
