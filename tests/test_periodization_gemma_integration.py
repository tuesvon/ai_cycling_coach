
import json

from unittest.mock import patch

from src.assistant import periodization_planner as planner


def build_test_context():
    goal = {
        "event_name": "Главная шоссейная гонка",
        "event_date": "2027-06-20",
        "event_type": "road_race",
        "distance_km": 120,
        "elevation_m": 1500,
        "target_result": "Финишировать в основной группе",
        "weekly_hours": 10,
        "description": "Главная цель сезона",
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
        "notes": "Гонки Zwift по желанию",
    }

    athlete_context = {
        "profile": {
            "ftp_watts": 304,
            "weight_kg": 76.5,
        },
        "training_history": {
            "cycling_sessions_per_week": 5,
        },
    }

    return planner.build_periodization_context(
        goal=goal,
        preferences=preferences,
        athlete_context=athlete_context,
        start_date="2027-05-23",
    )


def build_valid_response():
    return {
        "explanation": (
            "Подготовка направлена на главную гонку. "
            "Онлайн-гонки учитываются как тренировочная нагрузка."
        ),
        "blocks": [
            {
                "phase": "base",
                "start_date": "2027-05-23",
                "end_date": "2027-05-29",
                "focus": "Аэробная выносливость",
            },
            {
                "phase": "build",
                "start_date": "2027-05-30",
                "end_date": "2027-06-05",
                "focus": "Развитие мощности",
            },
            {
                "phase": "specific",
                "start_date": "2027-06-06",
                "end_date": "2027-06-12",
                "focus": "Специфическая подготовка",
            },
            {
                "phase": "taper",
                "start_date": "2027-06-13",
                "end_date": "2027-06-19",
                "focus": "Снижение усталости",
            },
        ],
    }


def test_periodization_gemma_integration():
    context = build_test_context()

    assert context["preparation_window"][
        "preparation_days"
    ] == 28

    assert context["training_preferences"][
        "spontaneous_races"
    ] is True

    print("PERIODIZATION CONTEXT TEST PASSED")

    prompt = planner.build_periodization_prompt(context)

    assert "Главная шоссейная гонка" in prompt
    assert "2027-06-20" in prompt
    assert "Гонки Zwift по желанию" in prompt

    print("PERIODIZATION PROMPT TEST PASSED")

    valid_response = json.dumps(
        build_valid_response(),
        ensure_ascii=False,
    )

    with patch.object(
        planner,
        "ask_gemma",
        return_value=valid_response,
    ) as mocked_gemma:

        result = planner.generate_periodization(context)

        assert result["total_days"] == 28
        assert len(result["blocks"]) == 4
        assert result["blocks"][-1][
            "end_date"
        ] == "2027-06-19"

        mocked_gemma.assert_called_once()

        assert mocked_gemma.call_args.kwargs[
            "system_prompt"
        ] == planner.PERIODIZATION_SYSTEM_PROMPT

    print("GEMMA PERIODIZATION TEST PASSED")

    invalid_response = json.dumps({
        "explanation": "Некорректный план",
        "blocks": [
            {
                "phase": "base",
                "start_date": "2027-05-23",
                "end_date": "2027-06-20",
                "focus": "Аэробная работа",
            }
        ],
    })

    with patch.object(
        planner,
        "ask_gemma",
        return_value=invalid_response,
    ):
        try:
            planner.generate_periodization(context)
        except ValueError:
            print("INVALID GEMMA PLAN TEST PASSED")
        else:
            raise AssertionError(
                "Некорректный план Gemma был принят"
            )

    print("Все тесты интеграции периодизации пройдены!")


if __name__ == "__main__":
    test_periodization_gemma_integration()
