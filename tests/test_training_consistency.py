
from pprint import pprint

from src.athletes.data_loader import (
    get_registered_athlete_unified_training
)

from src.analytics.training_consistency import analyze_training_gaps


def test_training_consistency():
    training_data = get_registered_athlete_unified_training(
        athlete_id="i280488",
        days=90
    )

    activities = training_data["activities"]

    result = analyze_training_gaps(activities)

    print("\n=== TRAINING CONSISTENCY ===")
    pprint(result)


if __name__ == "__main__":
    test_training_consistency()
