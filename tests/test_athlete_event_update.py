
from pprint import pprint

from src.athletes.athlete_events import (
    get_athlete_events,
    update_athlete_event
)


def test_update_athlete_event():
    events = get_athlete_events("i280488")

    if not events:
        print("События не найдены")
        return

    event_id = events[0]["event_id"]

    updated_events = update_athlete_event(
        athlete_id="i280488",
        event_id=event_id,
        end_date="2026-12-16",
        description="Отпуск продлён до 16 декабря"
    )

    print("\n=== UPDATED EVENTS ===")
    pprint(updated_events)


if __name__ == "__main__":
    test_update_athlete_event()
