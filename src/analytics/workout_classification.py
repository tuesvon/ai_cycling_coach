from datetime import datetime, timezone
from math import isfinite
from statistics import mean, pstdev


POWER_ZONES = (
    ("recovery", 0.55),
    ("endurance", 0.75),
    ("tempo", 0.90),
    ("threshold", 1.05),
    ("vo2max", 1.20),
    ("anaerobic", 1.50),
    ("high_intensity", float("inf")),
)

MIN_CLASSIFICATION_RECORDS = 300
MIN_HIGH_INTENSITY_SECONDS = 15
HIGH_INTENSITY_FTP_RATIO = 1.10
MAX_STEADY_CV_PERCENT = 15.0


def is_valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def prepare_power_records(records):
    """
    Подготавливает записи мощности.

    Пульс не является обязательным
    для классификации тренировки.

    Разделяет данные на непрерывные
    односекундные сегменты.
    """
    if not isinstance(records, list):
        raise ValueError(
            "Записи должны быть списком"
        )

    prepared = []

    for record in records:
        if not isinstance(record, dict):
            continue

        timestamp = record.get("timestamp")
        power = record.get("power")

        if not isinstance(timestamp, datetime):
            continue

        if not is_valid_number(power):
            continue

        if power < 0:
            continue

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )
        else:
            timestamp = timestamp.astimezone(
                timezone.utc
            )

        prepared.append({
            **record,
            "timestamp": timestamp,
        })

    prepared.sort(
        key=lambda record: record["timestamp"]
    )

    segments = []
    current_segment = []
    duplicate_timestamps = 0

    for record in prepared:
        if current_segment:
            previous = current_segment[-1]

            seconds = (
                record["timestamp"]
                - previous["timestamp"]
            ).total_seconds()

            if seconds == 0:
                duplicate_timestamps += 1
                continue

            if abs(seconds - 1.0) >= 0.01:
                segments.append(
                    current_segment
                )

                current_segment = []

        current_segment.append(record)

    if current_segment:
        segments.append(current_segment)

    valid_records = [
        record
        for segment in segments
        for record in segment
    ]

    return {
        "records": valid_records,
        "segments": segments,
        "duplicate_timestamps": (
            duplicate_timestamps
        ),
    }


def get_power_zone(power, ftp):
    """
    Определяет диапазон мощности
    относительно FTP.

    Используются предварительные
    классификационные границы.
    """
    ratio = power / ftp

    for zone_name, upper_limit in POWER_ZONES:
        if ratio <= upper_limit:
            return zone_name

    return "high_intensity"


def calculate_power_zone_distribution(
    records,
    ftp,
):
    """
    Рассчитывает распределение записей
    по диапазонам мощности.

    Для регулярной односекундной записи
    количество записей соответствует секундам.
    """
    distribution = {
        zone_name: {
            "seconds": 0,
            "percent": 0.0,
        }
        for zone_name, _ in POWER_ZONES
    }

    for record in records:
        zone = get_power_zone(
            record["power"],
            ftp,
        )

        distribution[zone]["seconds"] += 1

    total = len(records)

    if total:
        for values in distribution.values():
            values["percent"] = round(
                values["seconds"] / total * 100,
                2,
            )

    return distribution


def build_high_intensity_interval(
    records,
    ftp,
):
    """
    Формирует описание непрерывного
    интенсивного отрезка.
    """
    powers = [
        record["power"]
        for record in records
    ]

    average_power = mean(powers)

    return {
        "start": records[0][
            "timestamp"
        ].isoformat(),

        "end": records[-1][
            "timestamp"
        ].isoformat(),

        "duration_seconds": len(records),

        "average_power": round(
            average_power, 2
        ),

        "max_power": round(
            max(powers), 2
        ),

        "average_power_ftp_percent": round(
            average_power / ftp * 100,
            2,
        ),
    }


def detect_high_intensity_intervals(
    segments,
    ftp,
    min_duration_seconds=(
        MIN_HIGH_INTENSITY_SECONDS
    ),
    intensity_ratio=HIGH_INTENSITY_FTP_RATIO,
):
    """
    Находит непрерывные отрезки мощности
    выше заданной доли FTP.

    Не объединяет отрезки через
    временные разрывы.

    Это предварительное обнаружение,
    а не полноценное распознавание
    запланированных рабочих интервалов.
    """
    threshold = ftp * intensity_ratio

    intervals = []

    for segment in segments:
        current_interval = []

        for record in segment:
            if record["power"] >= threshold:
                current_interval.append(
                    record
                )

            else:
                if (
                    len(current_interval)
                    >= min_duration_seconds
                ):
                    intervals.append(
                        build_high_intensity_interval(
                            current_interval,
                            ftp,
                        )
                    )

                current_interval = []

        if (
            len(current_interval)
            >= min_duration_seconds
        ):
            intervals.append(
                build_high_intensity_interval(
                    current_interval,
                    ftp,
                )
            )

    return intervals


