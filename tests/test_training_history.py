
from pprint import pprint

from src.analytics.athlete_status import (
    get_registered_athlete_status
)


def test_training_history():
    status = get_registered_athlete_status("i280488")

    print("\n=== TRAINING HISTORY ===")
    pprint(status["training_history"])


if __name__ == "__main__":
    test_training_history()
