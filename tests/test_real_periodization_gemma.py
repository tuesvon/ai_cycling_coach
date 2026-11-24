
from pprint import pprint

from src.assistant.periodization_planner import (
    build_periodization_context,
    build_periodization_prompt,
    generate_periodization,
    PERIODIZATION_SYSTEM_PROMPT,
)

from src.assistant.llm import ask_gemma


def build_test_context():
    """
    Искусственная главная цель и пример данных спортсмена.

    Никаких записей в SQLite или Intervals.icu.
    """
    goal = {
        "event_name": "Главная шоссейная гонка",
        "event_date": "2027-03-21",
        "event_type": "road_race",
        "distance_km": 120,
        "elevation_m": 1500,
        "target_result": "Финишировать в основной группе",
        "weekly_hours": 9,
        "description": "Главная цель подготовки",
    }

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
        "notes": (
            "Иногда участвую в онлайн-гонках Zwift. "
            "День участия заранее неизвестен."
        ),
    }

    athlete_context = {
        "profile": {
            "ftp_watts": 280,
            "weight_kg": 75,
        },
        "training_history": {
            "cycling_sessions_per_week": 5,
            "cycling_hours_last_7_days": 8,
            "cycling_hours_last_30_days": 32,
        },
        "recovery": {
            "status": "normal",
        },
    }

    return build_periodization_context(
        goal=goal,
        preferences=preferences,
        athlete_context=athlete_context,
        start_date="2027-01-25",
    )


def test_real_periodization_gemma():
    context = build_test_context()

    window = context["preparation_window"]

    print("\n=== PREPARATION WINDOW ===")
    pprint(window)

    print("\n=== REQUESTING REAL GEMMA ===")

    try:
        result = generate_periodization(context)

    except Exception as error:
        print("\n=== PERIODIZATION FAILED ===")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")

        print("\n=== RAW GEMMA RESPONSE ===")

        # Дополнительный запрос только для диагностики.
        # Он может отличаться от первого ответа.
        try:
            raw_response = ask_gemma(
                build_periodization_prompt(context),
                system_prompt=PERIODIZATION_SYSTEM_PROMPT,
            )

            print(raw_response)

        except Exception as diagnostic_error:
            print(
                "Не удалось получить диагностический ответ:",
                diagnostic_error,
            )

        raise

    print("\n=== VALIDATED PERIODIZATION ===")

    pprint(result, sort_dicts=False)

    assert result["start_date"] == "2027-01-25"
    assert result["event_date"] == "2027-03-21"
    assert result["total_days"] == 55
    assert len(result["blocks"]) >= 1

    print("\nREAL GEMMA PERIODIZATION TEST PASSED")


if __name__ == "__main__":
    test_real_periodization_gemma()