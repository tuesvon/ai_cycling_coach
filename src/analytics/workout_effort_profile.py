from copy import deepcopy

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_effort_resolution import (
    analyze_resolved_workout_efforts,
    calculate_unique_effort_seconds,
)


POWER_CATEGORIES = (
    "recovery",
    "endurance",
    "tempo",
    "sweet_spot",
    "threshold",
    "vo2max_power",
    "anaerobic_power",
    "very_high_intensity",
)


def classify_effort_power(
    average_power,
    ftp,
):
    """
    Определяет категорию фактической
    средней мощности усилия.

    Категория не является доказательством
    физиологической направленности работы.
    """
    if (
        not is_valid_number(ftp)
        or ftp <= 0
        or not is_valid_number(average_power)
        or average_power < 0
    ):
        return "unknown"

    ratio = average_power / ftp

    if ratio <= 0.55:
        return "recovery"

    if ratio <= 0.75:
        return "endurance"

    if ratio < 0.88:
        return "tempo"

    if ratio < 0.95:
        return "sweet_spot"

    if ratio <= 1.05:
        return "threshold"

    if ratio <= 1.20:
        return "vo2max_power"

    if ratio <= 1.50:
        return "anaerobic_power"

    return "very_high_intensity"


def classify_effort_duration(
    duration_seconds,
):
    """
    Описывает продолжительность усилия.

    Не определяет тип метаболической
    нагрузки или цель тренировки.
    """
    if (
        not is_valid_number(duration_seconds)
        or duration_seconds <= 0
    ):
        return "unknown"

    if duration_seconds < 15:
        return "very_short"

    if duration_seconds < 60:
        return "short"

    if duration_seconds < 180:
        return "medium"

    if duration_seconds < 480:
        return "long"

    if duration_seconds < 1200:
        return "extended"

    return "sustained"


def enrich_effort_profile(
    effort,
    ftp,
):
    """
    Дополняет усилие независимыми
    характеристиками мощности
    и продолжительности.
    """
    average_power = effort.get(
        "average_power"
    )

    duration = effort.get(
        "duration_seconds"
    )

    detection_profile = effort.get(
        "primary_profile"
    )

    actual_power_category = (
        classify_effort_power(
            average_power=average_power,
            ftp=ftp,
        )
    )

    duration_category = (
        classify_effort_duration(
            duration
        )
    )

    ftp_percent = None

    if (
        is_valid_number(average_power)
        and average_power >= 0
        and is_valid_number(ftp)
        and ftp > 0
    ):
        ftp_percent = round(
            average_power / ftp * 100,
            2,
        )

    return {
        **deepcopy(effort),

        "detection_profile": (
            detection_profile
        ),

        "actual_power_category": (
            actual_power_category
        ),

        "duration_category": (
            duration_category
        ),

        "actual_ftp_percent": (
            ftp_percent
        ),

        "profile_mismatch": (
            detection_profile is not None
            and actual_power_category != "unknown"
            and detection_profile != actual_power_category
        ),
    }


def summarize_effort_categories(
    efforts,
):
    """
    Формирует сводку усилий по категориям
    фактической средней мощности.

    Категории могут пересекаться по времени.
    Их продолжительность нельзя суммировать.
    """
    categories = {
        category: []
        for category in POWER_CATEGORIES
    }

    categories["unknown"] = []

    for effort in efforts:
        category = effort[
            "actual_power_category"
        ]

        categories[category].append(
            effort
        )

    summary = {}

    for category, category_efforts in (
        categories.items()
    ):
        root_efforts = [
            effort
            for effort in category_efforts
            if effort.get(
                "parent_effort_id"
            ) is None
        ]

        nested_efforts = [
            effort
            for effort in category_efforts
            if effort.get(
                "parent_effort_id"
            ) is not None
        ]

        summary[category] = {
            "efforts_count": len(
                category_efforts
            ),

            "root_efforts_count": len(
                root_efforts
            ),

            "nested_efforts_count": len(
                nested_efforts
            ),

            "unique_covered_seconds": (
                calculate_unique_effort_seconds(
                    category_efforts
                )
            ),

            "longest_effort_seconds": max(
                (
                    effort["duration_seconds"]
                    for effort in category_efforts
                ),
                default=0,
            ),

            "effort_ids": [
                effort["effort_id"]
                for effort in category_efforts
            ],
        }

    return summary


def build_workout_effort_profile(
    resolution,
    ftp,
):
    """
    Формирует профиль фактической
    интенсивности обнаруженных усилий.

    Не изменяет исходное разрешение
    пересечений.
    """
    if not isinstance(resolution, dict):
        raise ValueError(
            "Результат разрешения пересечений "
            "должен быть словарём"
        )

    if (
        not is_valid_number(ftp)
        or ftp <= 0
    ):
        return {
            "status": "insufficient_data",

            "reason": "Некорректный FTP",

            "efforts": [],
            "root_efforts": [],

            "category_summary": {},
            "summary": {},
        }

    if resolution.get("status") != "ok":
        return {
            "status": "insufficient_data",

            "reason": resolution.get(
                "reason"
            ),

            "efforts": [],
            "root_efforts": [],

            "category_summary": {},
            "summary": {},
        }

    efforts = [
        enrich_effort_profile(
            effort=effort,
            ftp=ftp,
        )
        for effort in resolution["efforts"]
    ]

    root_efforts = [
        effort
        for effort in efforts
        if effort.get(
            "parent_effort_id"
        ) is None
    ]

    nested_efforts = [
        effort
        for effort in efforts
        if effort.get(
            "parent_effort_id"
        ) is not None
    ]

    mismatches = [
        effort
        for effort in efforts
        if effort["profile_mismatch"]
    ]

    category_summary = (
        summarize_effort_categories(
            efforts
        )
    )

    unique_work_seconds = (
        calculate_unique_effort_seconds(
            efforts
        )
    )

    return {
        "status": "ok",

        "ftp": ftp,

        "efforts": efforts,

        "root_efforts": root_efforts,

        "category_summary": (
            category_summary
        ),

        "summary": {
            "efforts_count": len(
                efforts
            ),

            "root_efforts_count": len(
                root_efforts
            ),

            "nested_efforts_count": len(
                nested_efforts
            ),

            "profile_mismatch_count": len(
                mismatches
            ),

            "unique_work_seconds": (
                unique_work_seconds
            ),

            "profile_mismatch_effort_ids": [
                effort["effort_id"]
                for effort in mismatches
            ],
        },

        "limitations": [
            (
                "Категория усилия определяется "
                "по его средней мощности"
            ),
            (
                "Категория мощности не определяет "
                "физиологическую цель усилия"
            ),
            (
                "Профиль обнаружения и фактическая "
                "интенсивность могут различаться"
            ),
            (
                "Продолжительность усилий разных "
                "категорий может пересекаться"
            ),
            (
                "Уникальное время категории не равно "
                "посекундному времени в зоне мощности"
            ),
            (
                "Корневое усилие не обязательно "
                "является отдельным рабочим интервалом"
            ),
        ],
    }


def analyze_workout_effort_profile(
    records,
    ftp,
):
    """
    Полный анализ фактического
    профиля обнаруженных усилий.
    """
    resolution = (
        analyze_resolved_workout_efforts(
            records=records,
            ftp=ftp,
        )
    )

    profile = build_workout_effort_profile(
        resolution=resolution,
        ftp=ftp,
    )

    return {
        **profile,

        "original_resolution": (
            resolution
        ),
    }