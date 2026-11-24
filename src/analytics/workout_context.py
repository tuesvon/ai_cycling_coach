import re


CONTEXT_LABELS = {
    "race": "Гонка",
    "structured_workout": "Структурированная тренировка",
    "warmup": "Разминка",
    "cooldown": "Заминка",
    "group_ride": "Групповая поездка",
    "free_ride": "Свободная поездка",
    "unknown": "Неизвестный контекст",
}


WARMUP_PATTERNS = (
    r"\bwarm[\s-]*up\b",
    r"\bразминк[а-я]*\b",
    r"\bpre[\s-]*race\b",
)


COOLDOWN_PATTERNS = (
    r"\bcool[\s-]*down\b",
    r"\bзаминк[а-я]*\b",
    r"\bpost[\s-]*race\b",
)


RACE_PATTERNS = (
    r"\brace\b",
    r"\bzrace\b",
    r"\bracing\b",
    r"\bгонк[а-я]*\b",
    r"\bгонка\b",
    r"\bcriterium\b",
    r"\bкритериум\b",
)


GROUP_RIDE_PATTERNS = (
    r"\bgroup[\s-]*ride\b",
    r"\bpacer\b",
    r"\brobopacer\b",
    r"\bгруппов[а-я]*\b",
)


FREE_RIDE_PATTERNS = (
    r"\bfree[\s-]*ride\b",
    r"\bсвободная поездка\b",
)


STRUCTURED_WORKOUT_PATTERNS = (
    # 5x1:30@375W
    # 4x1:00@375W
    # 2x14x0:10@540W
    r"\d+\s*[xх×]\s*\d+",

    # 60m@175W
    # 146m@175w
    r"\d+\s*(?:m|min|мин)\s*@\s*\d+",

    # 3x20 min
    r"\bintervals\b",

    # Z2 + 1min z4
    r"\bz[1-7]\b",

    r"\bsweet[\s-]*spot\b",
    r"\bthreshold\b",
    r"\bover[\s-]*under\b",
    r"\bvo2[\s-]*max\b",
    r"\bинтервал[а-я]*\b",
)


def normalize_activity_name(name):
    """
    Подготавливает название активности
    для поиска признаков контекста.
    """
    if not isinstance(name, str):
        return ""

    return " ".join(
        name.casefold().split()
    )


def find_matching_patterns(
    name,
    patterns,
):
    """
    Возвращает совпавшие признаки
    из набора регулярных выражений.
    """
    matches = []

    for pattern in patterns:
        match = re.search(
            pattern,
            name,
        )

        if match:
            matches.append(
                match.group(0)
            )

    return list(
        dict.fromkeys(matches)
    )


def get_activity_source_metadata(
    activity,
):
    """
    Получает исходные метаданные
    Intervals.icu и Garmin.

    Не предполагает обязательного
    наличия обоих источников.
    """
    sources = activity.get("sources")

    if not isinstance(sources, dict):
        sources = {}

    intervals = sources.get("intervals")

    if not isinstance(intervals, dict):
        intervals = {}

    garmin = sources.get("garmin")

    if not isinstance(garmin, dict):
        garmin = {}

    return {
        "intervals": intervals,
        "garmin": garmin,
    }


def build_context_result(
    context,
    confidence,
    evidence,
    activity_name,
    has_paired_event=False,
    conflicting_evidence=None,
):
    """
    Формирует стандартизированный
    результат определения контекста.
    """
    return {
        "status": "ok",

        "activity_name": activity_name,

        "activity_context": context,

        "context_label": CONTEXT_LABELS[
            context
        ],

        "confidence": confidence,

        "evidence": list(evidence),

        "conflicting_evidence": (
            list(conflicting_evidence)
            if conflicting_evidence
            else []
        ),

        "has_paired_event": (
            has_paired_event
        ),

        "limitations": [
            (
                "Контекст активности не определяет "
                "фактическую интенсивность нагрузки"
            ),
            (
                "Название активности может "
                "не соответствовать её содержанию"
            ),
            (
                "Связь с запланированным событием "
                "не доказывает выполнение задания"
            ),
        ],
    }


