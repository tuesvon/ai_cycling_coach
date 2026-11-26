from src.analytics.workout_classification import (
    is_valid_number,
)


MAX_HISTORICAL_WORKOUTS = 5

LOW_SIMILARITY_THRESHOLD = 65


STATUS_EXPLANATIONS = {
    "ok": "Анализ выполнен",

    "partial": (
        "Анализ выполнен с ограничениями"
    ),

    "insufficient_data": (
        "Недостаточно пригодных данных"
    ),

    "no_aerobic_segments": (
        "Не обнаружено подходящих "
        "стабильных аэробных сегментов"
    ),

    "no_comparable_workouts": (
        "Не найдено сопоставимых "
        "исторических тренировок"
    ),

    "no_work_blocks": (
        "Нет целевых интенсивных блоков "
        "для интервального анализа"
    ),

    "power_ignored": (
        "Мощность исключена из анализа"
    ),

    "not_comparable": (
        "Данные не удовлетворяют "
        "критериям сопоставимости"
    ),

    "not_applicable": (
        "Метод неприменим к данной нагрузке"
    ),

    "unavailable": (
        "Анализ недоступен"
    ),

    "error": (
        "Ошибка получения или обработки данных"
    ),
}


def select_fields(data, fields):
    """
    Извлекает только необходимые поля.
    Не заменяет отсутствующие значения нулями.
    """
    if not isinstance(data, dict):
        return {}

    return {
        field: data[field]

        for field in fields

        if field in data
    }


def compact_status(
    status,
    explanation=None,
):
    """
    Преобразует технический статус
    в понятное описание.
    """
    if status == "not_implemented":
        status = "not_applicable"

    if status is None:
        status = "unavailable"

    return {
        "status": status,

        "explanation": (
            explanation

            or STATUS_EXPLANATIONS.get(
                status,
                "Смотри ограничения анализа",
            )
        ),
    }


def compact_aerobic_segment(segment):
    metrics = segment.get("metrics") or {}

    efficiency = segment.get(
        "efficiency"
    ) or {}

    drift = segment.get("drift") or {}

    accumulated = segment.get(
        "accumulated_load"
    ) or {}

    previous_load = segment.get(
        "previous_load"
    ) or {}

    duration = segment.get(
        "duration_seconds"
    )

    return {
        "segment_id": segment.get(
            "segment_id"
        ),

        "status": compact_status(
            segment.get("status")
        ),

        "duration_minutes": (
            round(duration / 60, 2)

            if is_valid_number(duration)

            else None
        ),

        "target_power": segment.get(
            "target_power"
        ),

        "metrics": select_fields(
            metrics,

            (
                "average_power",
                "average_heart_rate",
                "max_heart_rate",
                "average_cadence",
                "work_kj",
                "heart_rate_coverage_ratio",
                "cadence_coverage_ratio",
            ),
        ),

        "efficiency": select_fields(
            efficiency,

            (
                "status",
                "method",
                "efficiency_factor",
                "average_paired_power",
                "average_paired_heart_rate",
                "paired_coverage_ratio",
            ),
        ),

        "drift": select_fields(
            drift,

            (
                "status",
                "method",
                "drift_percent",
                "heart_rate_difference_bpm",
                "half_power_difference_percent",
                "reasons",
            ),
        ),

        "accumulated_load": select_fields(
            accumulated,

            (
                "status",
                "elapsed_seconds_before_segment",
                "total_work_kj",
                "observed_work_kj",
                "power_coverage_ratio",
                "observed_high_intensity_seconds",
                "seconds_since_last_observed_high_intensity",
            ),
        ),

        "previous_load": select_fields(
            previous_load,

            (
                "average_power",
                "average_heart_rate",
                "work_kj",
                "power_coverage_ratio",
                "complete_power",
            ),
        ),

        "quality": segment.get(
            "quality"
        ),
    }


def compact_aerobic_analysis(analysis):
    return {
        **compact_status(
            analysis.get("status")
        ),

        "summary": analysis.get(
            "summary", {}
        ),

        "segments": [
            compact_aerobic_segment(
                segment
            )

            for segment in analysis.get(
                "segments", []
            )
        ],
    }


