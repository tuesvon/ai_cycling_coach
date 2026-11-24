from math import isfinite
from statistics import mean, pstdev


def is_valid_record(record):
    """
    Проверяет наличие корректной мощности и пульса.
    """
    if not isinstance(record, dict):
        return False

    power = record.get("power")
    heart_rate = record.get("heart_rate")

    for value in (power, heart_rate):
        if isinstance(value, bool):
            return False

        if not isinstance(value, (int, float)):
            return False

        if not isfinite(value):
            return False

    return power > 0 and heart_rate > 0


def calculate_aerobic_drift(
    records,
    min_samples=600,
    max_power_difference=0.10,
):
    """
    Рассчитывает аэробный дрейф между половинами
    тренировки.

    Предполагается, что записи идут последовательно
    с интервалом в одну секунду.

    min_samples — минимум валидных записей
    в каждой половине.

    max_power_difference — максимально допустимая
    относительная разница средней мощности
    между половинами.

    Для интервальных тренировок результат может
    быть недостаточно информативным.
    """
    if not isinstance(records, list):
        raise ValueError("Записи должны быть списком")

    if (
        isinstance(min_samples, bool)
        or not isinstance(min_samples, int)
        or min_samples <= 0
    ):
        raise ValueError("Некорректное число записей")

    if (
        isinstance(max_power_difference, bool)
        or not isinstance(max_power_difference, (int, float))
        or not isfinite(max_power_difference)
        or max_power_difference < 0
    ):
        raise ValueError("Некорректный допуск мощности")

    if not records:
        return {
            "status": "insufficient_data",
            "reason": "Нет записей тренировки",
        }

    midpoint = len(records) // 2

    first_half = [
        record
        for record in records[:midpoint]
        if is_valid_record(record)
    ]

    second_half = [
        record
        for record in records[midpoint:]
        if is_valid_record(record)
    ]

    if (
        len(first_half) < min_samples
        or len(second_half) < min_samples
    ):
        return {
            "status": "insufficient_data",
            "reason": (
                "Недостаточно записей мощности и пульса "
                "в одной или обеих половинах тренировки"
            ),
        }

    power_first = mean(
        record["power"] for record in first_half
    )

    power_second = mean(
        record["power"] for record in second_half
    )

    hr_first = mean(
        record["heart_rate"] for record in first_half
    )

    hr_second = mean(
        record["heart_rate"] for record in second_half
    )

    power_difference = abs(
        power_second - power_first
    ) / power_first

    if power_difference > max_power_difference:
        return {
            "status": "not_comparable",
            "reason": (
                "Средняя мощность между половинами "
                "тренировки отличается слишком сильно"
            ),
            "power_difference_percent": round(
                power_difference * 100, 2
            ),
        }

    efficiency_first = power_first / hr_first
    efficiency_second = power_second / hr_second

    drift_percent = (
        efficiency_first / efficiency_second - 1
    ) * 100

    return {
        "status": "ok",
        "drift_percent": round(drift_percent, 2),
        "first_half": {
            "average_power": round(power_first, 2),
            "average_hr": round(hr_first, 2),
            "efficiency_factor": round(
                efficiency_first, 4
            ),
            "samples": len(first_half),
        },
        "second_half": {
            "average_power": round(power_second, 2),
            "average_hr": round(hr_second, 2),
            "efficiency_factor": round(
                efficiency_second, 4
            ),
            "samples": len(second_half),
        },
        "power_difference_percent": round(
            power_difference * 100, 2
        ),
        "limitations": (
            "Предварительная оценка аэробного дрейфа. "
            "Не учитывает разминку, заминку, остановки, "
            "температуру, интервальную структуру "
            "и временную задержку реакции пульса."
        ),
    }

def assess_power_stability(
    records,
    max_cv_percent=15.0,
    min_samples=1200,
):
    """
    Предварительно оценивает стабильность мощности.

    CV = стандартное отклонение мощности /
         средняя мощность * 100.

    Низкий CV не гарантирует отсутствие интервалов.
    Высокий CV не обязательно означает плохие данные.
    """
    if not isinstance(records, list):
        raise ValueError("Записи должны быть списком")

    if (
        isinstance(min_samples, bool)
        or not isinstance(min_samples, int)
        or min_samples <= 0
    ):
        raise ValueError("Некорректное число записей")

    if (
        isinstance(max_cv_percent, bool)
        or not isinstance(max_cv_percent, (int, float))
        or not isfinite(max_cv_percent)
        or max_cv_percent < 0
    ):
        raise ValueError("Некорректный порог CV")

    valid_records = [
        record
        for record in records
        if is_valid_record(record)
    ]

    if len(valid_records) < min_samples:
        return {
            "status": "insufficient_data",
            "reason": "Недостаточно валидных записей",
        }

    powers = [
        record["power"]
        for record in valid_records
    ]

    average_power = mean(powers)

    if average_power <= 0:
        return {
            "status": "insufficient_data",
            "reason": "Некорректная средняя мощность",
        }

    cv_percent = (
        pstdev(powers) / average_power
    ) * 100

    return {
        "status": "ok",
        "average_power": round(average_power, 2),
        "power_cv_percent": round(cv_percent, 2),
        "is_stable": cv_percent <= max_cv_percent,
        "samples": len(valid_records),
        "limitations": (
            "Оценка стабильности по коэффициенту "
            "вариации мощности. Не учитывает "
            "структуру интервалов и остановки."
        ),
    }


def analyze_aerobic_drift_quality(
    records,
    max_cv_percent=15.0,
    min_samples=1200,
):
    """
    Анализирует аэробный дрейф с предварительной
    проверкой стабильности мощности.

    Возможные статусы:
    - ok: расчёт выполнен;
    - not_comparable: мощность слишком нестабильна;
    - insufficient_data: недостаточно данных.

    Статус ok не означает, что условия тренировки
    полностью сопоставимы с другими тренировками.
    """
    stability = assess_power_stability(
        records=records,
        max_cv_percent=max_cv_percent,
        min_samples=min_samples,
    )

    if stability["status"] != "ok":
        return {
            "status": "insufficient_data",
            "reason": stability.get(
                "reason",
                "Недостаточно данных для проверки мощности",
            ),
            "power_stability": stability,
        }

    if not stability["is_stable"]:
        return {
            "status": "not_comparable",
            "reason": (
                "Мощность слишком нестабильна для "
                "предварительной оценки аэробного дрейфа"
            ),
            "power_stability": stability,
        }

    drift = calculate_aerobic_drift(
        records=records,
    )

    return {
        **drift,
        "power_stability": stability,
    }
