import json
import re

from src.analytics.athlete_analysis import get_registered_athlete_analysis
from src.assistant.coach import build_coach_context
from src.assistant.llm import ask_gemma


PLANNER_SYSTEM_PROMPT = """
Ты — персональный AI Cycling Coach.

Твоя задача — принять решение о тренировке на сегодня
и предложить предварительный план на следующие два дня.

Работай только с переданными данными спортсмена.

ПРАВИЛА:

1. Все числовые показатели рассчитаны Python.
   Не пересчитывай их и не изменяй.

2. Не смешивай Garmin Load и TSS.
   Не смешивай велосипедные тренировки с другими активностями.

3. Учитывай готовность, сон, HRV, пульс покоя,
   тренировочную нагрузку, историю и регулярность тренировок.

4. Не делай медицинских выводов и не диагностируй
   переутомление или перетренированность.

5. Отсутствующий TSS не означает нулевую нагрузку.

6. Если данных недостаточно или показатели противоречат друг другу,
   выбирай более осторожную рекомендацию и объясняй неопределённость.

7. Не назначай интенсивную тренировку только потому,
   что отдельные показатели восстановления выглядят хорошо.

8. Учитывай последовательность тренировок:
   не планируй тяжёлые занятия несколько дней подряд
   без достаточных оснований.

9. Если сегодня рекомендуется отдых,
   явно укажи decision = "rest".
   Не предлагай тренировку сегодня.

10. Если сегодня рекомендуется тренировка,
    укажи decision = "training".
    Не назначай её продолжительность:
    сначала спортсмен должен сообщить, сколько времени у него есть.

11. На следующие два дня предложи предварительные рекомендации.
    Они должны учитывать сегодняшнее решение и восстановление.
    Эти рекомендации будут пересматриваться ежедневно.

12. Используй только переданные границы зон мощности.
    Не рассчитывай мощность самостоятельно.
    Если подходящая зона неизвестна, не выдумывай диапазон.

13. Не придумывай доступность спортсмена по времени.
    Продолжительность будущих тренировок указывай как предварительную.

14. Не называй исторические средние значения целевыми показателями.

15. Не используй чрезмерно категоричные формулировки:
    "критическое состояние", "критически низкий сон",
    "опасное состояние" и подобные.
    Описывай конкретные показатели и их отклонения
    от личной нормы спортсмена.

16. Не делай вывод о переутомлении или риске перетренированности
    только на основании одного показателя сна или нагрузки.

17. Статус readiness = "mixed" не означает автоматический запрет
    на интенсивные тренировки.
    Принимай решение с учётом всех доступных показателей,
    истории тренировок и их последовательности.

18. Не утверждай, что определённые зоны мощности запрещены
    системой. Выбирай интенсивность исходя из состояния спортсмена.

19. Рекомендации на следующие два дня являются предварительными.
    Не представляй их как обязательный план.
    Каждый день решение должно пересматриваться
    по актуальным данным восстановления и тренировок.

20. Не предлагай автоматически повторять вчерашнюю тренировку.
    Если состояние спортсмена изменилось, рекомендация
    должна формироваться заново.

21. Не используй формулировки о предотвращении перетренированности
    как обоснование конкретной тренировки.
    Объясняй, какую тренировочную задачу решает рекомендация.

22. Сравнение Garmin Load за последние 7 дней
    со средним за предыдущие 23 дня — это только сравнение
    двух периодов. Не называй его устойчивым ростом,
    долгосрочной тенденцией или доказательством перегрузки.

23. HRV и пульс покоя сравнивай с личной базой спортсмена.
    Более высокий HRV сам по себе не доказывает полное восстановление.
    Более низкий пульс покоя сам по себе не доказывает
    готовность к интенсивной тренировке.

24. Если workout_focus = "Active Recovery",
    intensity обязательно должно быть "recovery".
    Для Endurance используй "easy", для Tempo — "moderate",
    если нет особых оснований для другой классификации.

25. Не называй сравнение Garmin Load за последние 7 дней
с предыдущими 23 днями устойчивым ростом или трендом.
Это только сравнение двух периодов.

26. Не используй изменение Garmin Load на 12.5% как
самостоятельное основание для отдыха или снижения интенсивности.
Оценивай его только в совокупности с остальными показателями.

27. Если упоминаешь изменение нагрузки, обязательно указывай,
что сравниваются последние 7 дней со средним недельным
значением за предыдущие 23 дня.

28. Если duration_minutes равен null, не указывай конкретную
продолжительность тренировки ни в recommendation, ни в purpose,
ни в conditions.

29. Не добавляй числовую продолжительность тренировки в текстовые
поля, если она не указана в duration_minutes.

30. Если сегодня рекомендован отдых, не предлагай тренировку
сегодня даже в качестве необязательной альтернативы.
Предложения тренировок должны относиться к следующим дням.   

ФОРМАТ ОТВЕТА:

{
  "today": {
    "decision": "training или rest",
    "reason": "Объяснение решения",
    "workout_focus": "Тип тренировки или rest",
    "intensity": "recovery, easy, moderate, hard или rest"
  },
  "next_days": [
    {
      "day": "tomorrow",
      "recommendation": "Тип тренировки или rest",
      "duration_minutes": null,
      "power_zone": "Название зоны или null",
      "power_range_watts": "Диапазон из переданных зон или null",
      "intensity": "recovery, easy, moderate, hard или rest",
      "purpose": "Цель тренировки",
      "conditions": "Условия, при которых рекомендация актуальна"
    },
    {
      "day": "day_after_tomorrow",
      "recommendation": "Тип тренировки или rest",
      "duration_minutes": null,
      "power_zone": "Название зоны или null",
      "power_range_watts": "Диапазон из переданных зон или null",
      "intensity": "recovery, easy, moderate, hard или rest",
      "purpose": "Цель тренировки",
      "conditions": "Условия, при которых рекомендация актуальна"
    }
  ]
}
"""


