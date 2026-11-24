import json

from src.analytics.athlete_analysis import (
    get_registered_athlete_analysis,
)
from src.assistant.coach import build_coach_context
from src.athletes.training_plan_manager import get_weekly_plan


def build_weekly_planning_context(analysis, weekly_plan):
    """
    Формирует контекст для адаптации недельного плана.
    Не изменяет исходные данные.
    """
    if not isinstance(analysis, dict):
        raise ValueError("Аналитика должна быть словарём")

    if not isinstance(weekly_plan, dict):
        raise ValueError("Недельный план должен быть словарём")

    workouts = weekly_plan.get("workouts")

    if not isinstance(workouts, list) or len(workouts) != 7:
        raise ValueError("Недельный план должен содержать 7 дней")

    return {
        "athlete": build_coach_context(analysis),
        "weekly_plan": {
            "id": weekly_plan["id"],
            "week_start": weekly_plan["week_start"],
            "goal_description": weekly_plan.get("goal_description"),
            "workouts": [
                {
                    "id": workout["id"],
                    "date": workout["workout_date"],
                    "status": workout["status"],
                    "original_workout": workout["original_workout"],
                    "current_workout": workout["current_workout"],
                }
                for workout in workouts
            ]
        }
    }


def build_weekly_adaptation_prompt(context):
    """Формирует запрос Gemma на пересмотр недельного плана."""
    context_json = json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    return (
        "Проанализируй актуальное состояние спортсмена и "
        "существующий недельный тренировочный план.\n"
        "Определи, нужно ли изменить оставшиеся тренировки недели.\n"
        "Учитывай цель подготовки, восстановление, тренировочную "
        "нагрузку и уже выполненные занятия.\n"
        "Не переноси пропущенные тренировки автоматически.\n"
        "Если изменения необходимы, объясни каждое изменение "
        "и его влияние на подготовку к цели.\n\n"
        "ДАННЫЕ ДЛЯ АНАЛИЗА:\n"
        f"{context_json}"
    )


def get_registered_weekly_planning_context(athlete_id, plan_id):
    """
    Загружает актуальную аналитику и недельный план.
    """
    analysis = get_registered_athlete_analysis(athlete_id)
    weekly_plan = get_weekly_plan(plan_id)

    if weekly_plan is None:
        raise ValueError("Недельный план не найден")

    if weekly_plan["athlete_id"] != athlete_id:
        raise ValueError("План принадлежит другому спортсмену")

    return build_weekly_planning_context(analysis, weekly_plan)


WEEKLY_ADAPTATION_SYSTEM_PROMPT = """
Ты — профессиональный AI Cycling Coach.

Твоя задача — анализировать недельный тренировочный план
велосипедиста и предлагать обоснованные изменения.

Правила:

1. Учитывай восстановление, сон, HRV, пульс покоя,
   тренировочную нагрузку и историю тренировок.

2. Учитывай цель подготовки спортсмена.

3. Не изменяй тренировочный план без необходимости.

4. Не переноси пропущенные тренировки автоматически.

5. Не изменяй выполненные тренировки.

6. Не изменяй тренировки за прошедшие даты.

7. Используй только зоны мощности из данных спортсмена.

8. Для отдыха используй:
   type = "rest"
   duration_minutes = null
   power_zone = null
   power_range_watts = null

9. Для тренировок используй точные диапазоны мощности,
   соответствующие выбранной зоне.

10. Не выдумывай отсутствующие показатели спортсмена.

11. Если данных недостаточно, предпочитай осторожное решение.

Верни только JSON без Markdown.

Формат:

{
  "decision": "keep или adapt",
  "explanation": "Общее объяснение решения",
  "changes": [
    {
      "workout_id": 123,
      "new_workout": {
        "date": "YYYY-MM-DD",
        "type": "Endurance или Threshold или rest",
        "duration_minutes": 60,
        "power_zone": "Endurance",
        "power_range_watts": "168-228",
        "purpose": "Цель тренировки"
      },
      "change_reason": "Почему изменена тренировка",
      "impact_on_goal": "Как изменение влияет на подготовку"
    }
  ]
}

Если изменения не нужны:
{
  "decision": "keep",
  "explanation": "Почему план можно сохранить",
  "changes": []
}

Не добавляй поля вне указанной структуры.
"""


def generate_weekly_adaptation(context):
    """
    Запрашивает у Gemma предложение по адаптации недели.
    Проверяет JSON, но не сохраняет изменения в SQLite.
    """
    from src.assistant.llm import ask_gemma
    from src.assistant.training_planner import extract_json
    from src.assistant.weekly_adaptation_validator import (
        validate_weekly_adaptation,
    )

    prompt = build_weekly_adaptation_prompt(context)

    response = ask_gemma(
        prompt,
        system_prompt=WEEKLY_ADAPTATION_SYSTEM_PROMPT
    )

    decision = extract_json(response)

    return validate_weekly_adaptation(
        decision,
        context
    )