def classify_workout_context(
    activity,
):
    """
    Определяет предполагаемый контекст
    выполненной активности.

    Не анализирует мощность, пульс,
    каденс или тренировочную нагрузку.
    """
    if not isinstance(activity, dict):
        raise ValueError(
            "Активность должна быть словарём"
        )

    metadata = get_activity_source_metadata(
        activity
    )

    intervals = metadata["intervals"]
    garmin = metadata["garmin"]

    activity_name = (
        activity.get("name")
        or intervals.get("name")
        or garmin.get("activityName")
        or ""
    )

    normalized_name = normalize_activity_name(
        activity_name
    )

    paired_event_id = (
        intervals.get("paired_event_id")
        or activity.get("paired_event_id")
    )

    has_paired_event = bool(
        paired_event_id
    )

    # Явные признаки гонки, если они
    # присутствуют в метаданных.
    race_metadata = []

    if activity.get("is_race") is True:
        race_metadata.append(
            "activity.is_race"
        )

    if intervals.get("race") is True:
        race_metadata.append(
            "intervals.race"
        )

    if intervals.get("is_race") is True:
        race_metadata.append(
            "intervals.is_race"
        )

    if garmin.get("isRace") is True:
        race_metadata.append(
            "garmin.isRace"
        )

    warmup_matches = find_matching_patterns(
        normalized_name,
        WARMUP_PATTERNS,
    )

    cooldown_matches = find_matching_patterns(
        normalized_name,
        COOLDOWN_PATTERNS,
    )

    race_matches = find_matching_patterns(
        normalized_name,
        RACE_PATTERNS,
    )

    group_matches = find_matching_patterns(
        normalized_name,
        GROUP_RIDE_PATTERNS,
    )

    free_ride_matches = find_matching_patterns(
        normalized_name,
        FREE_RIDE_PATTERNS,
    )

    structured_matches = find_matching_patterns(
        normalized_name,
        STRUCTURED_WORKOUT_PATTERNS,
    )

    # Противоречие между разминкой и заминкой.
    if warmup_matches and cooldown_matches:
        return build_context_result(
            context="unknown",
            confidence="low",

            evidence=[
                *warmup_matches,
                *cooldown_matches,
            ],

            activity_name=activity_name,

            has_paired_event=has_paired_event,

            conflicting_evidence=[
                "warmup_and_cooldown",
            ],
        )

    # Явная метка гонки одновременно
    # с названием разминки или заминки.
    if race_metadata and (
        warmup_matches
        or cooldown_matches
    ):
        return build_context_result(
            context="unknown",
            confidence="low",

            evidence=[
                *race_metadata,
                *warmup_matches,
                *cooldown_matches,
            ],

            activity_name=activity_name,

            has_paired_event=has_paired_event,

            conflicting_evidence=[
                "race_and_preparation_context",
            ],
        )

    # Разминка имеет приоритет над словом
    # Race в названии Pre-Race Warm-up.
    if warmup_matches:
        return build_context_result(
            context="warmup",
            confidence="medium",
            evidence=warmup_matches,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    if cooldown_matches:
        return build_context_result(
            context="cooldown",
            confidence="medium",
            evidence=cooldown_matches,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    # Явные метаданные гонки.
    if race_metadata:
        return build_context_result(
            context="race",
            confidence="high",

            evidence=[
                *race_metadata,
                *race_matches,
            ],

            activity_name=activity_name,

            has_paired_event=has_paired_event,
        )

    # Гонка по названию.
    if race_matches:
        return build_context_result(
            context="race",
            confidence="medium",
            evidence=race_matches,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    # Групповая поездка.
    if group_matches:
        return build_context_result(
            context="group_ride",
            confidence="medium",
            evidence=group_matches,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    # Свободная поездка.
    if free_ride_matches:
        return build_context_result(
            context="free_ride",
            confidence="medium",
            evidence=free_ride_matches,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    # Предполагаемая структурированная
    # тренировка по названию.
    if structured_matches:
        evidence = list(
            structured_matches
        )

        if has_paired_event:
            evidence.append(
                "paired_event"
            )

        return build_context_result(
            context="structured_workout",
            confidence="medium",
            evidence=evidence,
            activity_name=activity_name,
            has_paired_event=has_paired_event,
        )

    # Связь с событием сама по себе
    # не определяет его тип.
    if has_paired_event:
        return build_context_result(
            context="unknown",
            confidence="low",
            evidence=["paired_event"],
            activity_name=activity_name,
            has_paired_event=True,
        )

    return build_context_result(
        context="unknown",
        confidence="low",
        evidence=[],
        activity_name=activity_name,
        has_paired_event=False,
    )