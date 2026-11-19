
from pprint import pprint

from src.athletes.athlete_events import get_athlete_events


def test_get_athlete_events():
    events = get_athlete_events(
        athlete_id="i280488"
    )

    print("\n=== ATHLETE EVENTS ===")
    pprint(events)


if __name__ == "__main__":
    test_get_athlete_events()
