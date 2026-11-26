from io import BytesIO

from fitparse import FitFile

from src.analytics.workout_comparison import (
    parse_activity_date,
    find_similar_workouts,
)

from src.analytics.fit_workout_comparison import (
    analyze_fit_workout_comparison,
)


def select_latest_cycling_workout(activities):
    """
    Выбирает последнюю велосипедную тренировку
    из нормализованного списка активностей.

    Будущие активности исключаются.
    """
    from datetime import datetime, timezone

    if not isinstance(activities, list):
        raise ValueError(
            "Активности должны быть списком"
        )

    now = datetime.now(timezone.utc)

    cycling_activities = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        if activity.get("type") != "cycling":
            continue

        if activity.get("id") is None:
            continue

        try:
            activity_date = parse_activity_date(
                activity["start_date"]
            )

        except (KeyError, TypeError, ValueError):
            continue

        if activity_date > now:
            continue

        cycling_activities.append(
            (activity_date, activity)
        )

    if not cycling_activities:
        return None

    return max(
        cycling_activities,
        key=lambda item: item[0],
    )[1]

def read_fit_bytes(content):
    """
    Читает FIT-файл из памяти.

    Не создаёт временные файлы на диске.
    """
    if not isinstance(content, bytes):
        raise ValueError(
            "Содержимое FIT должно быть в формате bytes"
        )

    if not content:
        raise ValueError("FIT-файл пуст")

    fit_file = FitFile(BytesIO(content))

    records = []

    for message in fit_file.get_messages("record"):
        record = {
            field.name: field.value
            for field in message
            if field.value is not None
        }

        if "timestamp" in record:
            records.append(record)

    if not records:
        raise ValueError(
            "FIT-файл не содержит записей"
        )

    return records


def load_comparison_records(
    latest_workout,
    activities,
    fit_downloader,
    days=30,
):
    """
    Загружает FIT-записи последней тренировки
    и похожих тренировок за указанный период.

    fit_downloader — функция, принимающая словарь
    активности и возвращающая FIT в формате bytes.
    """
    if not callable(fit_downloader):
        raise ValueError(
            "fit_downloader должен быть функцией"
        )

    similar_workouts = find_similar_workouts(
        latest_workout=latest_workout,
        activities=activities,
        days=days,
    )

    selected_workouts = [
        latest_workout,
        *similar_workouts,
    ]

    activity_records = {}
    download_errors = []
    attempted_ids = set()

    for workout in selected_workouts:
        activity_id = workout.get("id")

        if activity_id is None:
            continue

        if activity_id in attempted_ids:
            continue

        attempted_ids.add(activity_id)

        try:
            content = fit_downloader(workout)

            records = read_fit_bytes(content)

            activity_records[activity_id] = records

        except Exception as error:
            download_errors.append({
                "activity_id": activity_id,
                "activity_date": workout.get(
                    "start_date"
                ),
                "error_type": type(error).__name__,
            })

    return {
        "activity_records": activity_records,
        "download_errors": download_errors,
        "statistics": {
            "selected_workouts": len(attempted_ids),
            "loaded_workouts": len(activity_records),
            "failed_workouts": len(download_errors),
        },
    }



