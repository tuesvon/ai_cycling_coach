
from statistics import mean, median

from src.analytics.workout_classification import (
    classify_workout,
    prepare_power_records,
    is_valid_number,
)


EFFORT_PROFILES = {
    "tempo": {
        "minimum_ftp_ratio": 0.76,
        "minimum_duration_seconds": 180,
    },
    "sweet_spot": {
        "minimum_ftp_ratio": 0.88,
        "minimum_duration_seconds": 120,
    },
    "threshold": {
        "minimum_ftp_ratio": 0.95,
        "minimum_duration_seconds": 45,
    },
    "vo2max_power": {
        "minimum_ftp_ratio": 1.06,
        "minimum_duration_seconds": 30,
    },
    "anaerobic_power": {
        "minimum_ftp_ratio": 1.21,
        "minimum_duration_seconds": 15,
    },
    "very_high_intensity": {
        "minimum_ftp_ratio": 1.50,
        "minimum_duration_seconds": 5,
    },
}


SMOOTHING_WINDOW_SECONDS = 5


def smooth_segment_power(
    segment,
    window_seconds=SMOOTHING_WINDOW_SECONDS,
):
    """
    Рассчитывает медианную мощность
    в центрированном временном окне.

    Используется исключительно для
    обнаружения границ усилий.

    Исходные значения не изменяются.
    """
    if (
        isinstance(window_seconds, bool)
        or not isinstance(window_seconds, int)
        or window_seconds <= 0
        or window_seconds % 2 == 0
    ):
        raise ValueError(
            "Размер окна должен быть "
            "положительным нечётным числом"
        )

    half_window = window_seconds // 2

    powers = [
        record["power"]
        for record in segment
    ]

    smoothed = []

    for index in range(len(powers)):
        start = max(
            0,
            index - half_window,
        )

        end = min(
            len(powers),
            index + half_window + 1,
        )

        smoothed.append(
            median(powers[start:end])
        )

    return smoothed


def build_detected_effort(
    records,
    ftp,
    effort_type,
    minimum_power,
):
    """
    Рассчитывает метрики обнаруженного
    усилия по исходным FIT-записям.
    """
    powers = [
        record["power"]
        for record in records
    ]

    heart_rates = [
        record["heart_rate"]
        for record in records
        if (
            is_valid_number(
                record.get("heart_rate")
            )
            and record["heart_rate"] > 0
        )
    ]

    cadences = [
        record["cadence"]
        for record in records
        if (
            is_valid_number(
                record.get("cadence")
            )
            and record["cadence"] >= 0
        )
    ]

    duration = len(records)

    average_power = mean(powers)

    seconds_above_threshold = sum(
        power >= minimum_power
        for power in powers
    )

    return {
        "effort_type": effort_type,

        "start": records[0][
            "timestamp"
        ].isoformat(),

        "end": records[-1][
            "timestamp"
        ].isoformat(),

        "duration_seconds": duration,

        "minimum_detection_power": round(
            minimum_power, 2
        ),

        "average_power": round(
            average_power, 2
        ),

        "average_power_ftp_percent": round(
            average_power / ftp * 100,
            2,
        ),

        "min_power": min(powers),

        "max_power": max(powers),

        "seconds_above_threshold": (
            seconds_above_threshold
        ),

        "above_threshold_ratio": round(
            seconds_above_threshold
            / duration,
            4,
        ),

        "average_heart_rate": (
            round(mean(heart_rates), 2)
            if heart_rates
            else None
        ),

        "max_heart_rate": (
            max(heart_rates)
            if heart_rates
            else None
        ),

        "heart_rate_samples": len(
            heart_rates
        ),

        "heart_rate_coverage_ratio": round(
            len(heart_rates) / duration,
            4,
        ),

        "average_cadence": (
            round(mean(cadences), 2)
            if cadences
            else None
        ),

        "boundary_confidence": (
            "estimated"
        ),
    }