def compact_aerobic_comparison(comparison):
    quality = comparison.get(
        "comparison_quality"
    ) or {}

    reference = comparison.get(
        "reference"
    ) or {}

    candidate = comparison.get(
        "candidate"
    ) or {}

    profile_fields = (
        "segment_id",
        "duration_seconds",
        "average_power",
        "paired_heart_rate",
        "efficiency_factor",
        "drift_percent",
        "accumulated_work_kj",
        "previous_work_kj",
        "elapsed_seconds",
    )

    return {
        "status": comparison.get(
            "status"
        ),

        "reference": select_fields(
            reference,
            profile_fields,
        ),

        "candidate": select_fields(
            candidate,
            profile_fields,
        ),

        "differences": comparison.get(
            "differences", {}
        ),

        "quality": select_fields(
            quality,

            (
                "quality",
                "heart_rate_comparable",
                "blockers",
                "limitations",
                "power_difference_percent",
                "duration_difference_percent",
                "previous_work_difference_percent",
                "accumulated_work_difference_percent",
                "cadence_difference_rpm",
            ),
        ),

        "drift_comparable": comparison.get(
            "drift_comparable",
            False,
        ),
    }


def compact_historical_aerobic_workout(
    comparison,
    summary,
):
    similarity = (
        comparison.get("summary") or {}
    ).get("average_similarity_score")

    limitations = set()

    pairs = []

    for pair in comparison.get(
        "pairs", []
    ):
        details = compact_aerobic_comparison(
            pair["comparison"]
        )

        limitations.update(
            details["quality"].get(
                "limitations", []
            )
        )

        pairs.append({
            "similarity_score": (
                pair.get("similarity") or {}
            ).get("score"),

            **details,
        })

    weak_similarity = (
        similarity is None

        or similarity
        < LOW_SIMILARITY_THRESHOLD
    )

    return {
        "activity_id": comparison.get(
            "candidate_activity_id"
        ),

        "activity_name": comparison.get(
            "candidate_activity_name"
        ),

        "start_date": comparison.get(
            "candidate_start_date"
        ),

        "summary": summary,

        "similarity_score": similarity,

        "weak_similarity": weak_similarity,

        "interpretation_priority": (
            "supporting_context_only"

            if weak_similarity

            else "primary_comparison"
        ),

        "limitations": sorted(
            limitations
        ),

        "pairs": pairs,
    }


def compact_aerobic_history(history):
    summaries_by_id = {
        summary["activity_id"]: summary

        for summary in history.get(
            "historical_workout_summaries",
            [],
        )
    }

    historical_workouts = []

    for comparison in history.get(
        "historical_comparisons", []
    )[:MAX_HISTORICAL_WORKOUTS]:

        activity_id = comparison[
            "candidate_activity_id"
        ]

        summary = summaries_by_id.get(
            activity_id,
            {},
        )

        historical_workouts.append(
            compact_historical_aerobic_workout(
                comparison,
                summary,
            )
        )

    progression = history.get(
        "within_workout_progression"
    ) or {}

    return {
        **compact_status(
            history.get("status")
        ),

        "summary": history.get(
            "summary", {}
        ),

        "historical_workouts": (
            historical_workouts
        ),

        "within_workout_progression": {
            "status": progression.get(
                "status"
            ),

            "summary": progression.get(
                "summary", {}
            ),

            "comparisons": [
                compact_aerobic_comparison(
                    comparison
                )

                for comparison in progression.get(
                    "comparisons", []
                )
            ],
        },
    }


def compact_target_analysis(target):
    status = target.get("status")

    return {
        **compact_status(status),

        "summary": target.get(
            "summary", {}
        ),

        "target_efforts": target.get(
            "target_efforts", []
        ),

        "interpretation_notes": [
            (
                "Отсутствие автоматически "
                "распознанного соответствия "
                "не означает пропуск интервала"
            ),

            (
                "Выполнение задания оценивается "
                "по фактическим данным внутри "
                "целевого временного окна"
            ),
        ],
    }


def compact_interval_analysis(interval):
    status = interval.get("status")

    if status == "not_implemented":

        status_info = compact_status(
            "not_applicable",

            explanation=(
                "Для выбранных аналогов "
                "используется аэробная ветка. "
                "Отдельное интервальное "
                "сравнение отсутствует"
            ),
        )

    else:

        status_info = compact_status(
            status
        )

    return {
        **status_info,

        "summary": select_fields(
            interval,

            (
                "compared_workouts_count",
                "total_matched_pairs",
                "total_analyzed_pairs",
                "heart_rate_comparable_pairs",
                "recovery_comparable_checkpoints",
            ),
        ),

        "comparisons": interval.get(
            "comparisons", []
        )[:MAX_HISTORICAL_WORKOUTS],

        "interpretation_notes": [
            (
                "Ноль сопоставимых контрольных "
                "точек восстановления означает "
                "отсутствие пригодных сравнений, "
                "а не отсутствие восстановления"
            ),
        ],
    }


