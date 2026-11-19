from unittest.mock import patch

from src.athletes.athlete_manager import (
    register_athlete,
    get_athlete,
    get_all_athletes,
    delete_athlete
)


def test_athlete_registration():
    test_api_key = "test_intervals_key_123"
    test_athlete_id = "test_i12345"
    test_telegram_id = 999999999

    fake_athlete_data = {
        "id": test_athlete_id,
        "name": "Test Athlete",
        "weight": 70,
        "height": 175,
        "ftp": 250
    }

    try:
        print("1. Проверяем регистрацию...")

        with patch(
            "src.athletes.athlete_manager.get_athlete_data",
            return_value=fake_athlete_data
        ) as mock_api:

            athlete = register_athlete(
                api_key=test_api_key,
                telegram_id=test_telegram_id
            )

            mock_api.assert_called_once_with(api_key=test_api_key)

        assert athlete["athlete_id"] == test_athlete_id
        assert athlete["name"] == "Test Athlete"
        assert athlete["registered"] is True

        print("Регистрация прошла успешно.")

        print("2. Проверяем получение профиля...")

        saved_athlete = get_athlete(test_athlete_id)

        assert saved_athlete is not None
        assert saved_athlete["name"] == "Test Athlete"
        assert saved_athlete["telegram_id"] == str(test_telegram_id)

        print("Профиль успешно сохранён.")

        print("3. Проверяем список спортсменов...")

        athletes = get_all_athletes()

        assert any(
            item["athlete_id"] == test_athlete_id
            for item in athletes
        )

        print("Спортсмен найден в общем списке.")

        print("4. Проверяем источники данных...")

        assert saved_athlete["data_sources"]["training"]["primary"] == "intervals"
        assert saved_athlete["data_sources"]["recovery"]["primary"] == "intervals"

        print("Источники данных настроены правильно.")

    finally:
        print("5. Удаляем тестового спортсмена...")

        deleted = delete_athlete(test_athlete_id)

        assert deleted is True
        assert get_athlete(test_athlete_id) is None

        print("Профиль и API-ключ удалены.")
        print("\nВсе проверки пройдены!")


if __name__ == "__main__":
    test_athlete_registration()