
from collections import defaultdict
from statistics import mean
from math import isfinite


def is_valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def calculate_hr_by_power(
    records,
    power_step=10,
    min_samples=30,
):
    """
    Рассчитывает средний пульс по диапазонам мощности.

    records:
        [
            {"power": 200, "heart_rate": 140},
            ...
        ]

    power_step:
        Ширина диапазона мощности в ваттах.

    min_samples:
        Минимальное число секунд для диапазона.

    Предполагается одна запись в секунду.
    """
    if not isinstance(records, list):
        raise ValueError("Записи должны быть списком")

    if (
        isinstance(power_step, bool)
        or not isinstance(power_step, int)
        or power_step <= 0
    ):
        raise ValueError("Некорректный шаг мощности")

    if (
        isinstance(min_samples, bool)
        or not isinstance(min_samples, int)
        or min_samples <= 0
    ):
        raise ValueError("Некорректное число записей")

    groups = defaultdict(list)

    for record in records:
        if not isinstance(record, dict):
            continue

        power = record.get("power")
        heart_rate = record.get("heart_rate")

        if not is_valid_number(power):
            continue

        if not is_valid_number(heart_rate):
            continue

        if power < 0 or heart_rate <= 0:
            continue

        zone_start = int(power // power_step) * power_step

        groups[zone_start].append(heart_rate)

    result = {}

    for zone_start, heart_rates in sorted(groups.items()):
        if len(heart_rates) < min_samples:
            continue

        result[zone_start] = {
            "power_min": zone_start,
            "power_max": zone_start + power_step - 1,
            "average_hr": round(mean(heart_rates), 2),
            "samples": len(heart_rates),
        }

    return result


def compare_hr_at_same_power(
    latest_records,
    previous_records,
    power_step=10,
    min_samples=30,
):
    """
    Сравнивает пульс в одинаковых диапазонах мощности.

    Отрицательная разница означает, что в последней
    тренировке пульс был ниже.

    Не делает выводов о физической форме спортсмена.
    """
    latest = calculate_hr_by_power(
        latest_records,
        power_step=power_step,
        min_samples=min_samples,
    )

    previous = calculate_hr_by_power(
        previous_records,
        power_step=power_step,
        min_samples=min_samples,
    )

    common_zones = sorted(
        set(latest) & set(previous)
    )

    comparisons = []

    for zone in common_zones:
        current = latest[zone]
        old = previous[zone]

        difference = (
            current["average_hr"] - old["average_hr"]
        )

        comparisons.append({
            "power_min": current["power_min"],
            "power_max": current["power_max"],
            "latest_average_hr": current["average_hr"],
            "previous_average_hr": old["average_hr"],
            "difference_bpm": round(difference, 2),
            "latest_samples": current["samples"],
            "previous_samples": old["samples"],
        })

    return {
        "status": "ok" if comparisons else "insufficient_data",
        "comparison_type": "heart_rate_at_same_power",
        "power_step": power_step,
        "compared_power_ranges": len(comparisons),
        "ranges": comparisons,
        "limitations": (
            "Сравнение выполнено по диапазонам мощности. "
            "Пока не учитываются задержка реакции пульса, "
            "порядок интервалов, температура, усталость "
            "и аэробный дрейф."
        ),
    }
