from pprint import pprint

from src.analytics.athlete_status import (
    get_registered_athlete_status
)


def test_registered_athlete_status():
    athlete_id = "i280488"

    print("Получаем полный статус зарегистрированного спортсмена...")

    status = get_registered_athlete_status(athlete_id)

    print("\n=== TRAINING HISTORY ===")
    pprint(status.get("training_history"), sort_dicts=False)

    print("\n=== TRAINING CONSISTENCY ===")
    pprint(status.get("training_consistency"), sort_dicts=False)

    print("\n=== DATA SOURCES ===")
    pprint(status.get("data_sources"), sort_dicts=False)

    assert "training_history" in status
    assert "training_consistency" in status
    assert "objective" in status["training_consistency"]
    assert "context" in status["training_consistency"]
    assert "unexplained_gaps" in status["training_consistency"]

    print("\nВсе проверки успешно пройдены!")


if __name__ == "__main__":
    test_registered_athlete_status()
