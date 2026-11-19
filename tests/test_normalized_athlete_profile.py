from unittest.mock import patch

from src.athletes.athlete_manager import get_normalized_athlete_profile


def test_normalized_athlete_profile():
    fake_data = {
        "id": "test_i12345",
        "name": "Test Athlete",
        "weight": 70,
        "height": 1.75,
        "ftp": 250,
        "indoor_ftp": 240,
        "lthr": 170,
        "max_hr": 190,
        "power_zones": [55, 75, 90, 105, 120, 150, 999],
        "power_zone_names": [
            "Active Recovery",
            "Endurance",
            "Tempo",
            "Threshold",
            "VO2 Max",
            "Anaerobic",
            "Neuromuscular"
        ],
        "hr_zones": [118, 143, 162, 181, 190],
        "hr_zone_names": [
            "Recovery",
            "Endurance",
            "Steady State",
            "Tempo",
            "Interval"
        ]
    }

    print("1. Проверяем нормализацию профиля...")

    with patch(
        "src.athletes.athlete_manager.get_registered_athlete_data",
        return_value=fake_data
    ):
        profile = get_normalized_athlete_profile("test_i12345")

    assert profile["athlete_id"] == "test_i12345"
    assert profile["name"] == "Test Athlete"
    assert profile["weight"] == 70
    assert profile["height"] == 175
    assert profile["ftp"] == 250
    assert profile["ftp_per_kg"] == 3.57
    assert profile["max_heart_rate"] == 190

    print("Рост приведён к сантиметрам.")
    print("FTP/kg рассчитан правильно.")

    print("2. Проверяем отсутствие даты рождения...")

    assert "date_of_birth" not in profile
    assert "age" not in profile

    print("Возрастные поля отсутствуют.")

    print("\nВсе проверки пройдены!")


if __name__ == "__main__":
    test_normalized_athlete_profile()
