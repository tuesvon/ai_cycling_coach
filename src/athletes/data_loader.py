from src.athletes.athlete_manager import (
    get_athlete,
    get_registered_athlete_activities,
)
from src.athletes.credentials import get_api_key as get_stored_api_key
from src.integrations.intervals_api import (
    get_activities as get_intervals_activities,
)

from src.athletes.activity_matching import match_activities
from src.athletes.activity_merger import build_unified_activities

SUPPORTED_SOURCES = {"intervals", "garmin"}


def get_registered_athlete_training(athlete_id, days=30):
    athlete = get_athlete(athlete_id)

    if athlete is None:
        raise ValueError("Спортсмен не найден в базе данных")

    training_sources = athlete["data_sources"].get("training", {})

    primary = training_sources.get("primary")
    additional = training_sources.get("additional", [])

    if not primary:
        raise ValueError("Не указан основной источник тренировок")

    sources = list(dict.fromkeys([primary] + additional))

    result = {
        "athlete_id": str(athlete_id),
        "period_days": days,
        "primary_source": primary,
        "sources": {},
    }

    for source in sources:
        if source not in SUPPORTED_SOURCES:
            raise ValueError(
                f"Неподдерживаемый источник тренировок: {source}"
            )

        if source == "intervals":
            api_key = get_stored_api_key(
                athlete_id=str(athlete_id),
                provider="intervals",
            )

            if api_key is None:
                raise ValueError(
                    "Для спортсмена не найден API-ключ Intervals.icu"
                )

            activities = get_intervals_activities(
                days=days,
                api_key=api_key,
            )

        else:
            activities = get_registered_athlete_activities(
                athlete_id=athlete_id,
                days=days,
            )

        result["sources"][source] = activities

    return result

def get_registered_athlete_unified_training(athlete_id, days=30):
    """
    Загружает тренировки из настроенных источников
    и возвращает единый список без дубликатов.
    """

    result = get_registered_athlete_training(
        athlete_id=athlete_id,
        days=days
    )

    sources = result["sources"]

    intervals = sources.get("intervals", [])
    garmin = sources.get("garmin", [])

    matching = match_activities(
        intervals,
        garmin,
        time_tolerance=60
    )

    unified = build_unified_activities(matching)

    return {
        "athlete_id": str(athlete_id),
        "period_days": days,
        "activities": unified,
        "statistics": matching["statistics"],
    }