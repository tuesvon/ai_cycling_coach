
from unittest.mock import patch

from src.athletes import training_goal_questionnaire as questionnaire


def test_goal_questionnaire():
    questions = questionnaire.get_goal_questions()

    assert len(questions) == 8
    assert questions[0]["field"] == "event_name"

    print("QUESTIONS TEST PASSED")

    answers = {
        "event_name": "Главная шоссейная гонка",
        "event_date": "2099-06-20",
        "event_type": "road_race",
        "distance_km": "120",
        "elevation_m": "1500",
        "target_result": "Финишировать в основной группе",
        "weekly_hours": "10",
        "description": "",
    }

    validated = questionnaire.validate_goal_questionnaire(
        answers
    )

    assert validated["event_name"] == "Главная шоссейная гонка"
    assert validated["event_date"] == "2099-06-20"
    assert validated["distance_km"] == 120.0
    assert validated["elevation_m"] == 1500
    assert validated["weekly_hours"] == 10.0
    assert validated["description"] is None

    print("QUESTIONNAIRE VALIDATION TEST PASSED")

    try:
        questionnaire.validate_goal_questionnaire({
            **answers,
            "weekly_hours": "-5",
        })
    except ValueError:
        print("INVALID WEEKLY HOURS TEST PASSED")
    else:
        raise AssertionError(
            "Отрицательные часы не были отклонены"
        )

    try:
        questionnaire.validate_goal_questionnaire({
            **answers,
            "event_date": "2020-01-01",
        })
    except ValueError:
        print("PAST EVENT DATE TEST PASSED")
    else:
        raise AssertionError(
            "Прошедшая дата не была отклонена"
        )

    try:
        questionnaire.validate_goal_questionnaire({
            **answers,
            "event_name": "",
        })
    except ValueError:
        print("REQUIRED FIELD TEST PASSED")
    else:
        raise AssertionError(
            "Пустое обязательное поле не было отклонено"
        )

    with patch.object(
        questionnaire,
        "create_training_goal",
        return_value=123
    ) as mocked_create:

        goal_id = questionnaire.save_goal_questionnaire(
            "test_goal_athlete",
            answers,
        )

        assert goal_id == 123

        mocked_create.assert_called_once_with(
            athlete_id="test_goal_athlete",
            **validated,
        )

    print("SAVE QUESTIONNAIRE TEST PASSED")
    print("Все тесты первоначального опроса пройдены!")


if __name__ == "__main__":
    test_goal_questionnaire()
