
from src.analytics.athlete_status import get_registered_athlete_status
from src.analytics.athlete_readiness import evaluate_readiness


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

    return build_athlete_analysis(status)