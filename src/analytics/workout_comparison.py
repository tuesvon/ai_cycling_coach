from datetime import datetime, timedelta, timezone
from statistics import mean
from src.analytics.power_hr_analysis import (compare_hr_at_same_power,)
from src.analytics.aerobic_drift import analyze_aerobic_drift_quality


def parse_activity_date(value):
    """
    Преобразует дату активности в UTC.
    """
    if isinstance(value, datetime):
        result = value

    elif isinstance(value, str):
        result = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    else:
        raise ValueError("Некорректная дата активности")

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def get_activity_duration(activity):
    """
    Возвращает длительность в минутах.

    Ожидается поле duration_seconds.
    """
    seconds = activity.get("duration_seconds")

    if isinstance(seconds, bool):
        return None

    if not isinstance(seconds, (int, float)):
        return None

    if seconds <= 0:
        return None

    return seconds / 60


def is_similar_workout(
    reference,
    candidate,
    max_duration_difference=0.25,
    max_power_difference=0.10,
):
    """
    Проверяет базовую сопоставимость двух тренировок.

    Допуски:
    - длительность: +/-25%;
    - средняя мощность: +/-10%.

    Это предварительный фильтр, а не доказательство
    одинаковой физиологической нагрузки.
    """
    if reference.get("type") != candidate.get("type"):
        return False

    if reference.get("type") != "cycling":
        return False

    reference_duration = get_activity_duration(reference)
    candidate_duration = get_activity_duration(candidate)

    if reference_duration is None:
        return False

    if candidate_duration is None:
        return False

    duration_difference = abs(
        candidate_duration - reference_duration
    ) / reference_duration

    if duration_difference > max_duration_difference:
        return False

    reference_power = reference.get("average_power")
    candidate_power = candidate.get("average_power")

    for power in (reference_power, candidate_power):
        if isinstance(power, bool):
            return False

        if not isinstance(power, (int, float)):
            return False

        if power <= 0:
            return False

    power_difference = abs(
        candidate_power - reference_power
    ) / reference_power

    return power_difference <= max_power_difference


def find_similar_workouts(
    latest_workout,
    activities,
    days=30,
):
    """
    Ищет похожие завершённые тренировки,
    выполненные ДО последней тренировки.

    Текущая тренировка исключается из сравнения.
    """
    if not isinstance(latest_workout, dict):
        raise ValueError("Последняя тренировка должна быть словарём")

    if not isinstance(activities, list):
        raise ValueError("Активности должны быть списком")

    if isinstance(days, bool) or not isinstance(days, int):
        raise ValueError("Период должен быть целым числом")

    if days <= 0:
        raise ValueError("Период должен быть положительным")

    latest_date = parse_activity_date(
        latest_workout["start_date"]
    )

    cutoff = latest_date - timedelta(days=days)

    similar = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        if activity.get("id") == latest_workout.get("id"):
            if latest_workout.get("id") is not None:
                continue

        try:
            activity_date = parse_activity_date(
                activity["start_date"]
            )
        except (KeyError, TypeError, ValueError):
            continue

        if not cutoff <= activity_date < latest_date:
            continue

        if not is_similar_workout(
            latest_workout,
            activity,
        ):
            continue

        similar.append(activity)

    similar.sort(
        key=lambda activity: parse_activity_date(
            activity["start_date"]
        ),
        reverse=True,
    )

    return similar


def compare_workout_heart_rate(
    latest_workout,
    similar_workouts,
):
    """
    Сравнивает средний пульс.

    ВАЖНО:
    Средний пульс всей тренировки не равен пульсу
    при одинаковой мощности.

    Поэтому результат обозначается как
    предварительное сравнение.
    """
    latest_hr = latest_workout.get("average_hr")

    if (
        isinstance(latest_hr, bool)
        or not isinstance(latest_hr, (int, float))
        or latest_hr <= 0
    ):
        return {
            "status": "insufficient_data",
            "reason": "Нет среднего пульса последней тренировки",
        }

    valid = []

    for workout in similar_workouts:
        hr = workout.get("average_hr")

        if (
            isinstance(hr, bool)
            or not isinstance(hr, (int, float))
            or hr <= 0
        ):
            continue

        valid.append(workout)

    if not valid:
        return {
            "status": "insufficient_data",
            "reason": "Нет сопоставимых тренировок с пульсом",
        }

    previous_average_hr = mean(
        workout["average_hr"]
        for workout in valid
    )

    difference = latest_hr - previous_average_hr

    return {
        "status": "ok",
        "comparison_type": "whole_workout_average",
        "latest_average_hr": round(latest_hr, 1),
        "previous_average_hr": round(
            previous_average_hr, 1
        ),
        "difference_bpm": round(difference, 1),
        "compared_workouts": len(valid),
        "quality": (
            "limited"
            if len(valid) < 3
            else "preliminary"
        ),
        "interpretation": (
            "Разница среднего пульса между тренировками "
            "с похожей длительностью и средней мощностью. "
            "Это не измерение пульса при строго одинаковых "
            "ваттах и не доказательство изменения формы."
        ),
    }


