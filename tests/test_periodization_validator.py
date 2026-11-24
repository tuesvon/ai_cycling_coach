
from copy import deepcopy

from src.assistant.periodization_validator import (
    validate_periodization,
)


GOAL = {
    "event_name": "Главная гонка",
    "event_date": "2027-06-20",
}

START_DATE = "2027-05-23"

VALID_PLAN = {
    "explanation": (
        "Подготовка направлена на главную гонку. "
        "Промежуточные старты учитываются как нагрузка."
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
            "focus": "Специфическая работа",
        },
        {
            "phase": "taper",
            "start_date": "2027-06-13",
            "end_date": "2027-06-19",
            "focus": "Снижение усталости перед гонкой",
        },
    ],
}


def expect_invalid(plan, label):
    try:
        validate_periodization(
            plan,
            GOAL,
            start_date=START_DATE,
        )
    except ValueError:
        print(f"{label} PASSED")
    else:
        raise AssertionError(
            f"{label}: некорректный план принят"
        )


def test_periodization_validator():
    result = validate_periodization(
        VALID_PLAN,
        GOAL,
        start_date=START_DATE,
    )

    assert result["total_days"] == 28
    assert len(result["blocks"]) == 4
    assert result["blocks"][0]["duration_days"] == 7
    assert result["blocks"][-1]["end_date"] == "2027-06-19"

    print("VALID PERIODIZATION TEST PASSED")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][1]["start_date"] = "2027-05-31"
    expect_invalid(plan, "GAP BETWEEN BLOCKS TEST")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][1]["start_date"] = "2027-05-29"
    expect_invalid(plan, "OVERLAPPING BLOCKS TEST")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][-1]["end_date"] = "2027-06-20"
    expect_invalid(plan, "RACE DAY INCLUDED TEST")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][-1]["end_date"] = "2027-06-18"
    expect_invalid(plan, "INCOMPLETE PERIOD TEST")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][0]["phase"] = "unknown"
    expect_invalid(plan, "INVALID PHASE TEST")

    plan = deepcopy(VALID_PLAN)
    plan["blocks"][0]["focus"] = ""
    expect_invalid(plan, "MISSING FOCUS TEST")

    plan = deepcopy(VALID_PLAN)
    plan["explanation"] = ""
    expect_invalid(plan, "MISSING EXPLANATION TEST")

    print("Все тесты валидатора периодизации пройдены!")


if __name__ == "__main__":
    test_periodization_validator()