def classify_workout(
    records,
    ftp,
):
    """
    Классифицирует характер тренировки
    по фактическим данным мощности.

    Не определяет физиологическую
    направленность только по мощности.

    Возвращает:
    - характер нагрузки;
    - преобладающую зону;
    - распределение мощности;
    - интенсивные отрезки;
    - качество исходных данных.
    """
    if not is_valid_number(ftp) or ftp <= 0:
        return {
            "status": "insufficient_data",
            "workout_type": "unknown",
            "reason": "Нет корректного FTP",
        }

    prepared = prepare_power_records(
        records
    )

    power_records = prepared["records"]
    segments = prepared["segments"]

    count = len(power_records)

    if count < MIN_CLASSIFICATION_RECORDS:
        return {
            "status": "insufficient_data",
            "workout_type": "unknown",
            "reason": (
                "Недостаточно записей мощности"
            ),
            "valid_records": count,
        }

    elapsed_seconds = (
        power_records[-1]["timestamp"]
        - power_records[0]["timestamp"]
    ).total_seconds() + 1

    coverage_ratio = min(
        count / elapsed_seconds,
        1.0,
    )

    valid_records_ratio = (
        count / len(records)
        if records
        else 0
    )

    regular_intervals = sum(
        max(0, len(segment) - 1)
        for segment in segments
    )

    regular_timing_ratio = (
        regular_intervals / (count - 1)
        if count > 1
        else 0
    )

    quality = {
        "valid_records": count,

        "valid_records_ratio": round(
            valid_records_ratio, 4
        ),

        "time_coverage_ratio": round(
            coverage_ratio, 4
        ),

        "regular_timing_ratio": round(
            regular_timing_ratio, 4
        ),

        "continuous_segments_count": len(
            segments
        ),

        "duplicate_timestamps": prepared[
            "duplicate_timestamps"
        ],
    }

    if (
        coverage_ratio < 0.99
        or valid_records_ratio < 0.99
        or regular_timing_ratio < 0.99
        or prepared["duplicate_timestamps"] > 0
    ):
        return {
            "status": "insufficient_data",
            "workout_type": "unknown",
            "reason": (
                "Недостаточное качество "
                "временных записей мощности"
            ),
            "data_quality": quality,
        }

    powers = [
        record["power"]
        for record in power_records
    ]

    average_power = mean(powers)

    if average_power <= 0:
        return {
            "status": "insufficient_data",
            "workout_type": "unknown",
            "reason": (
                "Отсутствует положительная "
                "средняя мощность"
            ),
            "data_quality": quality,
        }

    power_cv = (
        pstdev(powers)
        / average_power
        * 100
    )

    distribution = (
        calculate_power_zone_distribution(
            power_records,
            ftp,
        )
    )

    dominant_zone = max(
        distribution,
        key=lambda zone: distribution[
            zone
        ]["seconds"],
    )

    intervals = detect_high_intensity_intervals(
        segments=segments,
        ftp=ftp,
    )

    intervals_count = len(intervals)

    high_intensity_seconds = sum(
        interval["duration_seconds"]
        for interval in intervals
    )

    if intervals_count >= 2:
        workout_type = "interval"

    elif power_cv <= MAX_STEADY_CV_PERCENT:
        workout_type = "steady"

    else:
        workout_type = "variable"

    if intervals:
        interval_average_power = (
            sum(
                interval["average_power"]
                * interval["duration_seconds"]
                for interval in intervals
            )
            / high_intensity_seconds
        )

        average_interval_duration = mean(
            interval["duration_seconds"]
            for interval in intervals
        )

    else:
        interval_average_power = None
        average_interval_duration = None

    return {
        "status": "ok",

        "workout_type": workout_type,

        "dominant_power_zone": dominant_zone,

        "ftp": ftp,

        "duration_seconds": count,

        "average_power": round(
            average_power, 2
        ),

        "average_power_ftp_percent": round(
            average_power / ftp * 100,
            2,
        ),

        "power_cv_percent": round(
            power_cv, 2
        ),

        "power_zone_distribution": (
            distribution
        ),

        "high_intensity": {
            "threshold_watts": round(
                ftp * HIGH_INTENSITY_FTP_RATIO,
                2,
            ),

            "intervals_count": intervals_count,

            "total_duration_seconds": (
                high_intensity_seconds
            ),

            "average_interval_duration_seconds": (
                round(
                    average_interval_duration,
                    2,
                )
                if average_interval_duration
                is not None
                else None
            ),

            "average_interval_power": (
                round(
                    interval_average_power, 2
                )
                if interval_average_power
                is not None
                else None
            ),

            "intervals": intervals,
        },

        "data_quality": quality,

        "limitations": [
            (
                "Классификация основана "
                "на фактической мощности"
            ),
            (
                "Кратковременные снижения мощности "
                "могут разделять один рабочий "
                "интервал на несколько отрезков"
            ),
            (
                "Пороговые и Sweet Spot интервалы "
                "пока не выделяются отдельно"
            ),
            (
                "Преобладающая зона не определяет "
                "физиологическую цель тренировки"
            ),
            (
                "Требуется FTP, актуальный "
                "на дату выполнения тренировки"
            ),
        ],
    }