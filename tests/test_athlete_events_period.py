
from pprint import pprint

from src.athletes.athlete_events import get_athlete_events


athlete_id = "i280488"

print("\n=== DECEMBER 2026 ===")
december_events = get_athlete_events(
    athlete_id,
    start_date="2026-12-10",
    end_date="2026-12-20"
)
pprint(december_events)

print("\n=== NOVEMBER 2026 ===")
november_events = get_athlete_events(
    athlete_id,
    start_date="2026-11-01",
    end_date="2026-11-30"
)
pprint(november_events)

print("\n=== JANUARY 2027 ===")
january_events = get_athlete_events(
    athlete_id,
    start_date="2027-01-01",
    end_date="2027-01-31"
)
pprint(january_events)

assert len(december_events) == 1
assert december_events[0]["event_type"] == "vacation"
assert november_events == []
assert january_events == []

print("\nВсе проверки успешно пройдены!")
