
from io import BytesIO

import requests
from fitparse import FitFile

from src.athletes.credentials import (
    get_api_key as get_stored_api_key,
)
from src.integrations.intervals_api import (
    get_activities,
    get_athlete_profile,
    download_activity_fit,
)


def test_real_intervals_fit():
    athlete_id = "i280488"

    print("Получаем API-ключ спортсмена...")

    api_key = get_stored_api_key(
        athlete_id,
        "intervals",
    )

    if not api_key:
        raise ValueError(
            "API-ключ зарегистрированного спортсмена не найден"
        )

    print("\n=== INTERVALS ACCOUNT ===")

    profile = get_athlete_profile(api_key=api_key)

    print("ID аккаунта:", profile.get("id"))
    print("Имя:", profile.get("name"))
    print("Ожидаемый ID:", athlete_id)

    assert str(profile.get("id")) == athlete_id, (
        "API-ключ принадлежит другому спортсмену"
    )

    print("\nПолучаем последние тренировки...")

    try:
        activities = get_activities(
            days=30,
            api_key=api_key,
        )

    except requests.exceptions.RequestException as error:
        raise AssertionError(
            f"Ошибка получения тренировок: {error}"
        ) from error

    print("\n=== ACTIVITIES DIAGNOSTICS ===")
    print("Всего активностей:", len(activities))

    if not activities:
        raise AssertionError(
            "Intervals.icu не вернул активности"
        )

    activities.sort(
        key=lambda activity: (
            activity.get("start_date_local")
            or activity.get("start_date")
            or ""
        ),
        reverse=True,
    )

    print("\n=== INCOMPLETE ACTIVITIES ===")

    incomplete = [
        activity
        for activity in activities
        if not activity.get("type")
    ]

    print(
        "Количество неполных записей:",
        len(incomplete),
    )

    for activity in incomplete[:10]:
        print(
            "\nДата:",
            activity.get("start_date_local"),
        )
        print("ID:", activity.get("id"))
        print("Source:", activity.get("source"))
        print("Note:", activity.get("_note"))
        print(
            "Athlete:",
            activity.get("icu_athlete_id"),
        )

    cycling_types = {
        "Ride",
        "VirtualRide",
        "GravelRide",
        "MountainBikeRide",
    }

    cycling_activities = [
        activity
        for activity in activities
        if activity.get("type") in cycling_types
    ]

    print("\n=== LAST 5 CYCLING ACTIVITIES ===")

    for activity in cycling_activities[:5]:
        print(
            activity.get("start_date_local"),
            "|",
            activity.get("name"),
            "| ID:",
            activity.get("id"),
        )

    if not cycling_activities:
        raise AssertionError(
            "Не найдены велосипедные тренировки "
            "с заполненным полем type"
        )

    activity = cycling_activities[0]

    print("\n=== FIT DOWNLOAD ===")
    print("Тренировка:", activity.get("name"))
    print("ID:", activity.get("id"))

    content = download_activity_fit(
        activity_id=activity["id"],
        api_key=api_key,
    )

    print("Размер файла:", len(content), "байт")

    fit_file = FitFile(BytesIO(content))

    records = list(
        fit_file.get_messages("record")
    )

    print("Количество FIT-записей:", len(records))

    assert records, (
        "В FIT-файле отсутствуют записи"
    )

    first_record = {
        field.name: field.value
        for field in records[0]
        if field.value is not None
    }

    print("\n=== FIRST FIT RECORD ===")

    for field_name in (
        "timestamp",
        "power",
        "heart_rate",
        "cadence",
    ):
        print(
            field_name,
            ":",
            first_record.get(field_name),
        )

    print("\nREAL INTERVALS FIT TEST PASSED")


if __name__ == "__main__":
    test_real_intervals_fit()