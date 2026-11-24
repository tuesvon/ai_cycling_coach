from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_context import (
    classify_workout_context,
    get_activity_source_metadata,
)

from src.analytics.workout_effort_profile import (
    analyze_workout_effort_profile,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


def resolve_workout_ftp(
    activity,
    fallback_ftp=None,
):
    """
    Определяет FTP для анализа тренировки.

    Приоритет отдаётся FTP, указанному
    в метаданных конкретной активности.

    При отсутствии значения используется
    переданный резервный FTP.
    """
    metadata = get_activity_source_metadata(
        activity
    )

    intervals = metadata["intervals"]

    activity_ftp = intervals.get(
        "icu_ftp"
    )

    if (
        is_valid_number(activity_ftp)
        and activity_ftp > 0
    ):
        return {
            "ftp": activity_ftp,
            "source": "intervals.icu_ftp",
            "confidence": "activity_metadata",
        }

    if (
        is_valid_number(fallback_ftp)
        and fallback_ftp > 0
    ):
        return {
            "ftp": fallback_ftp,
            "source": "fallback",
            "confidence": "estimated",
        }

    return {
        "ftp": None,
        "source": None,
        "confidence": "unknown",
    }


def extract_workout_conditions(activity):
    """
    Извлекает доступные условия
    выполнения тренировки.

    Отсутствующие данные не заменяются
    нулевыми значениями.
    """
    metadata = get_activity_source_metadata(
        activity
    )

    intervals = metadata["intervals"]
    garmin = metadata["garmin"]

    trainer = intervals.get("trainer")

    intervals_type = intervals.get("type")

    garmin_activity_type = garmin.get(
        "activityType"
    )

    garmin_type_key = None

    if isinstance(
        garmin_activity_type,
        dict,
    ):
        garmin_type_key = (
            garmin_activity_type.get(
                "typeKey"
            )
        )

    if (
        trainer is True
        or intervals_type == "VirtualRide"
        or garmin_type_key in {
            "indoor_cycling",
            "virtual_ride",
        }
    ):
        environment = "indoor"

    elif (
        trainer is False
        and intervals_type == "Ride"
    ):
        environment = "outdoor"

    else:
        environment = "unknown"

    average_temperature = intervals.get(
        "average_temp"
    )

    if not is_valid_number(
        average_temperature
    ):
        average_temperature = None

    weather_temperature = intervals.get(
        "average_weather_temp"
    )

    if not is_valid_number(
        weather_temperature
    ):
        weather_temperature = None

    rpe = intervals.get("icu_rpe")

    if (
        not is_valid_number(rpe)
        or rpe < 0
        or rpe > 10
    ):
        rpe = None

    return {
        "environment": environment,

        "trainer": trainer,

        "intervals_activity_type": (
            intervals_type
        ),

        "garmin_activity_type": (
            garmin_type_key
        ),

        "average_temperature": (
            average_temperature
        ),

        "average_weather_temperature": (
            weather_temperature
        ),

        "rpe": rpe,

        "device_name": intervals.get(
            "device_name"
        ),

        "power_meter": intervals.get(
            "power_meter"
        ),

        "ignore_power": (
            intervals.get(
                "icu_ignore_power"
            ) is True
        ),

        "ignore_heart_rate": (
            intervals.get(
                "icu_ignore_hr"
            ) is True
        ),
    }


def compact_effort(effort):
    """
    Создаёт компактное описание усилия
    без дублирования исходных данных.
    """
    return {
        "effort_id": effort["effort_id"],

        "start": effort["start"],

        "end": effort["end"],

        "duration_seconds": effort[
            "duration_seconds"
        ],

        "average_power": effort.get(
            "average_power"
        ),

        "ftp_percent": effort.get(
            "actual_ftp_percent"
        ),

        "power_category": effort.get(
            "actual_power_category"
        ),

        "duration_category": effort.get(
            "duration_category"
        ),

        "detection_profile": effort.get(
            "detection_profile"
        ),

        "average_heart_rate": effort.get(
            "average_heart_rate"
        ),

        "max_heart_rate": effort.get(
            "max_heart_rate"
        ),

        "heart_rate_coverage_ratio": effort.get(
            "heart_rate_coverage_ratio"
        ),

        "average_cadence": effort.get(
            "average_cadence"
        ),

        "parent_effort_id": effort.get(
            "parent_effort_id"
        ),

        "child_effort_ids": list(
            effort.get(
                "child_effort_ids",
                [],
            )
        ),

        "overlapping_effort_ids": list(
            effort.get(
                "overlapping_effort_ids",
                [],
            )
        ),
    }


def summarize_root_efforts(efforts):
    """
    Группирует корневые усилия
    по фактической мощности.

    Корневые усилия не обязательно
    являются отдельными повторениями.
    """
    grouped = {}

    for effort in efforts:
        category = effort.get(
            "power_category"
        )

        if category is None:
            category = "unknown"

        if category not in grouped:
            grouped[category] = []

        grouped[category].append(
            effort
        )

    summary = {}

    for category, items in grouped.items():
        durations = [
            effort["duration_seconds"]
            for effort in items
        ]

        powers = [
            effort["average_power"]
            for effort in items
            if is_valid_number(
                effort.get("average_power")
            )
        ]

        ftp_percentages = [
            effort["ftp_percent"]
            for effort in items
            if is_valid_number(
                effort.get("ftp_percent")
            )
        ]

        summary[category] = {
            "efforts_count": len(items),

            "average_duration_seconds": round(
                mean(durations),
                2,
            ),

            "min_duration_seconds": min(
                durations
            ),

            "max_duration_seconds": max(
                durations
            ),

            "average_effort_power": (
                round(mean(powers), 2)
                if powers
                else None
            ),

            "average_ftp_percent": (
                round(
                    mean(ftp_percentages),
                    2,
                )
                if ftp_percentages
                else None
            ),

            "effort_ids": [
                effort["effort_id"]
                for effort in items
            ],
        }

    return summary


def analyze_between_effort_gaps(efforts):
    """
    Рассчитывает временные промежутки
    между соседними корневыми усилиями.

    Промежуток не считается автоматически
    физиологическим восстановлением.
    """
    if len(efforts) < 2:
        return []

    ordered = sorted(
        efforts,
        key=lambda effort: (
            parse_activity_date(
                effort["start"]
            )
        ),
    )

    gaps = []

    for index in range(
        len(ordered) - 1
    ):
        previous = ordered[index]
        following = ordered[index + 1]

        previous_end = parse_activity_date(
            previous["end"]
        )

        following_start = parse_activity_date(
            following["start"]
        )

        gap_seconds = (
            following_start
            - previous_end
        ).total_seconds() - 1

        if gap_seconds < 0:
            status = "overlap"
            duration_seconds = None

        else:
            status = "ok"

            duration_seconds = round(
                gap_seconds,
                2,
            )

        gaps.append({
            "previous_effort_id": previous[
                "effort_id"
            ],

            "next_effort_id": following[
                "effort_id"
            ],

            "status": status,

            "duration_seconds": (
                duration_seconds
            ),

            "previous_power_category": (
                previous["power_category"]
            ),

            "next_power_category": (
                following["power_category"]
            ),
        })

    return gaps


def build_workout_signature(
    activity,
    records,
    fallback_ftp=None,
):
    """
    Формирует единый профиль
    фактически выполненной тренировки.

    Название используется для контекста,
    но не для определения фактических
    усилий и продолжительности работы.
    """
    if not isinstance(activity, dict):
        raise ValueError(
            "Активность должна быть словарём"
        )

    ftp_info = resolve_workout_ftp(
        activity=activity,
        fallback_ftp=fallback_ftp,
    )

    context = classify_workout_context(
        activity
    )

    conditions = extract_workout_conditions(
        activity
    )

    result = {
        "status": "ok",

        "activity_id": activity.get("id"),

        "activity_name": context.get(
            "activity_name"
        ),

        "start_date": activity.get(
            "start_date"
        ),

        "ftp_info": ftp_info,

        "activity_context": context,

        "conditions": conditions,
    }

    if ftp_info["ftp"] is None:
        return {
            **result,

            "status": "insufficient_data",

            "reason": (
                "Не удалось определить FTP"
            ),
        }

    if conditions["ignore_power"]:
        return {
            **result,

            "status": "insufficient_data",

            "reason": (
                "Мощность исключена из анализа "
                "в настройках активности"
            ),
        }

    analysis_records = records

    # Если спортсмен исключил пульс
    # из анализа, не используем его
    # даже при наличии записей FIT.
    if (
        conditions["ignore_heart_rate"]
        and isinstance(records, list)
    ):
        analysis_records = [
            {
                key: value
                for key, value in record.items()
                if key != "heart_rate"
            }
            if isinstance(record, dict)
            else record
            for record in records
        ]

    profile = analyze_workout_effort_profile(
        records=analysis_records,
        ftp=ftp_info["ftp"],
    )

    if profile["status"] != "ok":
        return {
            **result,

            "status": "insufficient_data",

            "reason": profile.get(
                "reason"
            ),
        }

    resolution = profile[
        "original_resolution"
    ]

    detection = resolution[
        "original_detection"
    ]

    classification = detection[
        "classification"
    ]

    efforts = [
        compact_effort(effort)
        for effort in profile["efforts"]
    ]

    root_efforts = [
        effort
        for effort in efforts
        if effort["parent_effort_id"] is None
    ]

    nested_efforts = [
        effort
        for effort in efforts
        if effort["parent_effort_id"] is not None
    ]

    duration_seconds = classification[
        "duration_seconds"
    ]

    unique_work_seconds = profile[
        "summary"
    ]["unique_work_seconds"]

    work_fraction = (
        unique_work_seconds
        / duration_seconds
        if duration_seconds > 0
        else None
    )

    if not root_efforts:
        effort_structure = (
            "no_detected_efforts"
        )

    elif len(root_efforts) == 1:
        effort_structure = (
            "single_root_effort"
        )

    else:
        effort_structure = (
            "multiple_root_efforts"
        )

    return {
        **result,

        "load_profile": {
            "power_pattern": classification[
                "workout_type"
            ],

            "dominant_power_zone": (
                classification[
                    "dominant_power_zone"
                ]
            ),

            "duration_seconds": (
                duration_seconds
            ),

            "average_power": classification[
                "average_power"
            ],

            "average_power_ftp_percent": (
                classification[
                    "average_power_ftp_percent"
                ]
            ),

            "power_cv_percent": classification[
                "power_cv_percent"
            ],

            "power_zone_distribution": (
                classification[
                    "power_zone_distribution"
                ]
            ),
        },

        "effort_structure": {
            "structure_type": (
                effort_structure
            ),

            "root_efforts_count": len(
                root_efforts
            ),

            "nested_efforts_count": len(
                nested_efforts
            ),

            "unique_work_seconds": (
                unique_work_seconds
            ),

            "work_fraction": (
                round(work_fraction, 4)
                if work_fraction is not None
                else None
            ),

            "root_effort_summary": (
                summarize_root_efforts(
                    root_efforts
                )
            ),

            "category_summary": profile[
                "category_summary"
            ],

            "root_efforts": root_efforts,

            "nested_efforts": nested_efforts,

            "between_effort_gaps": (
                analyze_between_effort_gaps(
                    root_efforts
                )
            ),

            "partially_overlapping_efforts_count": (
                resolution["summary"][
                    "partially_overlapping_efforts_count"
                ]
            ),
        },

        "data_quality": classification.get(
            "data_quality",
            {},
        ),

        "limitations": [
            (
                "FTP из метаданных активности "
                "может требовать подтверждения"
            ),
            (
                "Резервный FTP может отличаться "
                "от исторического FTP"
            ),
            (
                "Контекст активности является "
                "предполагаемым"
            ),
            (
                "Корневое усилие не обязательно "
                "является отдельным повторением"
            ),
            (
                "Промежутки между усилиями "
                "не обязательно являются отдыхом"
            ),
            (
                "Уникальное время обнаруженных "
                "усилий не равно времени "
                "в конкретной зоне мощности"
            ),
            (
                "Отсутствие обнаруженных усилий "
                "не означает отсутствие нагрузки"
            ),
            (
                "Температура датчика не обязательно "
                "соответствует температуре воздуха"
            ),
        ],
    }