def compact_structural_analysis(structural):
    signature = structural.get(
        "latest_signature"
    ) or {}

    return {
        **compact_status(
            signature.get("status")
        ),

        "comparison_family": structural.get(
            "latest_comparison_family"
        ),

        "load_profile": signature.get(
            "load_profile"
        ),

        "effort_structure": signature.get(
            "effort_structure"
        ),

        "similar_workouts_found": structural.get(
            "similar_workouts_found"
        ),

        "similar_workouts": structural.get(
            "similar_workouts", []
        )[:MAX_HISTORICAL_WORKOUTS],

        "signature_statistics": structural.get(
            "signature_statistics"
        ),
    }


def normalize_completeness(completeness):
    result = dict(
        completeness or {}
    )

    if result.get(
        "interval_analysis_status"
    ) == "not_implemented":

        result[
            "interval_analysis_status"
        ] = "not_applicable"

    return result


def build_workout_llm_context(unified_result):
    """
    Подготавливает ограниченный контекст
    для интерпретации тренировки моделью.

    Поддерживает результат:
    - analyze_latest_workout_unified();
    - analyze_registered_athlete_workout_unified().

    Не передаёт исходные FIT-записи.
    """
    if not isinstance(unified_result, dict):
        raise ValueError(
            "unified_result должен быть словарём"
        )

    if "analysis" in unified_result:

        analysis = unified_result.get(
            "analysis"
        )

    else:

        analysis = unified_result

    if not isinstance(analysis, dict):

        return {
            "status": compact_status(
                unified_result.get("status")
            ),

            "report_available": False,

            "reason": unified_result.get(
                "reason"
            ),

            "fitness_change": None,
        }

    structural = analysis.get(
        "structural_analysis"
    ) or {}

    interval = analysis.get(
        "interval_analysis"
    ) or {}

    target = analysis.get(
        "target_analysis"
    ) or {}

    aerobic = analysis.get(
        "aerobic_analysis"
    ) or {}

    aerobic_history = analysis.get(
        "aerobic_history"
    ) or {}

    completeness = normalize_completeness(
        analysis.get(
            "analysis_completeness"
        )
    )

    report_available = (
        analysis.get("status")
        in {"ok", "partial"}
    )

    return {
        "context_version": "workout_llm_v1",

        "status": compact_status(
            analysis.get("status")
        ),

        "report_available": report_available,

        "reason": analysis.get("reason"),

        "workout": analysis.get(
            "latest_workout"
        ),

        "ftp_info": analysis.get(
            "ftp_info"
        ),

        "conditions": select_fields(
            analysis.get("conditions"),

            (
                "environment",
                "average_temperature",
                "average_weather_temperature",
                "power_meter",
                "ignore_power",
                "ignore_heart_rate",
                "rpe",
            ),
        ),

        "comparison_period_days": analysis.get(
            "comparison_period_days"
        ),

        "structural": compact_structural_analysis(
            structural
        ),

        "intervals": compact_interval_analysis(
            interval
        ),

        "target": compact_target_analysis(
            target
        ),

        "aerobic": compact_aerobic_analysis(
            aerobic
        ),

        "aerobic_history": compact_aerobic_history(
            aerobic_history
        ),

        "completeness": completeness,

        "history_statistics": select_fields(
            analysis.get("history_statistics"),

            (
                "eligible_history_workouts",
                "history_workouts_with_fit",
                "missing_fit_count",
                "history_coverage_complete",
                "aerobic_history_requested",
                "aerobic_history_processed",
            ),
        ),

        "limitations": analysis.get(
            "limitations", []
        ),

        "fitness_change": None,

        "interpretation_rules": [
            "Все числовые показатели рассчитаны Python",

            "Не пересчитывать показатели самостоятельно",

            "None и null означают отсутствие значения",

            "Не интерпретировать null как ноль",

            "Не считать количество пар количеством независимых тренировок",

            "Не называть сравнение отдельных сегментов непрерывным дрейфом",

            "Учитывать качество и ограничения каждого сравнения",

            "Не считать изменение ЧСС или EF доказанным изменением формы",

            "Отрицательный дрейф сам по себе не доказывает улучшение формы",

            "Исторические аналоги с низким сходством использовать только как дополнительный контекст",

            "Не выдумывать температуру, питание, гидратацию и источник мощности",

            "Отсутствие аэробных сегментов не означает отсутствие аэробной нагрузки",
        ],
    }