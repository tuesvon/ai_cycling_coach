from src.analytics.athlete_status import get_registered_athlete_status
from src.analytics.athlete_readiness import evaluate_readiness
from src.athletes.athlete_manager import get_athlete_capabilities


def build_athlete_analysis(status):
    """
    Собирает единый аналитический контекст спортсмена
    на основе уже рассчитанного статуса.
    """

    analysis = dict(status)

    # Итоговая оценка готовности спортсмена.
    analysis["readiness"] = evaluate_readiness(status)

    return analysis


def get_registered_athlete_analysis(athlete_id):
    """
    Получает данные зарегистрированного спортсмена
    и формирует единый аналитический контекст.
    """
    status = get_registered_athlete_status(athlete_id)

    analysis = build_athlete_analysis(status)

    # Возможности и оборудование спортсмена.
    analysis["capabilities"] = get_athlete_capabilities(athlete_id)

    return analysis