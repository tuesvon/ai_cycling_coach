
from src.athletes.data_loader import (
    get_registered_athlete_unified_training
)


def test_unified_data_loader():
    result = get_registered_athlete_unified_training(
        athlete_id="i280488",
        days=30
    )

    print("\n=== UNIFIED LOADER STATISTICS ===")
    print(result["statistics"])

    print("\n=== TOTAL ACTIVITIES ===")
    print(len(result["activities"]))

    print("\n=== RECENT ACTIVITIES ===")

    for activity in result["activities"][:5]:
        print(
            activity.get("start_date"),
            "|",
            activity.get("name"),
            "|",
            activity.get("activity_type"),
            "| TSS:",
            activity.get("tss"),
            "| Garmin Load:",
            activity.get("garmin_load")
        )


if __name__ == "__main__":
    test_unified_data_loader()