def analyze_latest_workout(
    latest_workout,
    activities,
    days=30,
):
    """
    Основная точка входа модуля.
    """
    similar = find_similar_workouts(
        latest_workout=latest_workout,
        activities=activities,
        days=days,
    )

    comparison = compare_workout_heart_rate(
        latest_workout,
        similar,
    )

    return {
        "latest_workout_id": latest_workout.get("id"),
        "comparison_period_days": days,
        "similar_workouts_found": len(similar),
        "similar_workout_ids": [
            workout.get("id")
            for workout in similar
        ],
        "heart_rate_comparison": comparison,
    }




def analyze_latest_workout_detailed(
    latest_workout,
    activities,
    activity_records,
    days=30,
    drift_activity_records=None,
):
    """
    Комплексный анализ последней тренировки.

    activity_records:
        Записи, пригодные для сравнения
        пульса при одинаковой мощности.

    drift_activity_records:
        Записи, пригодные для расчёта
        аэробного дрейфа.

    Если drift_activity_records не передан,
    используется activity_records для обратной
    совместимости.
    """
    if not isinstance(activity_records, dict):
        raise ValueError(
            "Детальные записи должны быть словарём"
        )

    if drift_activity_records is None:
        drift_activity_records = activity_records

    if not isinstance(drift_activity_records, dict):
        raise ValueError(
            "Записи для анализа дрейфа "
            "должны быть словарём"
        )

    basic_analysis = analyze_latest_workout(
        latest_workout=latest_workout,
        activities=activities,
        days=days,
    )

    latest_id = latest_workout.get("id")

    latest_records = activity_records.get(
        latest_id
    )

    latest_drift_records = drift_activity_records.get(
        latest_id
    )

    if isinstance(latest_drift_records, list):
        latest_drift = analyze_aerobic_drift_quality(
            latest_drift_records
        )

    else:
        latest_drift = {
            "status": "insufficient_data",
            "reason": (
                "Нет непрерывных записей последней "
                "тренировки, пригодных для анализа дрейфа"
            ),
        }

    similar_workouts = find_similar_workouts(
        latest_workout=latest_workout,
        activities=activities,
        days=days,
    )

    detailed_comparisons = []
    drift_comparisons = []
    skipped_power_hr = []
    skipped_drift = []

    for workout in similar_workouts:
        previous_id = workout.get("id")

        previous_records = activity_records.get(
            previous_id
        )

        previous_drift_records = (
            drift_activity_records.get(previous_id)
        )

        if (
            isinstance(latest_records, list)
            and isinstance(previous_records, list)
        ):
            power_hr = compare_hr_at_same_power(
                latest_records=latest_records,
                previous_records=previous_records,
            )

            if power_hr["status"] == "ok":
                detailed_comparisons.append({
                    "workout_id": previous_id,
                    "workout_date": workout.get(
                        "start_date"
                    ),
                    "comparison": power_hr,
                })

            else:
                skipped_power_hr.append({
                    "workout_id": previous_id,
                    "status": power_hr["status"],
                    "reason": power_hr.get(
                        "reason",
                        "Недостаточно сопоставимых данных",
                    ),
                })

        else:
            skipped_power_hr.append({
                "workout_id": previous_id,
                "status": "insufficient_data",
                "reason": (
                    "Нет пригодных записей "
                    "мощности и пульса"
                ),
            })

        if latest_drift["status"] != "ok":
            skipped_drift.append({
                "workout_id": previous_id,
                "status": latest_drift["status"],
                "reason": (
                    "Дрейф последней тренировки "
                    "не может быть корректно рассчитан"
                ),
            })

            continue

        if not isinstance(
            previous_drift_records, list
        ):
            skipped_drift.append({
                "workout_id": previous_id,
                "status": "insufficient_data",
                "reason": (
                    "Нет пригодных непрерывных записей"
                ),
            })

            continue

        previous_drift = analyze_aerobic_drift_quality(
            previous_drift_records
        )

        if previous_drift["status"] != "ok":
            skipped_drift.append({
                "workout_id": previous_id,
                "status": previous_drift["status"],
                "reason": previous_drift.get(
                    "reason",
                    "Тренировка не подходит для анализа дрейфа",
                ),
            })

            continue

        drift_comparisons.append({
            "workout_id": previous_id,
            "workout_date": workout.get(
                "start_date"
            ),
            "previous_drift_percent": previous_drift[
                "drift_percent"
            ],
            "latest_drift_percent": latest_drift[
                "drift_percent"
            ],
            "difference_percentage_points": round(
                latest_drift["drift_percent"]
                - previous_drift["drift_percent"],
                2,
            ),
        })

    if detailed_comparisons:
        power_hr_result = {
            "status": "ok",
            "compared_workouts": len(
                detailed_comparisons
            ),
            "comparisons": detailed_comparisons,
        }

    else:
        power_hr_result = {
            "status": "insufficient_data",
            "compared_workouts": 0,
            "comparisons": [],
            "reason": (
                "Нет подходящих тренировок "
                "с детальными записями мощности и пульса"
            ),
        }

    power_hr_result["skipped_workouts"] = (
        skipped_power_hr
    )

    power_hr_result["skipped_workouts_count"] = len(
        skipped_power_hr
    )

    aerobic_drift_result = {
        **latest_drift,
        "previous_comparisons": drift_comparisons,
        "compared_workouts": len(
            drift_comparisons
        ),
        "skipped_workouts": skipped_drift,
        "skipped_workouts_count": len(
            skipped_drift
        ),
    }

    return {
        **basic_analysis,
        "power_hr_comparison": power_hr_result,
        "aerobic_drift": aerobic_drift_result,
    }

