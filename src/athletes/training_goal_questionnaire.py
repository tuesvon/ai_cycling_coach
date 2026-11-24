from datetime import date

from src.athletes.training_goal_manager import create_training_goal


GOAL_QUESTIONS = [
    {
        "field": "event_name",
        "question": "Как называется твоя главная гонка или цель?",
        "required": True,
    },
    {
        "field": "event_date",
        "question": "Когда состоится главное событие? (ГГГГ-ММ-ДД)",
        "required": True,
    },
    {
        "field": "event_type",
        "question": (
            "Какой тип соревнования? Например: шоссе, "
            "гравий, MTB, триатлон или другое."
        ),
        "required": True,
    },
    {
        "field": "distance_km",
        "question": "Какая дистанция в километрах? (Можно пропустить)",
        "required": False,
    },
    {
        "field": "elevation_m",
        "question": "Какой набор высоты в метрах? (Можно пропустить)",
        "required": False,
    },
    {
        "field": "target_result",
        "question": "Какого результата хочешь достичь? (Можно пропустить)",
        "required": False,
    },
    {
        "field": "weekly_hours",
        "question": "Сколько часов в неделю готов тренироваться?",
        "required": True,
    },
    {
        "field": "description",
        "question": (
            "Есть ли дополнительные пожелания или ограничения? "
            "(Можно пропустить)"
        ),
        "required": False,
    },
]


def get_goal_questions():
    """
    Возвращает вопросы первоначального опроса.
    """
    return [question.copy() for question in GOAL_QUESTIONS]


def validate_goal_answer(field, answer):
    """
    Проверяет и нормализует один ответ спортсмена.
    """
    questions = {
        question["field"]: question
        for question in GOAL_QUESTIONS
    }

    if field not in questions:
        raise ValueError(f"Неизвестное поле: {field}")

    required = questions[field]["required"]

    if answer is None or (
        isinstance(answer, str) and not answer.strip()
    ):
        if required:
            raise ValueError("Это обязательный вопрос")
        return None

    if field == "event_date":
        if not isinstance(answer, str):
            raise ValueError("Дата должна быть строкой")

        try:
            parsed_date = date.fromisoformat(answer.strip())
        except ValueError as error:
            raise ValueError(
                "Укажи дату в формате ГГГГ-ММ-ДД"
            ) from error

        if parsed_date < date.today():
            raise ValueError("Дата главной гонки уже прошла")

        return parsed_date.isoformat()

    if field in ("distance_km", "elevation_m", "weekly_hours"):
        if isinstance(answer, bool):
            raise ValueError("Нужно указать число")

        try:
            value = float(answer)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Нужно указать число") from error

        if not 0 < value < float("inf"):
            raise ValueError("Число должно быть положительным")

        if field == "elevation_m":
            if not value.is_integer():
                raise ValueError(
                    "Набор высоты должен быть целым числом"
                )
            return int(value)

        return value

    if not isinstance(answer, str):
        raise ValueError("Ответ должен быть текстом")

    return answer.strip()


def validate_goal_questionnaire(answers):
    """
    Проверяет всю анкету и возвращает нормализованные данные.
    """
    if not isinstance(answers, dict):
        raise ValueError("Ответы должны быть словарём")

    known_fields = {
        question["field"]
        for question in GOAL_QUESTIONS
    }

    unknown_fields = set(answers) - known_fields

    if unknown_fields:
        raise ValueError(
            f"Неизвестные поля: {sorted(unknown_fields)}"
        )

    result = {}

    for question in GOAL_QUESTIONS:
        field = question["field"]
        result[field] = validate_goal_answer(
            field,
            answers.get(field),
        )

    return result


def save_goal_questionnaire(athlete_id, answers):
    """
    Проверяет анкету и сохраняет цель спортсмена.

    Возвращает ID созданной цели.
    """
    validated = validate_goal_questionnaire(answers)

    return create_training_goal(
        athlete_id=athlete_id,
        **validated,
    )