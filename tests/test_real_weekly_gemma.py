
from pprint import pprint

from src.assistant.weekly_planner import (
    generate_weekly_adaptation,
)
from tests.test_weekly_gemma_integration import (
    build_context,
)


def test_real_weekly_gemma():
    context = build_context()

    print("Отправляем недельный план в Gemma...")

    try:
        decision = generate_weekly_adaptation(context)
    except Exception as error:
        print(
            "Gemma не вернула корректное решение:",
            type(error).__name__,
            str(error)
        )
        raise

    print("\n=== РЕШЕНИЕ GEMMA ===")
    pprint(decision, sort_dicts=False)

    assert decision["decision"] in ("keep", "adapt")
    assert isinstance(decision["changes"], list)

    print("\nREAL WEEKLY GEMMA TEST PASSED")


if __name__ == "__main__":
    test_real_weekly_gemma()
