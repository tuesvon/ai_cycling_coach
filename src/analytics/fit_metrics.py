from io import BytesIO
from fitparse import FitFile
import numpy as np


def read_fit_file(file_path):
    """Читает FIT-файл и возвращает список записей."""

    fit_file = FitFile(str(file_path))

    records = []

    for message in fit_file.get_messages("record"):
        record = {}

        for field in message:
            if field.value is not None:
                record[field.name] = field.value

        if record.get("timestamp") is not None:
            records.append(record)

    return records


def calculate_average(values):
    """Рассчитывает среднее значение."""

    valid_values = [
        value for value in values
        if value is not None
    ]

    if not valid_values:
        return None

    return round(float(np.mean(valid_values)), 2)


def calculate_max(values):
    """Рассчитывает максимальное значение."""

    valid_values = [
        value for value in values
        if value is not None
    ]

    if not valid_values:
        return None

    return max(valid_values)


def calculate_power_zone_boundaries(ftp, power_zones):
    boundaries = []

    for percentage in power_zones[:-1]:
        boundaries.append(round(ftp * percentage / 100))

    return boundaries


def calculate_normalized_power(power_values):
    """
    Рассчитывает приближённый Normalized Power.
    Использует 30-секундное скользящее среднее,
    возведение в четвёртую степень и корень четвёртой степени.
    """

    power = np.array([
        value if value is not None else 0
        for value in power_values
    ], dtype=float)

    if len(power) < 30:
        return None

    rolling_power = np.convolve(
        power,
        np.ones(30) / 30,
        mode="valid"
    )

    normalized_power = np.mean(rolling_power ** 4) ** 0.25

    return round(float(normalized_power), 1)


def calculate_intensity_factor(normalized_power, ftp):
    if normalized_power is None or ftp <= 0:
        return None

    return round(normalized_power / ftp, 3)


def calculate_tss(duration_seconds, intensity_factor):
    if intensity_factor is None:
        return None

    tss = (
        duration_seconds
        * intensity_factor ** 2
        / 3600
        * 100
    )

    return round(tss, 1)

def calculate_time_in_zones(values, zone_boundaries):
    """
    Рассчитывает время в зонах.
    Предполагается, что одна запись FIT соответствует одной секунде.
    """

    zones = {}

    for index, upper_limit in enumerate(zone_boundaries):
        zones[f"Z{index + 1}"] = 0

    for value in values:
        if value is None:
            continue

        for index, upper_limit in enumerate(zone_boundaries):
            if value <= upper_limit:
                zones[f"Z{index + 1}"] += 1
                break

    return zones

def calculate_time_in_range(records, field_name, lower_limit, upper_limit):
    total_seconds = 0

    if len(records) < 2:
        return 0

    for index in range(len(records) - 1):
        current_time = records[index]["timestamp"]
        next_time = records[index + 1]["timestamp"]

        seconds = (next_time - current_time).total_seconds()

        # Не учитываем большие пропуски в данных
        if seconds <= 0 or seconds > 5:
            continue

        value = records[index].get(field_name)

        if value is None:
            continue

        if lower_limit <= value <= upper_limit:
            total_seconds += seconds

    return round(total_seconds, 1)

def analyze_fit_file(file_path, profile):
    """Выполняет базовый анализ FIT-файла."""

    records = read_fit_file(file_path)

    power = [record.get("power") for record in records]
    heart_rate = [record.get("heart_rate") for record in records]
    cadence = [record.get("cadence") for record in records]

    power = [
        value if value is not None else None
        for value in power
    ]

    power_zone_boundaries = calculate_power_zone_boundaries(
        profile["ftp"],
        profile["power_zones"]
    )

    hr_zone_boundaries = profile["hr_zones"]

    normalized_power = calculate_normalized_power(power)

    intensity_factor = calculate_intensity_factor(
        normalized_power,
        profile["ftp"]
    )

    duration_seconds = (
            records[-1]["timestamp"] - records[0]["timestamp"]
    ).total_seconds()

    return {
        "records_count": len(records),

        "average_power": calculate_average(power),
        "max_power": calculate_max(power),
        "normalized_power": normalized_power,
        "intensity_factor": intensity_factor,
        "tss": calculate_tss(duration_seconds, intensity_factor),
        "average_hr": calculate_average(heart_rate),
        "max_hr": calculate_max(heart_rate),

        "average_cadence": calculate_average(cadence),
        "max_cadence": calculate_max(cadence),

        "power_zones_time": calculate_time_in_zones(
            power,
            power_zone_boundaries
        ),

        "hr_zones_time": calculate_time_in_zones(
            heart_rate,
            hr_zone_boundaries
        ),
        "sweet_spot_time": calculate_time_in_range(
            records,
            "power",
            255,
            294
        )
    }
