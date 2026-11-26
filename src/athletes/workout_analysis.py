from datetime import datetime, timezone

from src.athletes.data_loader import (
    get_registered_athlete_unified_training,
)

from src.athletes.credentials import (
    get_api_key as get_stored_api_key,
)

from src.integrations.intervals_api import (
    download_activity_fit,
)

from src.analytics.workout_comparison_loader import (
    analyze_workout_with_fit_loader,
    analyze_workout_with_structural_fit_loader,
    select_latest_cycling_workout,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)


def normalize_workout_for_comparison(activity):
    """
    Преобразует объединённую активность
    в формат модуля сравнения тренировок.

    Не изменяет исходную активность.
    """
    source_ids = activity.get("source_ids") or {}

    intervals_id = source_ids.get("intervals")
    garmin_id = source_ids.get("garmin")

    if intervals_id is not None:
        activity_id = f"intervals:{intervals_id}"

    elif garmin_id is not None:
        activity_id = f"garmin:{garmin_id}"

    else:
        return None

    return {
        **activity,

        "id": activity_id,

        "type": activity.get("activity_type"),

        "duration_seconds": activity.get(
            "duration"
        ),

        "source_ids": dict(source_ids),
    }


def prepare_comparison_activities(activities):
    """
    Подготавливает объединённую историю
    для сравнения тренировок.
    """
    if not isinstance(activities, list):
        raise ValueError(
            "Активности должны быть списком"
        )

    prepared = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        normalized = normalize_workout_for_comparison(
            activity
        )

        if normalized is not None:
            prepared.append(normalized)

    return prepared


def create_intervals_fit_downloader(api_key):
    """
    Создаёт загрузчик FIT-файлов Intervals.icu
    для конкретного спортсмена.
    """
    def downloader(workout):
        source_ids = workout.get(
            "source_ids"
        ) or {}

        intervals_id = source_ids.get(
            "intervals"
        )

        if not api_key:
            raise ValueError(
                "API-ключ Intervals.icu отсутствует"
            )

        if intervals_id is None:
            raise ValueError(
                "У тренировки нет ID Intervals.icu"
            )

        if not workout.get(
            "intervals_has_details"
        ):
            raise ValueError(
                "Детальные данные Intervals.icu "
                "недоступны"
            )

        return download_activity_fit(
            activity_id=intervals_id,
            api_key=api_key,
        )

    return downloader


def analyze_registered_athlete_workout(
    athlete_id,
    days=30,
    comparison_method="structural",
    fallback_ftp=None,
    include_physiology=True,
):
    """
    Анализирует последнюю велосипедную тренировку
    зарегистрированного спортсмена.

    По умолчанию выполняет структурное
    и физиологическое сравнение.

    include_physiology=False позволяет
    выполнить только структурное сравнение.

    Старый алгоритм доступен через
    comparison_method="legacy".
    """
    if (
        isinstance(days, bool)
        or not isinstance(days, int)
    ):
        raise ValueError(
            "Период должен быть целым числом"
        )

    if days <= 0:
        raise ValueError(
            "Период должен быть положительным"
        )

    if comparison_method not in {
        "structural",
        "legacy",
    }:
        raise ValueError(
            "Неизвестный метод сравнения тренировок"
        )

    if not isinstance(include_physiology, bool):
        raise ValueError(
            "include_physiology должен быть bool"
        )

    athlete_id = str(athlete_id)

    training = get_registered_athlete_unified_training(
        athlete_id=athlete_id,
        days=days,
    )

    activities = prepare_comparison_activities(
        training["activities"]
    )

    latest = select_latest_cycling_workout(
        activities
    )

    if latest is not None:
        latest_date = parse_activity_date(
            latest["start_date"]
        )

        now = datetime.now(timezone.utc)

        days_since_latest = max(
            0,
            (now - latest_date).days + 1,
        )

        required_days = (
            days + days_since_latest
        )

        if required_days > days:
            training = (
                get_registered_athlete_unified_training(
                    athlete_id=athlete_id,
                    days=required_days,
                )
            )

            activities = prepare_comparison_activities(
                training["activities"]
            )

    api_key = get_stored_api_key(
        athlete_id=athlete_id,
        provider="intervals",
    )

    fit_downloader = create_intervals_fit_downloader(
        api_key
    )

    if comparison_method == "legacy":
        result = analyze_workout_with_fit_loader(
            activities=activities,
            fit_downloader=fit_downloader,
            days=days,
        )

    else:
        result = (
            analyze_workout_with_structural_fit_loader(
                activities=activities,

                fit_downloader=fit_downloader,

                days=days,

                fallback_ftp=fallback_ftp,

                include_physiology=include_physiology,
            )
        )

    return {
        **result,

        "athlete_id": athlete_id,

        "comparison_method": comparison_method,

        "physiology_requested": (
            include_physiology
            and comparison_method == "structural"
        ),

        "history_statistics": training.get(
            "statistics", {}
        ),
    }

def analyze_registered_athlete_workout_unified(
    athlete_id,
    days=30,
    fallback_ftp=None,
    max_aerobic_workouts=5,
):
    """
    Полный анализ последней тренировки
    зарегистрированного спортсмена.
    """
    from datetime import datetime, timezone

    from src.athletes.data_loader import (
        get_registered_athlete_unified_training,
    )

    from src.athletes.credentials import (
        get_api_key as get_stored_api_key,
    )

    from src.analytics.workout_comparison import (
        parse_activity_date,
    )

    from src.analytics.workout_comparison_loader import (
        analyze_workout_with_unified_fit_loader,
    )

    if (
        not isinstance(days, int)
        or isinstance(days, bool)
        or days <= 0
    ):
        raise ValueError(
            "days должен быть положительным целым числом"
        )

    requested_history_days = days + 2

    training = (
        get_registered_athlete_unified_training(
            athlete_id=athlete_id,

            days=requested_history_days,
        )
    )

    activities = prepare_comparison_activities(
        training["activities"]
    )

    now = datetime.now(timezone.utc)

    cycling_dates = []

    for activity in activities:

        if activity.get("type") != "cycling":
            continue

        activity_date = parse_activity_date(
            activity.get("start_date")
        )

        if (
            activity_date is not None
            and activity_date < now
        ):
            cycling_dates.append(
                activity_date
            )

    if cycling_dates:

        latest_date = max(cycling_dates)

        days_since_latest = max(
            0,

            (now - latest_date).days + 1,
        )

        required_history_days = (
            days
            + days_since_latest
            + 2
        )

        if (
            required_history_days
            > requested_history_days
        ):
            requested_history_days = (
                required_history_days
            )

            training = (
                get_registered_athlete_unified_training(
                    athlete_id=athlete_id,

                    days=requested_history_days,
                )
            )

            activities = (
                prepare_comparison_activities(
                    training["activities"]
                )
            )

    api_key = get_stored_api_key(
        athlete_id=athlete_id,

        provider="intervals",
    )

    if not api_key:

        return {
            "status": "insufficient_data",

            "athlete_id": athlete_id,

            "reason": "missing_intervals_api_key",

            "analysis": None,

            "fitness_change": None,
        }

    downloader = create_intervals_fit_downloader(
        api_key
    )

    result = analyze_workout_with_unified_fit_loader(
        activities=activities,

        fit_downloader=downloader,

        days=days,

        fallback_ftp=fallback_ftp,

        max_aerobic_workouts=max_aerobic_workouts,
    )

    return {
        **result,

        "athlete_id": athlete_id,

        "comparison_method": "unified",

        "requested_history_days": (
            requested_history_days
        ),
    }