def analyze_workout_with_fit_loader(
    activities,
    fit_downloader,
    days=30,
):
    """
    Выбирает последнюю тренировку,
    загружает FIT-файлы и выполняет анализ.

    Общий статус учитывает полноту
    сравнения мощности и пульса.
    """
    latest_workout = select_latest_cycling_workout(
        activities
    )

    if latest_workout is None:
        return {
            "status": "insufficient_data",
            "reason": (
                "Не найдены велосипедные тренировки"
            ),
        }

    loaded = load_comparison_records(
        latest_workout=latest_workout,
        activities=activities,
        fit_downloader=fit_downloader,
        days=days,
    )

    analysis = analyze_fit_workout_comparison(
        latest_workout=latest_workout,
        activities=activities,
        activity_records=loaded["activity_records"],
        days=days,
    )

    latest_id = latest_workout["id"]

    latest_quality = (
        analysis.get("fit_data_quality", {})
        .get("latest_workout")
        or {}
    )

    power_hr = analysis.get(
        "power_hr_comparison", {}
    )

    aerobic_drift = analysis.get(
        "aerobic_drift", {}
    )

    similar_count = analysis.get(
        "similar_workouts_found", 0
    )

    compared_count = power_hr.get(
        "compared_workouts", 0
    )

    if latest_id not in loaded["activity_records"]:
        status = "insufficient_data"

    elif not latest_quality.get(
        "suitable_for_power_hr_analysis"
    ):
        status = "insufficient_data"

    elif power_hr.get("status") != "ok":
        status = "partial"

    elif loaded["download_errors"]:
        status = "partial"

    elif compared_count < similar_count:
        status = "partial"

    else:
        status = "ok"

    return {
        "status": status,

        "latest_workout": {
            "id": latest_id,
            "name": latest_workout.get("name"),
            "start_date": latest_workout.get(
                "start_date"
            ),
        },

        "download_statistics": loaded[
            "statistics"
        ],

        "download_errors": loaded[
            "download_errors"
        ],

        "analysis_completeness": {
            "similar_workouts_found": similar_count,

            "power_hr_compared_workouts": (
                compared_count
            ),

            "power_hr_skipped_workouts": max(
                0,
                similar_count - compared_count,
            ),

            "power_hr_status": power_hr.get(
                "status"
            ),

            "aerobic_drift_status": aerobic_drift.get(
                "status"
            ),

            "aerobic_drift_compared_workouts": (
                aerobic_drift.get(
                    "compared_workouts", 0
                )
            ),
        },

        "analysis": analysis,
    }

def load_structural_comparison_records(
    latest_workout,
    activities,
    fit_downloader,
    days=30,
):
    """
    Загружает FIT последней тренировки
    и предыдущих велосипедных активностей.

    Не фильтрует кандидатов по средней
    мощности и общей продолжительности.
    """
    from datetime import timedelta

    if not callable(fit_downloader):
        raise ValueError(
            "fit_downloader должен быть функцией"
        )

    if not isinstance(activities, list):
        raise ValueError(
            "Активности должны быть списком"
        )

    if (
        isinstance(days, bool)
        or not isinstance(days, int)
        or days <= 0
    ):
        raise ValueError(
            "Период должен быть положительным "
            "целым числом"
        )

    latest_id = latest_workout.get("id")

    if latest_id is None:
        raise ValueError(
            "Нет ID последней тренировки"
        )

    latest_date = parse_activity_date(
        latest_workout["start_date"]
    )

    cutoff_date = latest_date - timedelta(
        days=days
    )

    selected = [latest_workout]

    selected_ids = {latest_id}

    previous_workouts = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        if activity.get("type") != "cycling":
            continue

        activity_id = activity.get("id")

        if activity_id is None:
            continue

        if activity_id in selected_ids:
            continue

        try:
            activity_date = parse_activity_date(
                activity["start_date"]
            )

        except (KeyError, TypeError, ValueError):
            continue

        if not (
            cutoff_date
            <= activity_date
            < latest_date
        ):
            continue

        previous_workouts.append(
            (activity_date, activity)
        )

        selected_ids.add(activity_id)

    previous_workouts.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected.extend(
        activity
        for _, activity in previous_workouts
    )

    activity_records = {}
    download_errors = []
    attempted_ids = set()

    for activity in selected:
        activity_id = activity["id"]

        attempted_ids.add(activity_id)

        try:
            content = fit_downloader(activity)

            records = read_fit_bytes(content)

            activity_records[activity_id] = (
                records
            )

        except Exception as error:
            download_errors.append({
                "activity_id": activity_id,

                "activity_name": activity.get(
                    "name"
                ),

                "activity_date": activity.get(
                    "start_date"
                ),

                "error_type": type(error).__name__,
            })

    return {
        "activity_records": activity_records,

        "download_errors": download_errors,

        "selected_activities": selected,

        "statistics": {
            "selected_workouts": len(selected),

            "attempted_workouts": len(
                attempted_ids
            ),

            "loaded_workouts": len(
                activity_records
            ),

            "failed_workouts": len(
                download_errors
            ),
        },
    }

