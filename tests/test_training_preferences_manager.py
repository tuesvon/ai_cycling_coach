
import tempfile

from pathlib import Path
from unittest.mock import patch

from src.athletes import training_preferences_manager as manager


def test_training_preferences_manager():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = str(
            Path(temp_dir) / "preferences_test.db"
        )

        with patch.object(
            manager,
            "DATABASE_PATH",
            database_path
        ), patch.object(
            manager,
            "initialize_database",
            return_value=None
        ):
            preferences = {
                "availability": {
                    "monday": 60,
                    "tuesday": 90,
                    "wednesday": 90,
                    "thursday": 60,
                    "friday": 90,
                    "saturday": 180,
                    "sunday": 120,
                },
                "spontaneous_races": True,
                "race_duration_minutes": 90,
                "notes": "Гонки Zwift по желанию",
            }

            manager.save_training_preferences(
                "test_athlete",
                preferences,
            )

            saved = manager.get_training_preferences(
                "test_athlete"
            )

            assert saved is not None
            assert saved["availability"]["saturday"] == 180
            assert saved["spontaneous_races"] is True
            assert saved["race_duration_minutes"] == 90

            print("SAVE PREFERENCES TEST PASSED")

            updated = {
                **preferences,
                "availability": {
                    **preferences["availability"],
                    "friday": 0,
                },
                "race_duration_minutes": 75,
            }

            manager.save_training_preferences(
                "test_athlete",
                updated,
            )

            saved = manager.get_training_preferences(
                "test_athlete"
            )

            assert saved["availability"]["friday"] == 0
            assert saved["race_duration_minutes"] == 75

            print("UPDATE PREFERENCES TEST PASSED")

            assert manager.get_training_preferences(
                "unknown_athlete"
            ) is None

            print("UNKNOWN ATHLETE TEST PASSED")

            try:
                manager.validate_training_preferences({
                    **preferences,
                    "availability": {
                        **preferences["availability"],
                        "monday": -60,
                    },
                })
            except ValueError:
                print("INVALID DURATION TEST PASSED")
            else:
                raise AssertionError(
                    "Отрицательная длительность принята"
                )

            try:
                manager.validate_training_preferences({
                    **preferences,
                    "availability": {
                        "monday": 60,
                    },
                })
            except ValueError:
                print("INCOMPLETE SCHEDULE TEST PASSED")
            else:
                raise AssertionError(
                    "Неполное расписание принято"
                )

    print("Все тесты тренировочных предпочтений пройдены!")


if __name__ == "__main__":
    test_training_preferences_manager()