def detect_efforts_in_segment(
    segment,
    smoothed_power,
    ftp,
    effort_type,
    minimum_ftp_ratio,
    minimum_duration_seconds,
):
    """
    Обнаруживает непрерывные усилия
    выше заданного порога FTP.

    Временные разрывы не пересекаются.
    """
    if len(segment) != len(smoothed_power):
        raise ValueError(
            "Размеры исходных и сглаженных "
            "записей не совпадают"
        )

    minimum_power = (
        ftp * minimum_ftp_ratio
    )

    efforts = []
    current_effort = []

    def save_effort():
        if (
            len(current_effort)
            < minimum_duration_seconds
        ):
            return

        effort = build_detected_effort(
            records=current_effort,
            ftp=ftp,
            effort_type=effort_type,
            minimum_power=minimum_power,
        )

        # Проверяем достаточную долю
        # записей выше рабочего порога.
        if effort["above_threshold_ratio"] < 0.80:
            return

        if mean(
            record["power"]
            for record in current_effort
        ) < minimum_power:
            return

        efforts.append(effort)

    for index, power in enumerate(
        smoothed_power
    ):
        if power >= minimum_power:
            current_effort.append(
                segment[index]
            )

        else:
            save_effort()
            current_effort = []

    save_effort()

    return efforts


def detect_workout_efforts(
    records,
    ftp,
):
    """
    Обнаруживает усилия различных
    диапазонов интенсивности.

    Возвращает независимые наборы
    усилий для каждого порога.

    Пересечения между профилями
    допустимы и сохраняются.
    """
    classification = classify_workout(
        records=records,
        ftp=ftp,
    )

    if classification["status"] != "ok":
        return {
            "status": "insufficient_data",

            "reason": classification.get(
                "reason"
            ),

            "classification": classification,

            "efforts_by_type": {},

            "summary": {},
        }

    prepared = prepare_power_records(
        records
    )

    segments = prepared["segments"]

    efforts_by_type = {
        effort_type: []
        for effort_type in EFFORT_PROFILES
    }

    for segment in segments:
        if not segment:
            continue

        smoothed_power = smooth_segment_power(
            segment
        )

        for effort_type, profile in (
            EFFORT_PROFILES.items()
        ):
            efforts = detect_efforts_in_segment(
                segment=segment,

                smoothed_power=smoothed_power,

                ftp=ftp,

                effort_type=effort_type,

                minimum_ftp_ratio=profile[
                    "minimum_ftp_ratio"
                ],

                minimum_duration_seconds=profile[
                    "minimum_duration_seconds"
                ],
            )

            efforts_by_type[
                effort_type
            ].extend(efforts)

    summary = {}

    for effort_type, efforts in (
        efforts_by_type.items()
    ):
        total_duration = sum(
            effort["duration_seconds"]
            for effort in efforts
        )

        average_power = None

        if total_duration:
            average_power = sum(
                effort["average_power"]
                * effort["duration_seconds"]
                for effort in efforts
            ) / total_duration

        summary[effort_type] = {
            "efforts_count": len(efforts),

            "total_duration_seconds": (
                total_duration
            ),

            "average_duration_seconds": (
                round(
                    total_duration / len(efforts),
                    2,
                )
                if efforts
                else None
            ),

            "average_power": (
                round(average_power, 2)
                if average_power is not None
                else None
            ),

            "longest_effort_seconds": max(
                (
                    effort["duration_seconds"]
                    for effort in efforts
                ),
                default=0,
            ),
        }

    return {
        "status": "ok",

        "ftp": ftp,

        "classification": classification,

        "efforts_by_type": efforts_by_type,

        "summary": summary,

        "settings": {
            "smoothing_window_seconds": (
                SMOOTHING_WINDOW_SECONDS
            ),

            "effort_profiles": {
                name: dict(profile)
                for name, profile
                in EFFORT_PROFILES.items()
            },
        },

        "limitations": [
            (
                "Обнаруженные усилия разных "
                "профилей могут пересекаться"
            ),
            (
                "Нельзя суммировать длительность "
                "усилий разных профилей"
            ),
            (
                "Название профиля обозначает "
                "порог мощности, а не доказанную "
                "физиологическую направленность"
            ),
            (
                "Сглаживание используется "
                "только для обнаружения границ"
            ),
            (
                "Очень короткие изменения "
                "мощности могут быть сглажены"
            ),
            (
                "Метрики рассчитываются "
                "по исходным FIT-записям"
            ),
            (
                "Обнаруженное усилие не обязательно "
                "является отдельным рабочим интервалом"
            ),
        ],
    }