def analyze_workout_with_structural_fit_loader(
    activities,
    fit_downloader,
    days=30,
    fallback_ftp=None,
    include_physiology=False,
):
    """
    Выполняет структурный анализ
    последней велосипедной тренировки.

    При include_physiology=True выполняет
    физиологическое сравнение найденных
    сопоставимых рабочих усилий.
    """
    from src.analytics.workout_comparison import (
        analyze_latest_workout_structural,
    )

    latest_workout = select_latest_cycling_workout(
        activities
    )

    if latest_workout is None:
        return {
            "status": "insufficient_data",
            "reason": (
                "Не найдены велосипедные тренировки"
            ),
        }

    loaded = load_structural_comparison_records(
        latest_workout=latest_workout,
        activities=activities,
        fit_downloader=fit_downloader,
        days=days,
    )

    analysis = analyze_latest_workout_structural(
        latest_workout=latest_workout,

        activities=loaded[
            "selected_activities"
        ],

        activity_records=loaded[
            "activity_records"
        ],

        days=days,

        fallback_ftp=fallback_ftp,

        include_physiology=include_physiology,
    )

    latest_id = latest_workout["id"]

    structural_status = analysis["status"]

    signature_statistics = analysis.get(
        "signature_statistics",
        {},
    )

    physiology = analysis.get(
        "physiological_comparison",
        {},
    )

    physiology_status = physiology.get(
        "status",
        "not_implemented",
    )

    search_coverage_complete = (
        not loaded["download_errors"]

        and signature_statistics.get(
            "skipped_workouts", 0
        ) == 0
    )

    if structural_status == "insufficient_data":
        status = "insufficient_data"

    else:
        # Аэробное сравнение и ряд проверок
        # качества пока не реализованы.
        status = "partial"

    return {
        "status": status,

        "structural_analysis_status": (
            structural_status
        ),

        "physiological_analysis_status": (
            physiology_status
        ),

        "latest_workout": {
            "id": latest_id,

            "name": latest_workout.get("name"),

            "start_date": latest_workout.get(
                "start_date"
            ),
        },

        "download_statistics": loaded[
            "statistics"
        ],

        "download_errors": loaded[
            "download_errors"
        ],

        "analysis_completeness": {
            "structural_analysis_status": (
                structural_status
            ),

            "physiological_analysis_status": (
                physiology_status
            ),

            "search_coverage_complete": (
                search_coverage_complete
            ),

            "similar_workouts_found": analysis.get(
                "similar_workouts_found", 0
            ),

            "successful_signatures": (
                signature_statistics.get(
                    "successful_signatures", 0
                )
            ),

            "skipped_workouts": (
                signature_statistics.get(
                    "skipped_workouts", 0
                )
            ),

            "physiologically_analyzed_workouts": (
                physiology.get(
                    "compared_workouts_count", 0
                )
            ),

            "physiologically_skipped_workouts": (
                physiology.get(
                    "skipped_workouts_count", 0
                )
            ),

            "matched_efforts_count": (
                physiology.get(
                    "total_matched_pairs", 0
                )
            ),

            "analyzed_efforts_count": (
                physiology.get(
                    "total_analyzed_pairs", 0
                )
            ),

            "heart_rate_comparable_pairs": (
                physiology.get(
                    "heart_rate_comparable_pairs", 0
                )
            ),

            "recovery_comparable_checkpoints": (
                physiology.get(
                    "recovery_comparable_checkpoints", 0
                )
            ),

            "power_hr_compared_workouts": 0,

            "power_hr_status": "not_implemented",

            "aerobic_drift_status": "not_implemented",

            "aerobic_drift_compared_workouts": 0,
        },

        "analysis": analysis,
    }

