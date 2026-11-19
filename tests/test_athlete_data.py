from unittest.mock import patch

from src.athletes.athlete_manager import get_registered_athlete_data


def test_registered_athlete_data():
    athlete_id = "test_i12345"

    fake_athlete = {
        "athlete_id": athlete_id,
        "intervals_athlete_id": athlete_id,
        "name": "Test Athlete"
    }

    fake_data = {
        "id": athlete_id,
        "name": "Test Athlete",
        "weight": 70,
        "height": 175,
        "ftp": 250,
        "max_hr": 190
    }

    print("1. Проверяем загрузку данных спортсмена...")

    with patch(
        "src.athletes.athlete_manager.get_athlete",
        return_value=fake_athlete
    ), patch(
        "src.athletes.athlete_manager.get_stored_api_key",
        return_value="fake_encrypted_key"
    ), patch(
        "src.athletes.athlete_manager.get_athlete_data",
        return_value=fake_data
    ) as mock_api:

        result = get_registered_athlete_data(athlete_id)

        mock_api.assert_called_once_with(
            api_key="fake_encrypted_key"
        )

    assert result["id"] == athlete_id
    assert result["ftp"] == 250
    assert result["weight"] == 70

    print("Данные успешно загружены.")

    print("2. Проверяем защиту от несовпадения ID...")

    with patch(
        "src.athletes.athlete_manager.get_athlete",
        return_value=fake_athlete
    ), patch(
        "src.athletes.athlete_manager.get_stored_api_key",
        return_value="fake_key"
    ), patch(
        "src.athletes.athlete_manager.get_athlete_data",
        return_value={"id": "wrong_id", "name": "Other Athlete"}
    ):

        try:
            get_registered_athlete_data(athlete_id)
            assert False, "Ожидалась ошибка несовпадения ID"
        except ValueError as error:
            assert "не совпадает" in str(error)

    print("Проверка несовпадения ID пройдена.")

    print("\nВсе проверки пройдены!")


if __name__ == "__main__":
    test_registered_athlete_data()
