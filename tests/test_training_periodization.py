
from src.assistant.training_periodization import (
    calculate_preparation_window,
    build_preparation_calendar,
)


def test_training_periodization():
    window = calculate_preparation_window(
        event_date="2027-06-20",
        start_date="2026-11-23",
    )

    assert window["preparation_days"] == 209
    assert window["full_weeks"] == 29
    assert window["remaining_days"] == 6

    print("PREPARATION WINDOW TEST PASSED")

    calendar = build_preparation_calendar(
        event_date="2027-06-20",
        start_date="2026-11-23",
    )

    weeks = calendar["weeks"]

    assert len(weeks) == 30
    assert weeks[0]["start_date"] == "2026-11-23"
    assert weeks[0]["end_date"] == "2026-11-29"

    assert weeks[-1]["start_date"] == "2027-06-14"
    assert weeks[-1]["end_date"] == "2027-06-19"
    assert weeks[-1]["days"] == 6

    assert sum(week["days"] for week in weeks) == 209

    print("PREPARATION CALENDAR TEST PASSED")

    short_calendar = build_preparation_calendar(
        event_date="2027-01-04",
        start_date="2027-01-01",
    )

    assert short_calendar["total_calendar_weeks"] == 1
    assert short_calendar["weeks"][0]["days"] == 3

    print("SHORT PREPARATION TEST PASSED")

    try:
        calculate_preparation_window(
            event_date="2027-01-01",
            start_date="2027-01-01",
        )
    except ValueError:
        print("INVALID EVENT DATE TEST PASSED")
    else:
        raise AssertionError(
            "Одинаковые даты не были отклонены"
        )

    try:
        calculate_preparation_window(
            event_date="2027-01-01",
            start_date="2027-02-01",
        )
    except ValueError:
        print("PAST EVENT TEST PASSED")
    else:
        raise AssertionError(
            "Прошедшее событие не было отклонено"
        )

    print("Все тесты календаря подготовки пройдены!")


if __name__ == "__main__":
    test_training_periodization()