def build_comparison_signatures(
    latest_workout,
    activities,
    activity_records,
    days=30,
    fallback_ftp=None,
):
    """
    Формирует профили последней тренировки
    и всех предыдущих велосипедных активностей
    за указанный период.

    Не использует старые ограничения
    средней мощности и длительности.
    """
    from src.analytics.workout_signature import (
        build_workout_signature,
    )

    if not isinstance(latest_workout, dict):
        raise ValueError(
            "Последняя тренировка должна быть словарём"
        )

    if not isinstance(activities, list):
        raise ValueError(
            "Активности должны быть списком"
        )

    if not isinstance(activity_records, dict):
        raise ValueError(
            "Записи тренировок должны быть словарём"
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

        selected.append(activity)
        selected_ids.add(activity_id)

    signatures = {}
    skipped_workouts = []

    for activity in selected:
        activity_id = activity["id"]

        records = activity_records.get(
            activity_id
        )

        if not isinstance(records, list) or not records:
            skipped_workouts.append({
                "activity_id": activity_id,
                "name": activity.get("name"),
                "reason": "missing_fit_records",
            })

            continue

        try:
            signature = build_workout_signature(
                activity=activity,
                records=records,
                fallback_ftp=fallback_ftp,
            )

        except Exception as error:
            skipped_workouts.append({
                "activity_id": activity_id,
                "name": activity.get("name"),
                "reason": "signature_analysis_error",
                "error_type": type(error).__name__,
            })

            continue

        signatures[activity_id] = signature

        if signature["status"] != "ok":
            skipped_workouts.append({
                "activity_id": activity_id,
                "name": activity.get("name"),
                "reason": "insufficient_data",
                "details": signature.get("reason"),
            })

    successful_count = sum(
        signature["status"] == "ok"
        for signature in signatures.values()
    )

    return {
        "latest_signature": signatures.get(
            latest_id
        ),

        "signatures": signatures,

        "skipped_workouts": skipped_workouts,

        "statistics": {
            "selected_workouts": len(selected),

            "created_signatures": len(
                signatures
            ),

            "successful_signatures": (
                successful_count
            ),

            "skipped_workouts": len(
                skipped_workouts
            ),
        },
    }

def analyze_latest_workout_structural(
    latest_workout,
    activities,
    activity_records,
    days=30,
    fallback_ftp=None,
    include_physiology=False,
):
    """
    Анализирует структуру последней тренировки
    и ищет похожие тренировки.

    При include_physiology=True дополнительно
    сравнивает сопоставленные рабочие усилия
    и восстановление после них.
    """
    from src.analytics.workout_similarity import (
        find_similar_workout_signatures,
        get_comparison_family,
    )

    prepared = build_comparison_signatures(
        latest_workout=latest_workout,
        activities=activities,
        activity_records=activity_records,
        days=days,
        fallback_ftp=fallback_ftp,
    )

    latest_signature = prepared[
        "latest_signature"
    ]

    result = {
        "status": "ok",

        "comparison_method": "structural_similarity",

        "latest_workout_id": latest_workout.get(
            "id"
        ),

        "comparison_period_days": days,

        "latest_signature": latest_signature,

        "signature_statistics": prepared[
            "statistics"
        ],

        "skipped_workouts": prepared[
            "skipped_workouts"
        ],

        "similar_workouts_found": 0,

        "similar_workout_ids": [],

        "similar_workouts": [],

        "physiological_comparison": {
            "status": (
                "insufficient_data"
                if include_physiology
                else "not_implemented"
            ),

            "fitness_change": None,

            "reason": (
                "Физиологическое сравнение "
                "пока не выполнено"
                if include_physiology
                else "Запрошен только структурный анализ"
            ),
        },
    }

    if latest_signature is None:
        return {
            **result,

            "status": "insufficient_data",

            "reason": (
                "Не удалось сформировать профиль "
                "последней тренировки"
            ),
        }

    if latest_signature["status"] != "ok":
        return {
            **result,

            "status": "insufficient_data",

            "reason": latest_signature.get(
                "reason"
            ),
        }

    candidates = [
        signature

        for activity_id, signature
        in prepared["signatures"].items()

        if (
            activity_id
            != latest_signature["activity_id"]

            and signature["status"] == "ok"
        )
    ]

    similarity = find_similar_workout_signatures(
        reference=latest_signature,
        candidates=candidates,
        days=days,
    )

    similar_workouts = similarity[
        "similar_workouts"
    ]

    physiological_comparison = result[
        "physiological_comparison"
    ]

    if include_physiology:
        physiological_comparison = (
            analyze_similar_workouts_physiology(
                reference_signature=latest_signature,

                signatures=prepared["signatures"],

                similar_workouts=similar_workouts,

                activity_records=activity_records,
            )
        )

    return {
        **result,

        "status": similarity["status"],

        "latest_comparison_family": (
            get_comparison_family(
                latest_signature
            )
        ),

        "similar_workouts_found": len(
            similar_workouts
        ),

        "similar_workout_ids": [
            workout["candidate_activity_id"]

            for workout in similar_workouts
        ],

        "similar_workouts": similar_workouts,

        "similarity_search": similarity,

        "physiological_comparison": (
            physiological_comparison
        ),

        "limitations": [
            (
                "Структурное сходство не доказывает "
                "одинаковую физиологическую нагрузку"
            ),
            (
                "Изменение физической формы "
                "автоматически не оценивается"
            ),
            (
                "Качество сравнения зависит "
                "от полноты FIT-данных"
            ),
            (
                "Сложные вложенные блоки "
                "могут быть сопоставлены частично"
            ),
            (
                "Сравнение аэробных участков "
                "пока не реализовано"
            ),
        ],
    }

def analyze_similar_workouts_physiology(
    reference_signature,
    signatures,
    similar_workouts,
    activity_records,
):
    """
    Выполняет физиологическое сравнение
    последней тренировки со всеми
    найденными аналогами.

    Использует уже сформированные профили
    и загруженные FIT-записи.

    Не объединяет результаты разных
    тренировок в единую оценку физической формы.
    """
    from src.analytics.workout_pair_analysis import (
        analyze_workout_pair,
    )

    reference_id = reference_signature.get(
        "activity_id"
    )

    reference_records = activity_records.get(
        reference_id
    )

    comparisons = []
    skipped_workouts = []

    result = {
        "status": "insufficient_data",
        "comparison_method": "matched_efforts",
        "reference_activity_id": reference_id,
        "selected_workouts_count": len(similar_workouts),
        "compared_workouts_count": 0,
        "skipped_workouts_count": 0,
        "comparisons": comparisons,
        "skipped_workouts": skipped_workouts,
        "fitness_change": None,
    }

    if (
        not isinstance(reference_records, list)
        or not reference_records
    ):
        return {
            **result,
            "reason": "Нет FIT-записей последней тренировки",
        }

    if not similar_workouts:
        return {
            **result,
            "status": "no_similar_workouts",
        }

    processed_ids = set()

    for similarity in similar_workouts:
        candidate_id = similarity.get(
            "candidate_activity_id"
        )

        candidate_info = {
            "activity_id": candidate_id,
            "activity_name": similarity.get(
                "candidate_activity_name"
            ),
            "start_date": similarity.get(
                "candidate_start_date"
            ),
            "similarity_score": similarity.get("score"),
            "comparison_scope": similarity.get(
                "comparison_scope"
            ),
        }

        if (
            candidate_id is None
            or candidate_id == reference_id
            or candidate_id in processed_ids
        ):
            skipped_workouts.append({
                **candidate_info,
                "reason": "invalid_or_duplicate_candidate",
            })

            continue

        processed_ids.add(candidate_id)

        scope = similarity.get(
            "comparison_scope"
        )

        if scope == "aerobic_segment_candidates":
            skipped_workouts.append({
                **candidate_info,
                "reason": "aerobic_comparison_not_implemented",
            })

            continue

        if scope != "matched_efforts_only":
            skipped_workouts.append({
                **candidate_info,
                "reason": "unsupported_comparison_scope",
            })

            continue

        candidate_signature = signatures.get(
            candidate_id
        )

        candidate_records = activity_records.get(
            candidate_id
        )

        if (
            not isinstance(candidate_signature, dict)
            or candidate_signature.get("status") != "ok"
        ):
            skipped_workouts.append({
                **candidate_info,
                "reason": "missing_candidate_signature",
            })

            continue

        if (
            not isinstance(candidate_records, list)
            or not candidate_records
        ):
            skipped_workouts.append({
                **candidate_info,
                "reason": "missing_candidate_records",
            })

            continue

        try:
            comparison = analyze_workout_pair(
                reference_signature=reference_signature,
                candidate_signature=candidate_signature,
                similarity=similarity,
                reference_records=reference_records,
                candidate_records=candidate_records,
            )

        except Exception as error:
            skipped_workouts.append({
                **candidate_info,
                "reason": "physiological_analysis_error",
                "error_type": type(error).__name__,
            })

            continue

        if (
            comparison.get("status") not in {
                "ok",
                "partial",
            }
            or comparison.get(
                "analyzed_pairs_count", 0
            ) == 0
        ):
            skipped_workouts.append({
                **candidate_info,
                "reason": "physiological_comparison_unavailable",
                "analysis_status": comparison.get("status"),
            })

            continue

        comparisons.append({
            **candidate_info,
            "analysis": comparison,
        })

    total_analyzed_pairs = sum(
        comparison["analysis"].get(
            "analyzed_pairs_count", 0
        )
        for comparison in comparisons
    )

    total_matched_pairs = sum(
        comparison["analysis"].get(
            "matched_pairs_count", 0
        )
        for comparison in comparisons
    )

    heart_rate_comparable_pairs = sum(
        comparison["analysis"]
        .get("summary", {})
        .get("heart_rate_comparable_pairs", 0)

        for comparison in comparisons
    )

    recovery_comparable_checkpoints = sum(
        pair.get("recovery_comparison", {}).get(
            "comparable_checkpoints", 0
        )

        for comparison in comparisons

        for pair in comparison["analysis"].get(
            "pairs", []
        )
    )

    if not comparisons:
        if skipped_workouts and all(
            item["reason"]
            == "aerobic_comparison_not_implemented"

            for item in skipped_workouts
        ):
            status = "not_implemented"

        else:
            status = "insufficient_data"

    elif (
        skipped_workouts
        or any(
            item["analysis"]["status"] != "ok"

            for item in comparisons
        )
    ):
        status = "partial"

    else:
        status = "ok"

    return {
        **result,
        "status": status,
        "compared_workouts_count": len(comparisons),
        "skipped_workouts_count": len(skipped_workouts),
        "total_matched_pairs": total_matched_pairs,
        "total_analyzed_pairs": total_analyzed_pairs,
        "heart_rate_comparable_pairs": (
            heart_rate_comparable_pairs
        ),
        "recovery_comparable_checkpoints": (
            recovery_comparable_checkpoints
        ),
        "limitations": [
            (
                "Физиологические результаты "
                "рассчитываются отдельно для каждого аналога"
            ),
            (
                "Одно усилие последней тренировки "
                "может сравниваться с несколькими тренировками"
            ),
            (
                "Количество пар не является количеством "
                "независимых физиологических наблюдений"
            ),
            (
                "Сравнение аэробных участков "
                "ещё не реализовано"
            ),
            (
                "Автоматическая оценка изменения "
                "физической формы не выполняется"
            ),
        ],
    }