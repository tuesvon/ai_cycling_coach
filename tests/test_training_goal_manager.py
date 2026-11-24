import sqlite3
import tempfile

from pathlib import Path
from unittest.mock import patch

from src.athletes import training_goal_manager



def test_training_goal_manager():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = str(
            Path(temp_dir) / "test_training_goals.db"
        )

        with patch.object(
            training_goal_manager,
            "DATABASE_PATH",
            database_path
        ), patch.object(
            training_goal_manager,
            "initialize_database",
            return_value=None
        ):

            goal_id = training_goal_manager.create_training_goal(
                athlete_id="test_goal_athlete",
                event_name="Главная шоссейная гонка",
                event_date="2099-06-20",
                event_type="road_race",
                distance_km=120,
                elevation_m=1500,
                target_result="Финишировать в основной группе",
                weekly_hours=10,
                description="Главная цель сезона",
            )

            goal = training_goal_manager.get_training_goal(goal_id)

            assert goal is not None
            assert goal["athlete_id"] == "test_goal_athlete"
            assert goal["event_name"] == "Главная шоссейная гонка"
            assert goal["event_date"] == "2099-06-20"
            assert goal["distance_km"] == 120
            assert goal["elevation_m"] == 1500
            assert goal["weekly_hours"] == 10
            assert goal["status"] == "active"

            print("CREATE TRAINING GOAL TEST PASSED")

            active_goals = (
                training_goal_manager.get_active_training_goals(
                    "test_goal_athlete"
                )
            )

            assert len(active_goals) == 1
            assert active_goals[0]["id"] == goal_id

            print("GET ACTIVE GOALS TEST PASSED")

            try:
                training_goal_manager.create_training_goal(
                    athlete_id="test_goal_athlete",
                    event_name="Прошедшая гонка",
                    event_date="2020-01-01",
                    event_type="road_race",
                )
            except ValueError:
                print("PAST EVENT VALIDATION TEST PASSED")
            else:
                raise AssertionError(
                    "Прошедшая дата не была отклонена"
                )

            try:
                training_goal_manager.create_training_goal(
                    athlete_id="test_goal_athlete",
                    event_name="Некорректная гонка",
                    event_date="2099-06-20",
                    event_type="road_race",
                    weekly_hours=-5,
                )
            except ValueError:
                print("INVALID WEEKLY HOURS TEST PASSED")
            else:
                raise AssertionError(
                    "Отрицательные часы не были отклонены"
                )

            connection = sqlite3.connect(database_path)

            try:
                count = connection.execute(
                    "SELECT COUNT(*) FROM training_goals"
                ).fetchone()[0]

            finally:
                connection.close()

            assert count == 1

            print("DATABASE INTEGRITY TEST PASSED")

    print("Все тесты менеджера целей пройдены!")


if __name__ == "__main__":
    test_training_goal_manager()
