from getpass import getpass

import requests

from src.athletes.athlete_manager import register_athlete


def main():
    print("=== REAL ATHLETE REGISTRATION ===")
    print("Регистрация спортсмена через Intervals.icu")
    print()

    api_key = getpass("Введите API-ключ Intervals.icu: ").strip()

    if not api_key:
        print("API-ключ не введён.")
        return

    print()
    print("Проверяем подключение к Intervals.icu...")

    try:
        athlete = register_athlete(
            api_key=api_key,
            telegram_id=None
        )

    except requests.RequestException as error:
        print("Ошибка подключения к Intervals.icu.")
        print("Проверьте API-ключ и интернет-соединение.")
        print("Техническая информация:", error)
        return

    except ValueError as error:
        print("Ошибка регистрации:", error)
        return

    print()
    print("Спортсмен успешно зарегистрирован!")
    print()
    print("=== ATHLETE PROFILE ===")
    print("Athlete ID:", athlete["athlete_id"])
    print("Intervals ID:", athlete["intervals_athlete_id"])
    print("Name:", athlete["name"])
    print("Telegram ID:", athlete["telegram_id"])
    print("Data sources:", athlete["data_sources"])
    print()
    print("Профиль сохранён в SQLite.")
    print("API-ключ сохранён в зашифрованном виде.")


if __name__ == "__main__":
    main()