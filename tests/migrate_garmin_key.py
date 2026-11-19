import os

from dotenv import load_dotenv

from src.athletes.credentials import save_api_key, get_api_key

load_dotenv()

ATHLETE_ID = "i280488"


def main():
    print("1. Читаем Garmin API-ключ из .env...")

    api_key = os.getenv("GARMIN_PERSONAL_API_KEY")

    if not api_key:
        print("Garmin API-ключ не найден в .env.")
        return

    print("2. Сохраняем ключ в зашифрованном виде...")

    save_api_key(
        athlete_id=ATHLETE_ID,
        provider="garmin",
        api_key=api_key
    )

    print("3. Проверяем восстановление ключа...")

    restored_key = get_api_key(
        athlete_id=ATHLETE_ID,
        provider="garmin"
    )

    assert restored_key == api_key

    print("Garmin API-ключ успешно сохранён и проверен.")
    print("Сам ключ не выводился на экран.")

    from src.athletes.athlete_manager import get_registered_athlete_activities

    activities = get_registered_athlete_activities(
        athlete_id=ATHLETE_ID,
        days=7
    )

    print(f"Успешно загружено активностей: {len(activities)}")


if __name__ == "__main__":
    main()
