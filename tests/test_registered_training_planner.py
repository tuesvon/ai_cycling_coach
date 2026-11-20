from pprint import pprint

from src.assistant.training_planner import get_training_decision


ATHLETE_ID = "i280488"


def test_registered_training_planner():
    print("\nПолучаем решение AI Cycling Coach...")

    decision = get_training_decision(ATHLETE_ID)

    print("\n=== TODAY DECISION ===")
    pprint(decision["today"], sort_dicts=False)

    print("\n=== NEXT TWO DAYS ===")
    pprint(decision["next_days"], sort_dicts=False)

    print("\n=== VALIDATION ===")

    assert decision["today"]["decision"] in ("training", "rest")
    assert len(decision["next_days"]) == 2

    if decision["today"]["decision"] == "training":
        print("Сегодня рекомендована тренировка.")
        print("Следующий этап: запросить доступное время у спортсмена.")
    else:
        print("Сегодня рекомендован отдых.")
        print("Спортсмену можно показать предварительный план на два дня.")

    print("\nРеальное планирование успешно завершено!")


if __name__ == "__main__":
    test_registered_training_planner()