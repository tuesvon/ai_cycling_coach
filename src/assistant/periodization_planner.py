import json

from src.assistant.llm import ask_gemma
from src.assistant.training_planner import extract_json
from src.assistant.training_periodization import (
    calculate_preparation_window,
)
from src.assistant.periodization_validator import (
    validate_periodization,
)


PERIODIZATION_SYSTEM_PROMPT = """
Ты — профессиональный тренер по велоспорту.

Твоя задача — разработать долгосрочную стратегию
подготовки спортсмена к его ГЛАВНОМУ соревнованию.

Правила:

1. Главная цель спортсмена имеет высший приоритет.
2. Учитывай текущую подготовленность, историю
   тренировок и доступное время.
3. Промежуточные гонки являются частью подготовки,
   но не заменяют главную цель.
4. Спонтанные онлайн-гонки не имеют фиксированного дня.
5. Не планируй подробные ежедневные тренировки.
6. Предлагай блоки подготовки: base, build,
   specific, taper или transition.
7. Учитывай необходимость восстановления и
   постепенного изменения нагрузки.
8. Не придумывай отсутствующие данные.
9. Не используй возраст или дату рождения.
10. Не назначай фиксированные фазы механически:
    их последовательность и длительность должны
    соответствовать сроку подготовки и цели.

Верни только корректный JSON следующего формата:

{
  "explanation": "Объяснение общей стратегии",
  "blocks": [
    {
      "phase": "base",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "focus": "Основная задача блока"
    }
  ]
}

Требования к датам:

- Первый блок начинается в start_date.
- Каждый следующий блок начинается на следующий
  календарный день после предыдущего.
- Последний блок заканчивается за день до event_date.
- Между блоками нет пропусков или пересечений.
- День главной гонки не включается в блоки.
- Все даты включительны.

Не добавляй Markdown или пояснения вне JSON.
"""


def build_periodization_context(
    goal,
    preferences,
    athlete_context,
    start_date=None,
):
    """
    Формирует контекст для долгосрочного планирования.

    athlete_context — аналитические данные спортсмена,
    подготовленные существующим модулем coach.py.
    """
    if not isinstance(goal, dict):
        raise ValueError("Главная цель должна быть словарём")

    if not isinstance(preferences, dict):
        raise ValueError(
            "Тренировочные предпочтения должны быть словарём"
        )

    if not isinstance(athlete_context, dict):
        raise ValueError(
            "Аналитика спортсмена должна быть словарём"
        )

    required_goal_fields = (
        "event_name",
        "event_date",
        "event_type",
    )

    for field in required_goal_fields:
        value = goal.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Не заполнено обязательное поле цели: {field}"
            )

    window = calculate_preparation_window(
        event_date=goal["event_date"],
        start_date=start_date,
    )

    return {
        "goal": {
            "event_name": goal["event_name"],
            "event_date": window["event_date"],
            "event_type": goal["event_type"],
            "distance_km": goal.get("distance_km"),
            "elevation_m": goal.get("elevation_m"),
            "target_result": goal.get("target_result"),
            "weekly_hours": goal.get("weekly_hours"),
            "description": goal.get("description"),
        },
        "preparation_window": window,
        "training_preferences": {
            "availability": preferences.get("availability"),
            "spontaneous_races": preferences.get(
                "spontaneous_races", False
            ),
            "race_duration_minutes": preferences.get(
                "race_duration_minutes"
            ),
            "notes": preferences.get("notes"),
        },
        "athlete": athlete_context,
    }


def build_periodization_prompt(context):
    """
    Создаёт запрос для Gemma.
    """
    if not isinstance(context, dict):
        raise ValueError("Контекст должен быть словарём")

    context_json = json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    return (
        "Разработай долгосрочную периодизацию подготовки "
        "к главному соревнованию спортсмена.\n\n"
        "Учитывай его тренировочную историю, "
        "восстановление, доступное время и предпочтения.\n\n"
        "Срок подготовки указан в preparation_window.\n"
        "Используй start_date и event_date из этого объекта.\n\n"
        "Если данных недостаточно, не выдумывай показатели. "
        "Объясни ограничения стратегии.\n\n"
        "ДАННЫЕ СПОРТСМЕНА:\n"
        + context_json
    )


def generate_periodization(context):
    """
    Запрашивает периодизацию у Gemma
    и проверяет результат средствами Python.

    Ничего не сохраняет в базу данных.
    """
    if not isinstance(context, dict):
        raise ValueError("Контекст должен быть словарём")

    window = context.get("preparation_window")
    goal = context.get("goal")

    if not isinstance(window, dict):
        raise ValueError("Отсутствует период подготовки")

    if not isinstance(goal, dict):
        raise ValueError("Отсутствует главная цель")

    prompt = build_periodization_prompt(context)

    response = ask_gemma(
        prompt,
        system_prompt=PERIODIZATION_SYSTEM_PROMPT,
    )

    data = extract_json(response)

    return validate_periodization(
        data=data,
        goal=goal,
        start_date=window["start_date"],
    )