def analyze_workout_with_unified_fit_loader(
    activities,
    fit_downloader,
    days=30,
    fallback_ftp=None,
    max_aerobic_workouts=5,
):
    """
    Загружает FIT-файлы один раз
    и передаёт записи объединённой аналитике.
    """
    from datetime import datetime, timedelta, timezone
    from time import perf_counter

    from src.analytics.workout_comparison import (
        parse_activity_date,
        analyze_latest_workout_unified,
    )

    if (
        not isinstance(days, int)
        or isinstance(days, bool)
        or days <= 0
    ):
        raise ValueError(
            "days должен быть положительным целым числом"
        )

    result = {
        "status": "insufficient_data",

        "latest_workout": None,

        "download_statistics": {
            "requested_workouts": 0,

            "successful_downloads": 0,

            "failed_downloads": 0,

            "total_download_seconds": 0,

            "analysis_seconds": 0,
        },

        "download_errors": [],

        "analysis_completeness": {},

        "analysis": None,

        "fitness_change": None,
    }

    now = datetime.now(timezone.utc)

    completed = []
    seen_ids = set()

    for activity in activities:

        if not isinstance(activity, dict):
            continue

        if activity.get("type") != "cycling":
            continue

        activity_id = activity.get("id")

        activity_date = parse_activity_date(
            activity.get("start_date")
        )

        duration = activity.get(
            "duration_seconds"
        )

        if not activity_id:
            continue

        if activity_id in seen_ids:
            continue

        if activity_date is None:
            continue

        if activity_date >= now:
            continue

        if (
            isinstance(duration, (int, float))

            and not isinstance(duration, bool)

            and duration > 0
        ):
            end_date = activity_date + timedelta(
                seconds=duration
            )

            if end_date > now:
                continue

        seen_ids.add(activity_id)

        completed.append(activity)

    if not completed:

        return {
            **result,

            "reason": "no_completed_cycling_workouts",
        }

    completed.sort(
        key=lambda activity: (
            parse_activity_date(
                activity["start_date"]
            ),
            activity["id"],
        ),

        reverse=True,
    )

    latest = completed[0]

    latest_id = latest["id"]

    latest_date = parse_activity_date(
        latest["start_date"]
    )

    cutoff = latest_date - timedelta(
        days=days
    )

    selected = [
        latest,

        *[
            activity

            for activity in completed[1:]

            if (
                cutoff

                <= parse_activity_date(
                    activity["start_date"]
                )

                < latest_date
            )
        ],
    ]

    result["latest_workout"] = {
        "id": latest_id,

        "name": latest.get("name"),

        "start_date": latest.get("start_date"),
    }

    records_by_activity = {}

    errors = []

    download_start = perf_counter()

    for activity in selected:

        activity_id = activity["id"]

        try:

            content = fit_downloader(activity)

            records = read_fit_bytes(content)

            if not records:
                raise ValueError(
                    "FIT does not contain records"
                )

        except Exception as error:

            errors.append({
                "activity_id": activity_id,

                "activity_name": activity.get(
                    "name"
                ),

                "error_type": type(error).__name__,
            })

            # Нет последней тренировки —
            # историческое сравнение невозможно.

            if activity_id == latest_id:
                break

            continue

        records_by_activity[
            activity_id
        ] = records

    download_seconds = round(
        perf_counter() - download_start,
        3,
    )

    statistics = {
        "requested_workouts": len(selected),

        "attempted_downloads": (
            len(records_by_activity)
            + len(errors)
        ),

        "successful_downloads": len(
            records_by_activity
        ),

        "failed_downloads": len(errors),

        "total_download_seconds": (
            download_seconds
        ),

        "analysis_seconds": 0,
    }

    result["download_statistics"] = statistics

    result["download_errors"] = errors

    if latest_id not in records_by_activity:

        return {
            **result,

            "status": "error",

            "reason": "latest_fit_unavailable",
        }

    analysis_start = perf_counter()

    analysis = analyze_latest_workout_unified(
        latest_workout=latest,

        activities=selected,

        activity_records=records_by_activity,

        days=days,

        fallback_ftp=fallback_ftp,

        max_aerobic_workouts=max_aerobic_workouts,
    )

    statistics["analysis_seconds"] = round(
        perf_counter() - analysis_start,
        3,
    )

    status = analysis["status"]

    if errors and status == "ok":
        status = "partial"

    return {
        **result,

        "status": status,

        "download_statistics": statistics,

        "download_errors": errors,

        "analysis_completeness": analysis.get(
            "analysis_completeness"
        ) or {},

        "analysis": analysis,
    }