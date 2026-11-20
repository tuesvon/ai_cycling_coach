from pprint import pprint

from src.analytics.athlete_analysis import get_registered_athlete_analysis
from src.assistant.coach import ask_coach


def test_registered_athlete_coach():
    athlete_id = "i280488"

    print("\nПолучаем аналитические данные...")
    analysis = get_registered_athlete_analysis(athlete_id)

    print("\n=== TRAINING LOAD: 7 DAYS ===")
    pprint(analysis["training_load"]["7_days"], sort_dicts=False)

    print("\n=== TRAINING LOAD: 30 DAYS ===")
    pprint(analysis["training_load"]["30_days"], sort_dicts=False)

    print("\n=== TRAINING LOAD TRENDS ===")
    pprint(analysis["training_load_trends"], sort_dicts=False)

    question = (
        "Проанализируй моё текущее состояние. "
        "Оцени тренировочную нагрузку и восстановление. "
        "Дай рекомендации по тренировкам на ближайшие дни."
    )

    answer = ask_coach(
        athlete_id=athlete_id,
        question=question
    )

    print("\n=== AI CYCLING COACH RESPONSE ===")
    print(answer)

    assert isinstance(answer, str)
    assert len(answer.strip()) > 0

    print("\nGemma успешно проанализировала спортсмена!")


if __name__ == "__main__":
    test_registered_athlete_coach()