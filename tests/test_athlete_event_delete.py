
from pprint import pprint

from src.athletes.athlete_events import (
    add_athlete_event,
    delete_athlete_event,
    get_athlete_events
)


def test_delete_athlete_event():
    # Создаём временное тестовое событие.
    event = add_athlete_event(
        athlete_id="i280488",
        event_type="other",
        start_date="2026-11-20",
        description="Тестовое событие для проверки удаления"
    )

    event_id = event["event_id"]

    print("\n=== CREATED TEST EVENT ===")
    pprint(event)

    # Удаляем тестовое событие.
    deleted = delete_athlete_event(
        athlete_id="i280488",
        event_id=event_id
    )

    print("\n=== DELETE RESULT ===")
    print(deleted)

    # Проверяем, что событие исчезло.
    events = get_athlete_events("i280488")

    remaining_event = any(
        item["event_id"] == event_id
        for item in events
    )

    print("\n=== EVENT EXISTS AFTER DELETE ===")
    print(remaining_event)


if __name__ == "__main__":
    test_delete_athlete_event()