def extract_json(response):
    """
    Извлекает JSON из ответа Gemma.
    Поддерживает как чистый JSON, так и JSON в Markdown-блоке.
    """
    if not isinstance(response, str) or not response.strip():
        raise ValueError("Gemma вернула пустой ответ")

    cleaned = response.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("В ответе Gemma не найден JSON-объект")

    return json.loads(cleaned[start:end + 1])


def validate_training_decision(data, power_zones=None):
    """
    Проверяет решение Gemma:
    - структуру ответа;
    - интенсивность;
    - названия зон мощности;
    - диапазоны мощности;
    - продолжительность тренировок;
    - согласованность отдыха и тренировок.

    Не исправляет и не додумывает ответ Gemma.
    """

    if not isinstance(data, dict):
        raise ValueError("Результат планирования должен быть JSON-объектом")

    # Подготавливаем допустимые зоны мощности.
    power_zones = power_zones or []

    zones_by_name = {
        zone["name"]: zone
        for zone in power_zones
    }

    allowed_intensities = {
        "recovery",
        "easy",
        "moderate",
        "hard",
        "rest"
    }

    def validate_duration(value, field_name):
        if value is None:
            return

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value <= 0
        ):
            raise ValueError(
                f"{field_name}: продолжительность должна быть "
                "положительным числом или null"
            )

    def validate_zone(item, field_name):
        zone_name = item.get("power_zone")
        power_range = item.get("power_range_watts")

        if zone_name is None:
            if power_range is not None:
                raise ValueError(
                    f"{field_name}: указан диапазон мощности "
                    "без названия зоны"
                )
            return

        if zone_name not in zones_by_name:
            raise ValueError(
                f"{field_name}: неизвестная зона мощности: {zone_name}"
            )

        zone = zones_by_name[zone_name]

        min_watts = zone["min_watts"]
        max_watts = zone["max_watts"]

        if max_watts is None:
            expected_range = f"{min_watts}+"
        else:
            expected_range = f"{min_watts}-{max_watts}"

        if power_range != expected_range:
            raise ValueError(
                f"{field_name}: неверный диапазон мощности "
                f"для зоны {zone_name}. "
                f"Ожидался {expected_range}, получен {power_range}"
            )

        # Проверяем соответствие зоны заявленной интенсивности.
        zone_number = zone["zone"]

        expected_intensity = {
            1: "recovery",
            2: "easy",
            3: "moderate",
        }.get(zone_number, "hard")

        if item.get("intensity") != expected_intensity:
            raise ValueError(
                f"{field_name}: зона {zone_name} "
                f"не соответствует интенсивности "
                f"{item.get('intensity')}. "
                f"Ожидается {expected_intensity}"
            )

    # Проверяем сегодняшний день.
    today = data.get("today")

    if not isinstance(today, dict):
        raise ValueError("В ответе отсутствует объект today")

    if today.get("decision") not in ("training", "rest"):
        raise ValueError(
            "today.decision должен быть training или rest"
        )

    if today.get("intensity") not in allowed_intensities:
        raise ValueError("Некорректное значение today.intensity")

    if not isinstance(today.get("reason"), str) or not today["reason"].strip():
        raise ValueError("Не указана причина сегодняшнего решения")

    if (
        not isinstance(today.get("workout_focus"), str)
        or not today["workout_focus"].strip()
    ):
        raise ValueError("Не указан workout_focus")

    if today["decision"] == "rest":
        if today["intensity"] != "rest":
            raise ValueError(
                "При решении rest интенсивность должна быть rest"
            )

        if today["workout_focus"].strip().lower() not in (
            "rest",
            "отдых",
            "полный отдых"
        ):
            raise ValueError(
                "При решении rest workout_focus должен обозначать отдых"
            )

    elif today["intensity"] == "rest":
        raise ValueError(
            "При решении training интенсивность не может быть rest"
        )

    # Проверяем следующие два дня.
    next_days = data.get("next_days")

    if not isinstance(next_days, list) or len(next_days) != 2:
        raise ValueError(
            "Необходимо ровно две рекомендации на следующие дни"
        )

    expected_days = [
        "tomorrow",
        "day_after_tomorrow"
    ]

    for index, item in enumerate(next_days):
        field_name = expected_days[index]

        if not isinstance(item, dict):
            raise ValueError(
                f"{field_name}: рекомендация должна быть объектом"
            )

        if item.get("day") != field_name:
            raise ValueError(
                f"Ожидался день {field_name}"
            )

        if (
            not isinstance(item.get("recommendation"), str)
            or not item["recommendation"].strip()
        ):
            raise ValueError(
                f"{field_name}: не указана рекомендация"
            )

        if item.get("intensity") not in allowed_intensities:
            raise ValueError(
                f"{field_name}: некорректная интенсивность"
            )

        if (
            not isinstance(item.get("purpose"), str)
            or not item["purpose"].strip()
        ):
            raise ValueError(
                f"{field_name}: не указана цель тренировки"
            )

        if (
            not isinstance(item.get("conditions"), str)
            or not item["conditions"].strip()
        ):
            raise ValueError(
                f"{field_name}: не указаны условия рекомендации"
            )

        validate_duration(
            item.get("duration_minutes"),
            f"{field_name}.duration_minutes"
        )

        if item["intensity"] == "rest":
            if item.get("power_zone") is not None:
                raise ValueError(
                    f"{field_name}: для отдыха не должна указываться зона"
                )

            if item.get("power_range_watts") is not None:
                raise ValueError(
                    f"{field_name}: для отдыха не должен указываться "
                    "диапазон мощности"
                )
        else:
            validate_zone(item, field_name)

    return data

def build_training_decision_prompt(analysis):
    """
    Формирует запрос Gemma на основании аналитики спортсмена.
    """
    context = build_coach_context(analysis)

    context_json = json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    return (
        "Проанализируй состояние спортсмена.\n"
        "Прими решение о тренировке на сегодня и предложи "
        "предварительные рекомендации на следующие два дня.\n\n"
        "ДАННЫЕ СПОРТСМЕНА:\n"
        f"{context_json}"
    )


def get_training_decision(athlete_id):
    """
    Получает актуальную аналитику спортсмена
    и формирует решение о тренировках на три дня.
    """

    analysis = get_registered_athlete_analysis(athlete_id)

    # Получаем контекст и рассчитанные зоны мощности.
    context = build_coach_context(analysis)

    power_zones = context.get("power_zones_watts", [])

    prompt = build_training_decision_prompt(analysis)

    response = ask_gemma(
        prompt,
        system_prompt=PLANNER_SYSTEM_PROMPT
    )

    result = extract_json(response)

    # Проверяем ответ Gemma по реальным зонам спортсмена.
    return validate_training_decision(
        result,
        power_zones=power_zones
    )