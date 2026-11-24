
from datetime import date, timedelta

from src.assistant.training_periodization import (
    calculate_preparation_window,
)


ALLOWED_PHASES = {
    "base",
    "build",
    "specific",
    "taper",
    "transition",
}


def validate_periodization(data, goal, start_date=None):
    """
    Проверяет долгосрочный план, предложенный Gemma.

    Блоки должны:
    - покрывать весь период до главной гонки;
    - идти подряд, без пропусков и пересечений;
    - не включать день главного соревнования;
    - содержать объяснение цели каждого блока.
    """
    if not isinstance(data, dict):
        raise ValueError("Периодизация должна быть словарём")

    if not isinstance(goal, dict):
        raise ValueError("Главная цель должна быть словарём")

    event_date = goal.get("event_date")

    window = calculate_preparation_window(
        event_date=event_date,
        start_date=start_date,
    )

    preparation_start = date.fromisoformat(
        window["start_date"]
    )
    event = date.fromisoformat(window["event_date"])

    blocks = data.get("blocks")

    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Отсутствуют блоки подготовки")

    explanation = data.get("explanation")

    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Отсутствует объяснение стратегии")

    expected_start = preparation_start
    validated_blocks = []

    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise ValueError(f"Блок {index}: некорректные данные")

        phase = block.get("phase")

        if phase not in ALLOWED_PHASES:
            raise ValueError(
                f"Блок {index}: неизвестная фаза {phase}"
            )

        try:
            block_start = date.fromisoformat(
                block["start_date"]
            )
            block_end = date.fromisoformat(
                block["end_date"]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"Блок {index}: некорректные даты"
            ) from error

        if block_start != expected_start:
            raise ValueError(
                f"Блок {index}: пропуск или пересечение дат. "
                f"Ожидалось начало {expected_start}"
            )

        if block_end < block_start:
            raise ValueError(
                f"Блок {index}: конец раньше начала"
            )

        if block_end >= event:
            raise ValueError(
                f"Блок {index}: блок включает день гонки "
                "или выходит за него"
            )

        focus = block.get("focus")

        if not isinstance(focus, str) or not focus.strip():
            raise ValueError(
                f"Блок {index}: отсутствует задача подготовки"
            )

        duration_days = (
            block_end - block_start
        ).days + 1

        validated_blocks.append({
            "phase": phase,
            "start_date": block_start.isoformat(),
            "end_date": block_end.isoformat(),
            "duration_days": duration_days,
            "focus": focus.strip(),
        })

        expected_start = block_end + timedelta(days=1)

    if expected_start != event:
        raise ValueError(
            "Периодизация не покрывает весь срок "
            "до главного соревнования"
        )

    return {
        "explanation": explanation.strip(),
        "start_date": preparation_start.isoformat(),
        "event_date": event.isoformat(),
        "total_days": window["preparation_days"],
        "blocks": validated_blocks,
    }
