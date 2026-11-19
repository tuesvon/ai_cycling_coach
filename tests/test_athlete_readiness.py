
from pprint import pprint

from src.analytics.athlete_status import get_registered_athlete_status
from src.analytics.athlete_readiness import evaluate_readiness


def test_athlete_readiness():
    status = get_registered_athlete_status("i280488")

    readiness = evaluate_readiness(status)

    print("\n=== ATHLETE READINESS ===")
    pprint(readiness)


if __name__ == "__main__":
    test_athlete_readiness()
