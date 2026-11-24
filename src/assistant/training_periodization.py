from datetime import date, datetime, timedelta


def parse_event_date(value):
    """
    Преобразует дату соревнования в date.
    """
    if isinstance(value, datetime):
        raise ValueError("Нужна дата без времени")

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                "Дата должна быть в формате YYYY-MM-DD"
            ) from error

    raise ValueError("Некорректная дата соревнования")


def calculate_preparation_window(event_date, start_date=None):
    """
    Рассчитывает оставшееся время до главной гонки.

    День соревнования не считается тренировочным днём.
    """
    event_date = parse_event_date(event_date)

    if start_date is None:
        start_date = date.today()
    else:
        start_date = parse_event_date(start_date)

    if event_date <= start_date:
        raise ValueError(
            "Дата соревнования должна быть позже начала подготовки"
        )

    days = (event_date - start_date).days

    return {
        "start_date": start_date.isoformat(),
        "event_date": event_date.isoformat(),
        "preparation_days": days,
        "full_weeks": days // 7,
        "remaining_days": days % 7,
        "weeks_exact": round(days / 7, 2),
    }


def build_preparation_calendar(
    event_date,
    start_date=None,
):
    """
    Создаёт календарные недели подготовки.

    Это НЕ тренировочный план и НЕ периодизация.
    Типы блоков позже определит Gemma.
    """
    window = calculate_preparation_window(
        event_date=event_date,
        start_date=start_date,
    )

    start = date.fromisoformat(window["start_date"])
    event = date.fromisoformat(window["event_date"])

    weeks = []
    current = start
    week_number = 1

    while current < event:
        end = min(
            current + timedelta(days=6),
            event - timedelta(days=1),
        )

        weeks.append({
            "week_number": week_number,
            "start_date": current.isoformat(),
            "end_date": end.isoformat(),
            "days": (end - current).days + 1,
            "phase": None,
        })

        current = end + timedelta(days=1)
        week_number += 1

    return {
        "window": window,
        "weeks": weeks,
        "total_calendar_weeks": len(weeks),
    }