from datetime import date

def validate_weekly_adaptation(data, context, today=None):
    if today is None:
        today = date.today()

    if isinstance(today, str):
        today = date.fromisoformat(today)

    if not isinstance(today, date):
        raise ValueError("today должен быть датой")
    """
    Проверяет предложение Gemma по адаптации недельного плана.

    Не изменяет данные и не сохраняет результат в SQLite.
    """
    if not isinstance(data, dict):
        raise ValueError("Решение Gemma должно быть JSON-объектом")

    if not isinstance(context, dict):
        raise ValueError("Контекст должен быть словарём")

    decision = data.get("decision")

    if decision not in ("keep", "adapt"):
        raise ValueError("decision должен быть keep или adapt")

    explanation = data.get("explanation")

    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Необходимо объяснение решения")

    changes = data.get("changes")

    if not isinstance(changes, list):
        raise ValueError("changes должен быть списком")

    if decision == "keep" and changes:
        raise ValueError("При keep список changes должен быть пустым")

    if decision == "adapt" and not changes:
        raise ValueError("При adapt необходимы изменения")

    weekly_plan = context.get("weekly_plan", {})
    workouts = weekly_plan.get("workouts", [])

    workouts_by_id = {
        workout["id"]: workout
        for workout in workouts
    }

    power_zones = context.get("athlete", {}).get(
        "power_zones_watts", []
    )

    zones_by_name = {
        zone["name"]: zone
        for zone in power_zones
    }

    seen_ids = set()

    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Каждое изменение должно быть словарём")

        workout_id = change.get("workout_id")

        if type(workout_id) is not int:
            raise ValueError("workout_id должен быть целым числом")

        if workout_id in seen_ids:
            raise ValueError("Повторное изменение одной тренировки")

        seen_ids.add(workout_id)

        if workout_id not in workouts_by_id:
            raise ValueError(
                f"Тренировка {workout_id} отсутствует в недельном плане"
            )

        original = workouts_by_id[workout_id]

        if original.get("status") != "planned":
            raise ValueError(
                f"Тренировку {workout_id} нельзя изменить: "
                "она уже выполнена или имеет другой статус"
            )

        workout_date = date.fromisoformat(original["date"])

        if workout_date < today:
            raise ValueError(
                f"Нельзя изменять тренировку за {workout_date}: "
                "дата уже прошла"
            )

        new_workout = change.get("new_workout")

        if not isinstance(new_workout, dict):
            raise ValueError("new_workout должен быть словарём")

        if new_workout.get("date") != original["date"]:
            raise ValueError("Нельзя изменять дату тренировки")

        workout_type = new_workout.get("type")
        duration = new_workout.get("duration_minutes")
        power_zone = new_workout.get("power_zone")

        if not isinstance(workout_type, str) or not workout_type.strip():
            raise ValueError("Не указан тип тренировки")

        if not isinstance(new_workout.get("purpose"), str) or not new_workout["purpose"].strip():
            raise ValueError("Не указана цель тренировки")

        if duration is not None:
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or duration <= 0
            ):
                raise ValueError("Некорректная продолжительность")

        if workout_type.strip().lower() == "rest":
            if power_zone is not None:
                raise ValueError("Для отдыха зона мощности должна быть null")
            if duration is not None:
                raise ValueError("Для отдыха продолжительность должна быть null")

        else:
            if power_zone not in zones_by_name:
                raise ValueError(
                    f"Неизвестная зона мощности: {power_zone}"
                )

        power_range = new_workout.get("power_range_watts")

        if power_range is not None:
            if workout_type.strip().lower() == "rest":
                raise ValueError(
                    "Для отдыха диапазон мощности должен быть null"
                )

            if not isinstance(power_range, str):
                raise ValueError(
                    "Диапазон мощности должен быть строкой"
                )

            zone = zones_by_name[power_zone]

            min_watts = zone["min_watts"]
            max_watts = zone.get("max_watts")

            if max_watts is None:
                expected_range = f"{min_watts}+"
            else:
                expected_range = f"{min_watts}-{max_watts}"

            if power_range != expected_range:
                raise ValueError(
                    f"Неверный диапазон мощности для {power_zone}: "
                    f"{power_range}. Ожидается {expected_range}"
                )

        for field in ("change_reason", "impact_on_goal"):
            value = change.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Необходимо заполнить {field}")

    return data